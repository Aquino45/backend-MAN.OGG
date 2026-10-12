"""Tests de la carga y el borrado de los árboles simulados.

Los archivos de prueba son chicos, se escriben en `tmp_path` con la forma del archivo real y se
apoyan en los sectores reales de `conftest.py`; nunca se usa el archivo de datos real.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO

import pytest
from django.contrib.gis.db.models.functions import PointOnSurface, Transform
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.censo.models import Arbol, Sector
from apps.censo.servicios.cargar_demo import ReporteDemo, borrar_demo, cargar_demo
from apps.censo.servicios.importar_planilla import ArbolFueraDeSector
from apps.censo.servicios.resolver_campos import texto_de
from config.constantes import (
    DECIMALES_UTM,
    ESTADO_REGISTRO_EN_REVISION,
    ESTADO_REGISTRO_PUBLICADO,
    LETRA_CODIGO_DEMO,
    SRID_MAPA,
    SRID_UTM_CENSO,
    TOPE_DESTACADOS_POR_SECTOR,
)

pytestmark = pytest.mark.usefixtures("especie_molle")

MOTIVO = "Dato de ejemplo: ejemplar de gran porte (simulado)"
FUENTE = "Dato simulado (demo): ubicación al azar dentro del sector; no es del censo."
ORDEN_DEL_REAL_CON_LETRA_DEMO = 5
ORDEN_SIN_CHOQUES = 11
"""Orden desde el que los árboles de prueba no chocan con el real de letra demo."""


def codigo_demo(id_sector, orden, letra=LETRA_CODIGO_DEMO):
    return f"S{id_sector:02d}-{letra}{orden:03d}"


def lat_lon_dentro(id_sector):
    """(lat, lon) de un punto dentro del sector, calculado por PostGIS."""
    punto = (
        Sector.objects.filter(id=id_sector)
        .annotate(centro=Transform(PointOnSurface("geom"), SRID_MAPA))
        .get()
        .centro
    )
    return punto.y, punto.x


def registro(id_sector=2, orden=1, **cambios):
    """Un árbol simulado con todas las claves del archivo real."""
    lat, lon = lat_lon_dentro(id_sector)
    datos = {
        "codigo": codigo_demo(id_sector, orden),
        "sector": id_sector,
        "nombre_comun": "Molle",
        "nombre_cientifico": "Schinus molle",
        "identificacion": "Identificada",
        "origen": "Nativa",
        "condicion_conservacion": None,
        "lat": lat,
        "lon": lon,
        "altura_total_m": 8.5,
        "dap_cm": 35.25,
        "copa_ns_m": 4.5,
        "copa_eo_m": 5.0,
        "estado_general": "Bueno",
        "estado_copa": "Buena",
        "tronco_danos": "Sin daño aparente",
        "raices_base": "Sin daño aparente",
        "interferencia_entorno": "Ninguna",
        "observaciones": None,
        "foto_url": None,
        "foto_miniatura_url": None,
        "co2_almacenado_kg": 120.5,
        "co2_captura_anual_kg": 10.25,
        "fuente": FUENTE,
        "fecha_registro": None,
        "demo": True,
        "destacado": False,
        "motivo_destacado": None,
    }
    datos.update(cambios)
    return datos


def destacado(id_sector, orden, **cambios):
    datos = {"destacado": True, "motivo_destacado": MOTIVO, **cambios}
    return registro(id_sector, orden, **datos)


def escribir(tmp_path, registros, nombre="demo-prueba.json"):
    ruta = tmp_path / nombre
    ruta.write_text(json.dumps(registros, ensure_ascii=False), encoding="utf-8")
    return ruta


def utm_calculada_por_postgis(lat, lon):
    """(este, norte) que da PostGIS al transformar el punto WGS84 al UTM del censo."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ST_X(p), ST_Y(p) FROM (SELECT ST_Transform("
            "ST_SetSRID(ST_MakePoint(%s, %s), %s), %s) AS p) AS t",
            [lon, lat, SRID_MAPA, SRID_UTM_CENSO],
        )
        return cursor.fetchone()


def crear_real(codigo="S02-A001", **cambios):
    datos = {"sector_id": 2, "fuente": "Brigada A", "demo": False}
    datos.update(cambios)
    return Arbol.objects.create(codigo=codigo, **datos)


