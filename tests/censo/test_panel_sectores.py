"""Tests de las fronteras del sector en el panel: widget, vista previa, recálculo y permisos."""

import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse

from apps.censo.admin_geometrias import MapaEditable
from apps.censo.models import Arbol, Sector
from apps.censo.servicios import geometrias
from config.constantes import (
    ESTADO_REGISTRO_EN_REVISION,
    ESTADO_REGISTRO_PUBLICADO,
    NOMBRE_ROL_ADMINISTRADOR,
    NOMBRE_ROL_EDITOR,
    PERMISOS_POR_ROL,
    SRID_UTM_CENSO,
    TOLERANCIA_FUERA_DE_SECTOR_M,
)
from tests.censo.conftest import arbol_evaluado
from tests.censo.test_panel_geometrias import en_el_widget

SECTOR = 1
RADIO_DEL_NUEVO_POLIGONO_M = 30
LEJOS_M = 100
"""Cuánto se aparta el segundo árbol: más que el radio del polígono nuevo y la tolerancia."""


@pytest.fixture
def dos_arboles(sectores):
    """Un árbol dentro del sector y otro 100 m al este, también registrado en el sector 1."""
    cerca = arbol_evaluado("S01-A001")
    punto = Point(cerca.ubicacion.x + LEJOS_M, cerca.ubicacion.y, srid=SRID_UTM_CENSO)
    lejos = arbol_evaluado("S01-A002", ubicacion=punto)
    assert lejos.estado_registro == ESTADO_REGISTRO_PUBLICADO
    return cerca, lejos


@pytest.fixture
def poligono_alrededor_del_primero(dos_arboles):
    """Un polígono nuevo que contiene al primer árbol y deja al segundo a 70 m."""
    return dos_arboles[0].ubicacion.buffer(RADIO_DEL_NUEVO_POLIGONO_M)


def datos_del_sector(poligono, **extra):
    sector = Sector.objects.get(id=SECTOR)
    datos = {
        "id": sector.id,
        "nombre": sector.nombre,
        "geom": en_el_widget(poligono),
        "color": sector.color or "",
        "fuente": sector.fuente,
    }
    if sector.provisional:
        datos["provisional"] = "on"
    return {**datos, **extra}


def ruta_del_sector():
    return reverse("admin:censo_sector_change", args=[SECTOR])


# --- servicio ----------------------------------------------------------------------------------


def test_el_servicio_cuenta_los_arboles_que_quedarian_fuera_del_poligono_nuevo(
    dos_arboles, poligono_alrededor_del_primero
):
    cuantos = geometrias.contar_arboles_fuera(SECTOR, poligono_alrededor_del_primero)

    assert cuantos == 1


def test_un_arbol_a_menos_de_la_tolerancia_no_cuenta(dos_arboles):
    cerca, lejos = dos_arboles
    poligono = cerca.ubicacion.buffer(LEJOS_M - TOLERANCIA_FUERA_DE_SECTOR_M + 1)

    assert geometrias.contar_arboles_fuera(SECTOR, poligono) == 0


def test_el_conteo_no_toca_la_base(dos_arboles, poligono_alrededor_del_primero):
    geometrias.contar_arboles_fuera(SECTOR, poligono_alrededor_del_primero)

    assert Sector.objects.get(id=SECTOR).geom.contains(dos_arboles[0].ubicacion)
    assert all(a.estado_registro == ESTADO_REGISTRO_PUBLICADO for a in Arbol.objects.all())


def test_recalcular_el_sector_manda_a_revision_a_los_que_quedaron_fuera(
    dos_arboles, poligono_alrededor_del_primero
):
    Sector.objects.filter(id=SECTOR).update(geom=poligono_alrededor_del_primero)

    resultado = geometrias.recalcular_calidad_del_sector(Sector.objects.get(id=SECTOR))

    cerca, lejos = dos_arboles
    cerca.refresh_from_db()
    lejos.refresh_from_db()
    assert (resultado.a_revision, resultado.publicados) == (1, 0)
    assert cerca.estado_registro == ESTADO_REGISTRO_PUBLICADO
    assert lejos.estado_registro == ESTADO_REGISTRO_EN_REVISION
    assert "La ubicación cae a" in lejos.motivos_revision


