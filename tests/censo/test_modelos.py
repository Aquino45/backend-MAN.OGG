"""Tests de los modelos Sector y Arbol."""

from decimal import Decimal
from uuid import UUID

import pytest
from django.conf import settings
from django.contrib.gis.geos import Point, Polygon
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError

from apps.censo.models import Arbol, Sector
from config.constantes import SRID_UTM_CENSO, TOPE_DESTACADOS_POR_SECTOR

ESTE_BASE = 300000.0
NORTE_BASE = 8673000.0
MOTIVO_DESTACADO = "Ejemplar de mayor copa del sector"
SECTOR_VECINO_ID = 2


@pytest.fixture
def sector(db):
    """Un sector cuadrado de 100 m de lado."""
    cuadrado = Polygon.from_bbox((ESTE_BASE, NORTE_BASE, ESTE_BASE + 100, NORTE_BASE + 100))
    cuadrado.srid = SRID_UTM_CENSO
    return Sector.objects.create(id=1, nombre="Sector 1", geom=cuadrado, fuente="Prueba")


def _arbol(sector, **extra):
    datos = {"codigo": "S01-A001", "sector": sector, "fuente": "Prueba, fila 2"}
    datos.update(extra)
    return Arbol(**datos)


@pytest.mark.django_db
@pytest.mark.parametrize("tabla", [Sector._meta.db_table, Arbol._meta.db_table])
def test_las_tablas_quedan_en_el_esquema_de_settings(tabla):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_schema FROM information_schema.tables WHERE table_name = %s", [tabla]
        )
        esquemas = [fila[0] for fila in cursor.fetchall()]

    assert esquemas == [settings.DB_ESQUEMA]


def test_sector_usa_entero_pequeno_como_clave():
    assert Sector._meta.pk.get_internal_type() == "PositiveSmallIntegerField"


def test_los_campos_geograficos_usan_el_srid_utm():
    assert Sector._meta.get_field("geom").srid == SRID_UTM_CENSO
    assert Arbol._meta.get_field("ubicacion").srid == SRID_UTM_CENSO


def test_valores_por_defecto(sector):
    arbol = _arbol(sector)

    assert arbol.demo is False
    assert arbol.ubicacion is None
    assert arbol.fecha_registro is None
    assert arbol.dap_cm is None
    assert arbol.nombre_comun is None
    assert arbol.destacado is False
    assert arbol.motivo_destacado is None


@pytest.mark.django_db
def test_guarda_con_fechas_automaticas_y_medidas_decimales(sector):
    arbol = _arbol(
        sector,
        dap_cm=Decimal("35.5"),
        ubicacion=Point(ESTE_BASE + 10, NORTE_BASE + 10, srid=SRID_UTM_CENSO),
    )
    arbol.save()
    arbol.refresh_from_db()

    assert arbol.creado_en is not None
    assert arbol.actualizado_en >= arbol.creado_en
    assert arbol.dap_cm == Decimal("35.500")
    assert arbol.ubicacion.srid == SRID_UTM_CENSO


@pytest.mark.parametrize("codigo", ["S1-A001", "s01-A001", "S01-a001", "S01-A01", "S01-AA001", ""])
def test_codigo_con_formato_invalido_no_valida(sector, codigo):
    with pytest.raises(ValidationError) as error:
        _arbol(sector, codigo=codigo).full_clean()

    assert "codigo" in error.value.message_dict


@pytest.mark.django_db
def test_codigo_es_unico(sector):
    _arbol(sector).save()

    with pytest.raises(IntegrityError), transaction.atomic():
        _arbol(sector).save()


@pytest.mark.django_db
def test_fuente_vacia_se_rechaza_en_validacion_y_en_la_bd(sector):
    with pytest.raises(ValidationError) as error:
        _arbol(sector, fuente="").full_clean()
    assert "fuente" in error.value.message_dict

    with pytest.raises(IntegrityError), transaction.atomic():
        _arbol(sector, fuente="").save()


@pytest.mark.django_db
def test_no_se_borra_un_sector_con_arboles(sector):
    _arbol(sector).save()

    with pytest.raises(ProtectedError):
        sector.delete()


def test_textos_para_leer_en_el_admin(sector):
    assert str(sector) == "Sector 1"
    assert str(_arbol(sector)) == "S01-A001"
    assert str(_arbol(sector, nombre_comun="Molle")) == "S01-A001 · Molle"


def test_admin_registra_sector_y_arbol():
    from django.contrib import admin

    assert Sector in admin.site._registry
    assert Arbol in admin.site._registry


@pytest.mark.django_db
def test_admin_redirige_a_login_sin_sesion(client):
    respuesta = client.get(f"/{settings.ADMIN_RUTA}")

    assert respuesta.status_code == 302
    assert respuesta.url.startswith(f"/{settings.ADMIN_RUTA}login/")


def _codigo_numerado(sector_id, numero):
    return f"S{sector_id:02d}-A{numero:03d}"