# --- carga ---------------------------------------------------------------------------------


def test_carga_guarda_los_campos_tal_como_vienen(sectores, tmp_path):
    lat, lon = lat_lon_dentro(2)
    ruta = escribir(
        tmp_path,
        [
            registro(2, 1, fecha_registro="2026-10-07", condicion_conservacion=None),
            destacado(2, 2, altura_total_m=None, observaciones="Cerca del paradero"),
        ],
    )

    reporte = cargar_demo(ruta)

    simple = Arbol.objects.get(codigo="S02-D001")
    assert (reporte.creados, reporte.actualizados) == (2, 0)
    assert simple.demo is True
    assert simple.sector_id == 2
    assert simple.fuente == FUENTE
    assert simple.destacado is False and simple.motivo_destacado is None
    assert str(simple.fecha_registro) == "2026-10-07"
    assert texto_de(simple, "nombre_cientifico") == "Schinus molle"
    assert simple.condicion_conservacion is None
    assert simple.co2_almacenado_kg == Decimal("120.5")
    assert simple.co2_captura_anual_kg == Decimal("10.25")
    assert simple.co2_simulado is True
    assert simple.dap_cm == Decimal("35.25")
    este, norte = utm_calculada_por_postgis(lat, lon)
    assert simple.ubicacion.srid == SRID_UTM_CENSO
    tolerancia = 10**-DECIMALES_UTM
    assert (simple.ubicacion.x, simple.ubicacion.y) == pytest.approx((este, norte), abs=tolerancia)
    marcado = Arbol.objects.get(codigo="S02-D002")
    assert marcado.destacado is True and marcado.motivo_destacado == MOTIVO
    assert marcado.altura_total_m is None
    assert marcado.observaciones == "Cerca del paradero"
    assert marcado.fecha_registro is None


def test_sin_lat_lon_el_arbol_se_guarda_sin_ubicacion(sectores, tmp_path):
    ruta = escribir(tmp_path, [registro(2, 1, lat=None, lon=None)])

    cargar_demo(ruta)

    assert Arbol.objects.get(codigo="S02-D001").ubicacion is None


def test_segunda_carga_actualiza_sin_duplicar_y_conserva_el_uid(sectores, tmp_path):
    registros = [registro(2, 1), destacado(3, 1), registro(4, 1)]
    ruta = escribir(tmp_path, registros)
    cargar_demo(ruta)
    uids = dict(Arbol.objects.values_list("codigo", "uid"))

    registros[0]["observaciones"] = "Junto a la banca"
    reporte = cargar_demo(escribir(tmp_path, registros))

    assert (reporte.creados, reporte.actualizados) == (0, 3)
    assert Arbol.objects.count() == 3
    assert dict(Arbol.objects.values_list("codigo", "uid")) == uids
    assert Arbol.objects.get(codigo="S02-D001").observaciones == "Junto a la banca"


def test_recarga_puede_cambiar_cuales_son_los_destacados_sin_chocar_con_el_tope(sectores, tmp_path):
    ordenes = range(1, 2 * TOPE_DESTACADOS_POR_SECTOR + 1)
    primeros = [destacado(2, orden) for orden in ordenes[:TOPE_DESTACADOS_POR_SECTOR]]
    siguientes = [destacado(2, orden) for orden in ordenes[TOPE_DESTACADOS_POR_SECTOR:]]
    cargar_demo(
        escribir(
            tmp_path,
            primeros + [registro(2, orden) for orden in ordenes[TOPE_DESTACADOS_POR_SECTOR:]],
        )
    )

    quitados = [registro(2, orden) for orden in ordenes[:TOPE_DESTACADOS_POR_SECTOR]]
    reporte = cargar_demo(escribir(tmp_path, siguientes + quitados))

    assert reporte.actualizados == 2 * TOPE_DESTACADOS_POR_SECTOR
    codigos = set(Arbol.objects.filter(destacado=True).values_list("codigo", flat=True))
    assert codigos == {codigo_demo(2, orden) for orden in ordenes[TOPE_DESTACADOS_POR_SECTOR:]}
    assert Arbol.objects.filter(destacado=False, motivo_destacado__isnull=False).count() == 0