def test_recalcular_el_sector_vuelve_a_publicar_si_el_poligono_los_recupera(dos_arboles):
    cerca, lejos = dos_arboles
    Sector.objects.filter(id=SECTOR).update(geom=cerca.ubicacion.buffer(RADIO_DEL_NUEVO_POLIGONO_M))
    geometrias.recalcular_calidad_del_sector(Sector.objects.get(id=SECTOR))

    Sector.objects.filter(id=SECTOR).update(geom=cerca.ubicacion.buffer(LEJOS_M * 2))
    resultado = geometrias.recalcular_calidad_del_sector(Sector.objects.get(id=SECTOR))

    lejos.refresh_from_db()
    assert (resultado.a_revision, resultado.publicados) == (0, 1)
    assert lejos.estado_registro == ESTADO_REGISTRO_PUBLICADO


def test_recalcular_el_sector_deja_el_cambio_en_el_historial_de_cada_arbol(
    dos_arboles, poligono_alrededor_del_primero
):
    cerca, lejos = dos_arboles
    antes = lejos.history.count()
    Sector.objects.filter(id=SECTOR).update(geom=poligono_alrededor_del_primero)

    geometrias.recalcular_calidad_del_sector(Sector.objects.get(id=SECTOR))

    assert lejos.history.count() == antes + 1
    assert cerca.history.count() == 1
    assert "sector 1" in lejos.history.first().history_change_reason


# --- el formulario del sector ------------------------------------------------------------------


def test_el_campo_geom_usa_el_widget_del_mapa_con_los_vecinos_como_contexto(
    cliente_administrador, sectores
):
    formulario = cliente_administrador.get(ruta_del_sector()).context["adminform"].form

    widget = formulario.fields["geom"].widget
    assert isinstance(widget, MapaEditable)
    assert widget.vinculos["parametros_contexto"] == {"sector": SECTOR}
    assert widget.vinculos["campos"] is None


def test_el_contexto_del_sector_trae_los_vecinos_y_sus_arboles(cliente_administrador, dos_arboles):
    arbol_evaluado("S02-A001", sector_id=2)

    cuerpo = cliente_administrador.get(
        reverse("admin:censo_sector_contexto_del_mapa"), {"sector": SECTOR}
    ).json()

    sectores = sorted(e["properties"]["id"] for e in cuerpo["features"] if "id" in e["properties"])
    codigos = sorted(
        e["properties"]["codigo"] for e in cuerpo["features"] if "codigo" in e["properties"]
    )
    assert sectores == [2, 3, 4, 5]
    assert codigos == ["S01-A001", "S01-A002"]


def test_sin_arboles_fuera_el_sector_se_guarda_directo_y_sin_aviso(
    cliente_administrador, dos_arboles
):
    poligono = Sector.objects.get(id=SECTOR).geom.buffer(5)

    respuesta = cliente_administrador.post(
        ruta_del_sector(), datos_del_sector(poligono), follow=True
    )

    avisos = [str(m) for m in respuesta.context["messages"]]
    assert not any("pasaron a revisión" in a or "pasó a revisión" in a for a in avisos)
    assert Sector.objects.get(id=SECTOR).geom.area == pytest.approx(poligono.area, rel=1e-6)
    assert "Guardar igual" not in respuesta.content.decode()


def test_la_vista_previa_cuenta_los_arboles_y_no_guarda_hasta_guardar_igual(
    cliente_administrador, dos_arboles, poligono_alrededor_del_primero
):
    original = Sector.objects.get(id=SECTOR).geom.area

    respuesta = cliente_administrador.post(
        ruta_del_sector(), datos_del_sector(poligono_alrededor_del_primero)
    )

    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "1 árbol quedaría a más de 15 m del sector" in contenido
    assert 'name="guardar_igual"' in contenido
    assert "pasaría a revisión" not in contenido  # la vista previa no promete el estado
    assert Sector.objects.get(id=SECTOR).geom.area == pytest.approx(original)
    assert dos_arboles[1].history.count() == 1