def _guardar_destacados(sector, cantidad):
    """Guarda `cantidad` árboles destacados en el sector y devuelve sus códigos."""
    codigos = []
    for numero in range(1, cantidad + 1):
        codigo = _codigo_numerado(sector.id, numero)
        _arbol(sector, codigo=codigo, destacado=True, motivo_destacado=MOTIVO_DESTACADO).save()
        codigos.append(codigo)
    return codigos


@pytest.fixture
def sector_vecino(db):
    """Otro sector cuadrado, al lado del primero."""
    cuadrado = Polygon.from_bbox((ESTE_BASE + 200, NORTE_BASE, ESTE_BASE + 300, NORTE_BASE + 100))
    cuadrado.srid = SRID_UTM_CENSO
    return Sector.objects.create(
        id=SECTOR_VECINO_ID, nombre="Sector 2", geom=cuadrado, fuente="Prueba"
    )


@pytest.mark.django_db
def test_cada_arbol_recibe_un_uid_uuid_distinto(sector):
    primero = _arbol(sector)
    segundo = _arbol(sector, codigo="S01-A002")
    primero.save()
    segundo.save()

    assert isinstance(primero.uid, UUID)
    assert primero.uid.version == 4
    assert primero.uid != segundo.uid


@pytest.mark.django_db
def test_el_uid_no_cambia_al_guardar_de_nuevo(sector):
    arbol = _arbol(sector)
    arbol.save()
    uid_original = arbol.uid

    arbol.nombre_comun = "Molle"
    arbol.save()
    arbol.refresh_from_db()

    assert arbol.uid == uid_original


def test_el_uid_es_unico_y_no_se_edita():
    campo = Arbol._meta.get_field("uid")

    assert campo.unique is True
    assert campo.editable is False


@pytest.mark.django_db
@pytest.mark.parametrize("motivo", [None, "", "   "])
def test_destacado_sin_motivo_valida_y_el_motivo_queda_en_null(sector, motivo):
    arbol = _arbol(sector, destacado=True, motivo_destacado=motivo)

    arbol.full_clean()
    arbol.save()
    arbol.refresh_from_db()

    assert (arbol.destacado, arbol.motivo_destacado) == (True, None)


@pytest.mark.django_db
def test_destacado_con_motivo_valida_y_se_guarda(sector):
    arbol = _arbol(sector, destacado=True, motivo_destacado=MOTIVO_DESTACADO)

    arbol.full_clean()
    arbol.save()
    arbol.refresh_from_db()

    assert (arbol.destacado, arbol.motivo_destacado) == (True, MOTIVO_DESTACADO)


@pytest.mark.django_db
def test_no_destacado_con_motivo_deja_el_motivo_en_null(sector):
    arbol = _arbol(sector, destacado=False, motivo_destacado=MOTIVO_DESTACADO)

    arbol.full_clean()

    assert arbol.motivo_destacado is None


@pytest.mark.django_db
def test_el_siguiente_destacado_del_sector_lleno_no_valida_y_nombra_los_actuales(sector):
    codigos_actuales = _guardar_destacados(sector, TOPE_DESTACADOS_POR_SECTOR)
    aspirante = _arbol(
        sector,
        codigo=_codigo_numerado(sector.id, TOPE_DESTACADOS_POR_SECTOR + 1),
        destacado=True,
        motivo_destacado=MOTIVO_DESTACADO,
    )

    with pytest.raises(ValidationError) as error:
        aspirante.full_clean()

    mensaje = " ".join(error.value.message_dict["destacado"])
    assert str(TOPE_DESTACADOS_POR_SECTOR) in mensaje
    for codigo in codigos_actuales:
        assert codigo in mensaje
    assert codigos_actuales == sorted(codigos_actuales)
    assert mensaje.index(codigos_actuales[0]) < mensaje.index(codigos_actuales[-1])


@pytest.mark.django_db
def test_un_destacado_de_otro_sector_valida_aunque_el_primero_este_lleno(sector, sector_vecino):
    _guardar_destacados(sector, TOPE_DESTACADOS_POR_SECTOR)
    del_vecino = _arbol(
        sector_vecino,
        codigo=_codigo_numerado(sector_vecino.id, 1),
        destacado=True,
        motivo_destacado=MOTIVO_DESTACADO,
    )

    del_vecino.full_clean()


@pytest.mark.django_db
def test_validar_otra_vez_a_un_destacado_con_el_sector_lleno_pasa(sector):
    _guardar_destacados(sector, TOPE_DESTACADOS_POR_SECTOR)
    ya_destacado = Arbol.objects.get(codigo=_codigo_numerado(sector.id, 1))

    ya_destacado.full_clean()


@pytest.mark.django_db
def test_un_destacado_hasta_el_tope_valida(sector):
    _guardar_destacados(sector, TOPE_DESTACADOS_POR_SECTOR - 1)
    ultimo = _arbol(
        sector,
        codigo=_codigo_numerado(sector.id, TOPE_DESTACADOS_POR_SECTOR),
        destacado=True,
        motivo_destacado=MOTIVO_DESTACADO,
    )

    ultimo.full_clean()