def test_reporte_cuenta_los_destacados_de_cada_sector(sectores, tmp_path):
    registros = [destacado(2, 1), destacado(2, 2), registro(2, 3), destacado(3, 1), registro(4, 1)]

    reporte = cargar_demo(escribir(tmp_path, registros))

    assert isinstance(reporte, ReporteDemo)
    assert reporte.archivo == "demo-prueba.json"
    assert (reporte.creados, reporte.actualizados) == (len(registros), 0)
    assert reporte.destacados_por_sector == {2: 2, 3: 1, 4: 0}
    assert reporte.fuera_de_sector == []


def test_un_punto_lejos_de_su_poligono_se_avisa_pero_se_guarda(sectores, tmp_path):
    lat, lon = lat_lon_dentro(3)
    ruta = escribir(tmp_path, [registro(2, 1, lat=lat, lon=lon), registro(2, 2)])

    reporte = cargar_demo(ruta)

    assert Arbol.objects.count() == 2
    assert len(reporte.fuera_de_sector) == 1
    aviso = reporte.fuera_de_sector[0]
    assert isinstance(aviso, ArbolFueraDeSector)
    assert (aviso.codigo, aviso.sector) == ("S02-D001", 2)
    assert aviso.distancia_m > 0


# --- borrado -------------------------------------------------------------------------------


def test_borrar_demo_solo_borra_los_simulados(sectores, tmp_path):
    cargar_demo(escribir(tmp_path, [registro(2, 1), destacado(3, 1), registro(5, 1)]))
    real = crear_real("S02-A001")
    real_con_letra_demo = crear_real(codigo_demo(2, 9))
    demo_con_letra_real = crear_real("S02-A002", demo=True)

    borrados = borrar_demo()

    assert borrados == 3
    assert set(Arbol.objects.values_list("codigo", flat=True)) == {
        real.codigo,
        real_con_letra_demo.codigo,
        demo_con_letra_real.codigo,
    }


def test_borrar_demo_sin_simulados_devuelve_cero(sectores):
    crear_real()

    assert borrar_demo() == 0
    assert Arbol.objects.count() == 1


def test_borrar_demo_borra_tambien_los_simulados_de_la_papelera_pero_no_los_reales(
    sectores, tmp_path
):
    cargar_demo(escribir(tmp_path, [registro(2, 1), registro(3, 1)]))
    Arbol.objects.filter(codigo=codigo_demo(2, 1)).update(eliminado_en=datetime.now(tz=UTC))
    real_en_papelera = crear_real("S02-A001", eliminado_en=datetime.now(tz=UTC))

    borrados = borrar_demo()

    assert borrados == 2
    assert list(Arbol.todos.values_list("codigo", flat=True)) == [real_en_papelera.codigo]


def test_cargar_demo_rechaza_un_simulado_que_esta_en_la_papelera(sectores, tmp_path):
    ruta = escribir(tmp_path, [registro(2, 1)])
    cargar_demo(ruta)
    Arbol.objects.filter(codigo=codigo_demo(2, 1)).update(eliminado_en=datetime.now(tz=UTC))

    with pytest.raises(ValueError, match="está en la papelera; puede restaurarse"):
        cargar_demo(ruta)

    assert Arbol.todos.count() == 1


def test_cargar_demo_no_pisa_un_real_de_la_papelera(sectores, tmp_path):
    crear_real(codigo_demo(2, 1), eliminado_en=datetime.now(tz=UTC))

    with pytest.raises(ValueError, match="ya pertenece a un árbol real"):
        cargar_demo(escribir(tmp_path, [registro(2, 1)]))


# --- rechazos: el archivo entero se descarta -----------------------------------------------


def _con(campo, valor):
    return lambda: [registro(2, 2), registro(2, 1, **{campo: valor})]


def test_un_destacado_sin_motivo_se_carga_con_el_motivo_en_null(sectores, tmp_path):
    ruta = escribir(tmp_path, [destacado(2, 1, motivo_destacado=None)])

    cargar_demo(ruta)

    arbol = Arbol.objects.get(codigo="S02-D001")
    assert (arbol.destacado, arbol.motivo_destacado) == (True, None)