def test_guardar_igual_guarda_recalcula_y_avisa_con_el_conteo(
    cliente_administrador, dos_arboles, poligono_alrededor_del_primero
):
    datos = datos_del_sector(poligono_alrededor_del_primero, guardar_igual="Guardar igual")

    respuesta = cliente_administrador.post(ruta_del_sector(), datos, follow=True)

    cerca, lejos = dos_arboles
    lejos.refresh_from_db()
    assert Sector.objects.get(id=SECTOR).geom.area == pytest.approx(
        poligono_alrededor_del_primero.area, rel=1e-6
    )
    assert lejos.estado_registro == ESTADO_REGISTRO_EN_REVISION
    avisos = [str(m) for m in respuesta.context["messages"]]
    assert "1 árbol quedó fuera del sector y pasó a revisión" in " ".join(avisos)


def test_el_aviso_va_en_plural_con_varios_arboles(cliente_administrador, dos_arboles):
    cerca, lejos = dos_arboles
    poligono = Point(cerca.ubicacion.x, cerca.ubicacion.y + 5000, srid=SRID_UTM_CENSO).buffer(
        RADIO_DEL_NUEVO_POLIGONO_M
    )

    respuesta = cliente_administrador.post(
        ruta_del_sector(), datos_del_sector(poligono, guardar_igual="Guardar igual"), follow=True
    )

    avisos = " ".join(str(m) for m in respuesta.context["messages"])
    assert "2 árboles quedaron fuera del sector y pasaron a revisión" in avisos


def test_el_cambio_de_frontera_queda_en_el_historial_del_sector(
    cliente_administrador, dos_arboles, poligono_alrededor_del_primero
):
    sector = Sector.objects.get(id=SECTOR)
    antes = sector.history.count()

    cliente_administrador.post(
        ruta_del_sector(),
        datos_del_sector(poligono_alrededor_del_primero, guardar_igual="Guardar igual"),
    )

    ultima = sector.history.first()
    assert sector.history.count() == antes + 1
    assert ultima.geom.area == pytest.approx(poligono_alrededor_del_primero.area, rel=1e-6)


def test_guardar_el_sector_sin_tocar_la_geometria_no_recalcula(cliente_administrador, dos_arboles):
    sector = Sector.objects.get(id=SECTOR)
    lejos = dos_arboles[1]

    cliente_administrador.post(
        ruta_del_sector(), datos_del_sector(sector.geom, nombre="Nombre nuevo")
    )

    assert Sector.objects.get(id=SECTOR).nombre == "Nombre nuevo"
    assert lejos.history.count() == 1


# --- permisos ----------------------------------------------------------------------------------


def test_solo_el_administrador_tiene_el_permiso_de_cambiar_sectores():
    assert "change_sector" in PERMISOS_POR_ROL[NOMBRE_ROL_ADMINISTRADOR]
    assert "change_sector" not in PERMISOS_POR_ROL[NOMBRE_ROL_EDITOR]


def test_el_editor_no_edita_las_fronteras_ni_usa_el_contexto_del_sector(
    cliente_editor, dos_arboles, poligono_alrededor_del_primero
):
    original = Sector.objects.get(id=SECTOR).geom.area

    editado = cliente_editor.post(
        ruta_del_sector(),
        datos_del_sector(poligono_alrededor_del_primero, guardar_igual="Guardar igual"),
    )
    contexto = cliente_editor.get(reverse("admin:censo_sector_contexto_del_mapa"))

    assert editado.status_code == 403
    assert contexto.status_code == 403
    assert Sector.objects.get(id=SECTOR).geom.area == pytest.approx(original)