def test_un_simulado_completo_queda_publicado_y_uno_incompleto_en_revision(sectores, tmp_path):
    completo = registro(2, 1, tipo_individuo="Árbol ≥1.30 m (medir DAP)")
    incompleto = registro(2, 2)  # sin tipo_individuo
    ruta = escribir(tmp_path, [completo, incompleto])

    cargar_demo(ruta)

    assert Arbol.objects.get(codigo="S02-D001").estado_registro == ESTADO_REGISTRO_PUBLICADO
    en_revision = Arbol.objects.get(codigo="S02-D002")
    assert en_revision.estado_registro == ESTADO_REGISTRO_EN_REVISION
    assert "Tipo de individuo" in en_revision.motivos_revision


CASOS_DE_RECHAZO = {
    "demo_falso": (_con("demo", False), "demo"),
    "demo_texto": (_con("demo", "true"), "demo"),
    "demo_ausente": (lambda: [{**registro(2, 1), "demo": None}], "demo"),
    "codigo_fuera_de_patron": (_con("codigo", "S2-D1"), "patrón"),
    "codigo_sin_letra_demo": (_con("codigo", "S02-A050"), "letra"),
    "fuente_vacia": (_con("fuente", ""), "fuente"),
    "fuente_solo_espacios": (_con("fuente", "   "), "fuente"),
    "fuente_nula": (_con("fuente", None), "fuente"),
    "foto_url": (_con("foto_url", "https://ejemplo.pe/foto.jpg"), "foto"),
    "foto_miniatura_url": (_con("foto_miniatura_url", "https://ejemplo.pe/mini.jpg"), "foto"),
    "sector_inexistente": (_con("sector", 99), "sector"),
    "tope_superado": (
        lambda: [
            destacado(2, orden)
            for orden in range(
                ORDEN_SIN_CHOQUES, ORDEN_SIN_CHOQUES + TOPE_DESTACADOS_POR_SECTOR + 1
            )
        ],
        "tope",
    ),
    "codigo_repetido": (lambda: [registro(2, 1), registro(2, 1)], "repetido"),
    "codigo_de_un_real": (
        lambda: [registro(2, 1), registro(2, ORDEN_DEL_REAL_CON_LETRA_DEMO)],
        "real",
    ),
    "clave_desconocida": (_con("color_hoja", "verde"), "color_hoja"),
}


@pytest.mark.parametrize("construir, pista", CASOS_DE_RECHAZO.values(), ids=CASOS_DE_RECHAZO)
def test_un_registro_malo_rechaza_el_archivo_entero_sin_tocar_la_bd(
    sectores, tmp_path, construir, pista
):
    crear_real(
        codigo_demo(2, ORDEN_DEL_REAL_CON_LETRA_DEMO), demo=False
    )  # un real que lleva la letra demo
    previos = list(Arbol.objects.values_list("codigo", "uid", "actualizado_en"))

    with pytest.raises(ValueError, match=pista):
        cargar_demo(escribir(tmp_path, construir()))

    assert list(Arbol.objects.values_list("codigo", "uid", "actualizado_en")) == previos


def test_el_tope_cuenta_los_destacados_que_ya_hay_en_la_bd(sectores, tmp_path):
    cargar_demo(escribir(tmp_path, [destacado(2, 1)]))
    nuevos = [destacado(2, orden) for orden in range(2, TOPE_DESTACADOS_POR_SECTOR + 2)]

    with pytest.raises(ValueError, match="tope"):
        cargar_demo(escribir(tmp_path, nuevos))

    assert Arbol.objects.count() == 1


def test_el_mensaje_junta_todos_los_errores_con_su_codigo_o_indice(sectores, tmp_path):
    registros = [
        registro(2, 1, fuente=""),
        registro(2, 2, foto_url="https://ejemplo.pe/f.jpg"),
        registro(2, 3, sector=99),
    ]

    with pytest.raises(ValueError) as error:
        cargar_demo(escribir(tmp_path, registros))

    mensaje = str(error.value)
    for codigo in ("S02-D001", "S02-D002", "S02-D003"):
        assert codigo in mensaje
    assert Arbol.objects.count() == 0


def test_sin_codigo_el_error_nombra_el_indice_del_registro(sectores, tmp_path):
    registros = [registro(2, 1), {**registro(2, 2), "codigo": None}]

    with pytest.raises(ValueError, match="registro 2"):
        cargar_demo(escribir(tmp_path, registros))


def test_un_fallo_a_mitad_de_la_escritura_revierte_todo(sectores, tmp_path, monkeypatch):
    ruta = escribir(tmp_path, [registro(2, 1), registro(2, 2), registro(2, 3)])
    guardados = []
    guardar_original = Arbol.save

    def guardar_y_fallar(self, *args, **kwargs):
        if len(guardados) == 2:
            raise RuntimeError("falla simulada")
        guardados.append(self.codigo)
        guardar_original(self, *args, **kwargs)

    monkeypatch.setattr(Arbol, "save", guardar_y_fallar)

    with pytest.raises(RuntimeError):
        cargar_demo(ruta)

    assert Arbol.objects.count() == 0


@pytest.mark.parametrize(
    "contenido, pista",
    [
        ("no es json", "JSON"),
        ('{"codigo": "S02-D001"}', "lista"),
        ("[1, 2]", "objeto"),
        ("[]", "vacío"),
    ],
)
def test_un_archivo_que_no_sirve_lanza_valueerror(sectores, tmp_path, contenido, pista):
    ruta = tmp_path / "malo.json"
    ruta.write_text(contenido, encoding="utf-8")

    with pytest.raises(ValueError, match=pista):
        cargar_demo(ruta)


def test_un_archivo_inexistente_lanza_valueerror(sectores, tmp_path):
    with pytest.raises(ValueError, match="No existe"):
        cargar_demo(tmp_path / "no-hay.json")


# --- comando -------------------------------------------------------------------------------


def ejecutar(*argumentos):
    salida = StringIO()
    call_command("cargar_demo", *argumentos, stdout=salida)
    return salida.getvalue()


def test_comando_carga_e_imprime_el_reporte(sectores, tmp_path):
    ruta = escribir(tmp_path, [destacado(2, 1), registro(2, 2), registro(3, 1)])

    texto = ejecutar(str(ruta))

    assert Arbol.objects.filter(demo=True).count() == 3
    assert "Árboles creados: 3" in texto
    assert "Árboles actualizados: 0" in texto
    assert "Sector 2: 1" in texto
    assert "Árboles fuera de su sector: 0" in texto
    assert "Árboles actualizados: 3" in ejecutar(str(ruta))


def test_comando_imprime_los_avisos_fuera_de_sector(sectores, tmp_path):
    lat, lon = lat_lon_dentro(3)
    ruta = escribir(tmp_path, [registro(2, 1, lat=lat, lon=lon)])

    texto = ejecutar(str(ruta))

    assert "Árboles fuera de su sector: 1" in texto
    assert "S02-D001 (sector 2)" in texto


def test_comando_borrar_quita_solo_los_simulados(sectores, tmp_path):
    ejecutar(str(escribir(tmp_path, [registro(2, 1), registro(3, 1)])))
    crear_real("S02-A001")

    texto = ejecutar("--borrar")

    assert "2" in texto
    assert list(Arbol.objects.values_list("codigo", flat=True)) == ["S02-A001"]


def test_comando_traduce_el_valueerror_a_commanderror(sectores, tmp_path):
    ruta = escribir(tmp_path, [registro(2, 1, demo=False)])

    with pytest.raises(CommandError, match="demo"):
        ejecutar(str(ruta))
    assert Arbol.objects.count() == 0


def test_comando_exige_ruta_o_borrar_pero_no_ambos(sectores, tmp_path):
    ruta = escribir(tmp_path, [registro(2, 1)])

    with pytest.raises(CommandError):
        ejecutar()
    with pytest.raises(CommandError):
        ejecutar(str(ruta), "--borrar")
    assert Arbol.objects.count() == 0


def test_carga_marca_el_co2_simulado_solo_si_el_ejemplo_trae_co2(sectores, tmp_path):
    ruta = escribir(
        tmp_path,
        [
            registro(2, 1),
            registro(2, 2, co2_almacenado_kg=None, co2_captura_anual_kg=None),
        ],
    )

    cargar_demo(ruta)

    assert Arbol.objects.get(codigo="S02-D001").co2_simulado is True
    assert Arbol.objects.get(codigo="S02-D002").co2_simulado is False
