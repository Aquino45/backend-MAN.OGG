"""Tests de los serializers del censo: la salida debe ser la forma exacta del contrato.

Cada salida se valida contra su schema de `contrato/openapi.yaml` (con el mismo validador de
`scripts/validar_contrato.py`) y se comprueban aparte las reglas que el schema no cubre.
"""

import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.gis.geos import Point

from apps.censo import selectores
from apps.censo.api.serializers import (
    ArbolResumenColeccionSerializer,
    ArbolSerializer,
    SectorColeccionSerializer,
)
from apps.censo.models import Arbol, Sector
from config.constantes import DECIMALES_COORDENADAS, SRID_UTM_CENSO

RUTA_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validar_contrato.py"
FUENTE_PRUEBA = "Prueba de serializers"
LONGITUD_CAMPUS = -76.8
LATITUD_CAMPUS = -12.0
TOLERANCIA_GRADOS = 0.2
CODIGO_COMPLETO = "S01-A001"
CODIGO_MUERTO = "S01-A002"
CAMPOS_DE_MEDIDA = ("altura_total_m", "dap_cm", "copa_ns_m", "copa_eo_m")
CAMPOS_DE_CO2 = ("co2_almacenado_kg", "co2_captura_anual_kg")
CAMPOS_DE_TEXTO = ("nombre_comun", "nombre_cientifico", "condicion_conservacion")
CAMPOS_DE_ESTADO = ("estado_general", "estado_copa", "tronco_danos", "raices_base")
FUERA_DEL_CONTRATO = ("observaciones", "brigada", "foto_archivo", "ubicacion")
MEDIDAS_COMPLETAS = {
    "altura_total_m": Decimal("8.500"),
    "dap_cm": Decimal("35.250"),
    "copa_ns_m": Decimal("4.500"),
    "copa_eo_m": Decimal("5.000"),
    "co2_almacenado_kg": Decimal("120.500"),
    "co2_captura_anual_kg": Decimal("10.250"),
}


def _cargar_script():
    """Carga scripts/validar_contrato.py como módulo."""
    especificacion = importlib.util.spec_from_file_location("validar_contrato", RUTA_SCRIPT)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


validar_contrato = _cargar_script()


@pytest.fixture(scope="module")
def contrato():
    return validar_contrato.cargar_contrato()


def validar(contrato, nombre_schema, documento):
    """Falla con todos los errores si `documento` no cumple el schema."""
    validador = validar_contrato.validador_de_schema(contrato, nombre_schema)
    errores = [
        f"{'/'.join(str(parte) for parte in error.path) or '(raíz)'}: {error.message}"
        for error in validador.iter_errors(documento)
    ]
    assert errores == [], f"no cumple {nombre_schema}: {errores}"


def requeridas(contrato, nombre_schema):
    """Las claves `required` del schema, leídas del contrato cargado."""
    return set(contrato["components"]["schemas"][nombre_schema]["required"])


def decimales(numero):
    return -Decimal(repr(numero)).as_tuple().exponent


def es_numero(valor):
    return type(valor) in (int, float)


def crear_arbol(codigo, ubicacion=None, **extra):
    """Árbol de prueba: siempre con fuente y `demo=True`."""
    extra.setdefault("fuente", FUENTE_PRUEBA)
    return Arbol.objects.create(codigo=codigo, sector_id=1, ubicacion=ubicacion, demo=True, **extra)


@pytest.fixture
def arbol_completo(punto_dentro):
    return crear_arbol(
        CODIGO_COMPLETO,
        ubicacion=Point(*punto_dentro, srid=SRID_UTM_CENSO),
        fecha_registro=date(2026, 10, 7),
        brigada="Brigada A",
        nombre_comun="Molle",
        nombre_cientifico="Schinus molle",
        condicion_conservacion="Sin categoría",
        **MEDIDAS_COMPLETAS,
        estado_general="Bueno",
        estado_copa="Completa",
        tronco_danos="Sin daños",
        raices_base="Sanas",
        interferencia_entorno="Ninguna",
        foto_archivo="IMG_0001.jpg",
        observaciones="Junto a la banca",
    )


@pytest.fixture
def arbol_muerto(sectores):
    """Como los 36 del S01: sin DAP, sin especie, sin ubicación."""
    return crear_arbol(
        CODIGO_MUERTO,
        brigada="Brigada A",
        observaciones="DAP en planilla: muerto",
        fuente="Planilla de campo, fila 3",
    )


def cartilla(codigo):
    return ArbolSerializer(selectores.arbol_por_codigo(codigo)).data


def lista_del_sector(sector_id=1):
    return ArbolResumenColeccionSerializer(selectores.arboles_de_sector(sector_id)).data


def test_cartilla_completa_cumple_el_schema(contrato, arbol_completo):
    validar(contrato, "Arbol", cartilla(CODIGO_COMPLETO))


def test_cartilla_trae_exactamente_los_campos_del_contrato(contrato, arbol_completo):
    datos = cartilla(CODIGO_COMPLETO)

    assert set(datos) == requeridas(contrato, "Arbol")
    assert not set(FUERA_DEL_CONTRATO) & set(datos)


def test_cartilla_completa_entrega_textos_y_banderas(arbol_completo):
    datos = cartilla(CODIGO_COMPLETO)

    assert (datos["codigo"], datos["sector"]) == (CODIGO_COMPLETO, 1)
    assert (datos["nombre_cientifico"], datos["estado_copa"]) == ("Schinus molle", "Completa")
    assert (datos["fuente"], datos["demo"]) == (FUENTE_PRUEBA, True)
    assert datos["fecha_registro"] == "2026-10-07"
    assert datos["foto_url"] is None
    assert datos["foto_miniatura_url"] is None


def test_cartilla_numeros_como_numeros_y_lat_lon_en_wgs84(arbol_completo):
    datos = cartilla(CODIGO_COMPLETO)

    for campo in (*CAMPOS_DE_MEDIDA, *CAMPOS_DE_CO2, "lat", "lon"):
        assert es_numero(datos[campo]), f"{campo} no es número: {datos[campo]!r}"
    assert (datos["dap_cm"], datos["co2_almacenado_kg"]) == (35.25, 120.5)
    assert datos["lon"] == pytest.approx(LONGITUD_CAMPUS, abs=TOLERANCIA_GRADOS)
    assert datos["lat"] == pytest.approx(LATITUD_CAMPUS, abs=TOLERANCIA_GRADOS)
    assert decimales(datos["lat"]) <= DECIMALES_COORDENADAS
    assert decimales(datos["lon"]) <= DECIMALES_COORDENADAS


def test_cartilla_de_arbol_muerto_va_con_todo_en_null(contrato, arbol_muerto):
    datos = cartilla(CODIGO_MUERTO)

    validar(contrato, "Arbol", datos)
    assert set(datos) == requeridas(contrato, "Arbol")
    sin_dato = (*CAMPOS_DE_MEDIDA, *CAMPOS_DE_CO2, *CAMPOS_DE_TEXTO, *CAMPOS_DE_ESTADO)
    for campo in (*sin_dato, "interferencia_entorno", "lat", "lon", "fecha_registro", "foto_url"):
        assert datos[campo] is None, f"{campo} debía ser null: {datos[campo]!r}"
    assert datos["foto_miniatura_url"] is None
    assert (datos["fuente"], datos["demo"]) == ("Planilla de campo, fila 3", True)


def test_lista_cumple_el_schema_y_sus_claves(contrato, arbol_completo, arbol_muerto):
    datos = lista_del_sector()

    validar(contrato, "ArbolResumenColeccion", datos)
    assert set(datos) == requeridas(contrato, "ArbolResumenColeccion")
    assert datos["type"] == "FeatureCollection"
    for feature in datos["features"]:
        assert set(feature) == requeridas(contrato, "ArbolResumenFeature")
        assert set(feature["properties"]) == requeridas(contrato, "ArbolResumen")
        assert not set(FUERA_DEL_CONTRATO) & set(feature["properties"])


def test_lista_va_ordenada_por_codigo_con_id_igual_al_codigo(arbol_completo, arbol_muerto):
    features = lista_del_sector()["features"]

    assert [feature["id"] for feature in features] == [CODIGO_COMPLETO, CODIGO_MUERTO]
    for feature in features:
        assert feature["id"] == feature["properties"]["codigo"]


def test_lista_punto_es_lon_lat_igual_a_la_cartilla(arbol_completo):
    feature = lista_del_sector()["features"][0]
    datos = cartilla(CODIGO_COMPLETO)

    assert feature["geometry"]["type"] == "Point"
    assert feature["geometry"]["coordinates"] == [datos["lon"], datos["lat"]]
    for coordenada in feature["geometry"]["coordinates"]:
        assert es_numero(coordenada)
        assert decimales(coordenada) <= DECIMALES_COORDENADAS


def test_lista_resumen_lleva_textos_y_sin_foto(arbol_completo):
    propiedades = lista_del_sector()["features"][0]["properties"]

    assert propiedades["nombre_comun"] == "Molle"
    assert propiedades["nombre_cientifico"] == "Schinus molle"
    assert propiedades["estado_general"] == "Bueno"
    assert propiedades["foto_miniatura_url"] is None
    assert (propiedades["sector"], propiedades["demo"]) == (1, True)


def test_lista_arbol_muerto_sin_geometria_y_textos_null(contrato, arbol_muerto):
    feature = lista_del_sector()["features"][0]

    validar(contrato, "ArbolResumenColeccion", lista_del_sector())
    assert feature["geometry"] is None
    assert feature["properties"]["nombre_comun"] is None
    assert feature["properties"]["estado_general"] is None


def test_lista_de_sector_sin_arboles_es_coleccion_vacia(contrato, sectores):
    datos = lista_del_sector(sector_id=2)

    validar(contrato, "ArbolResumenColeccion", datos)
    assert datos == {"type": "FeatureCollection", "features": []}


def sectores_serializados():
    return SectorColeccionSerializer(selectores.sectores_con_total()).data


def test_sectores_cumplen_el_schema_y_sus_claves(contrato, sectores):
    datos = sectores_serializados()

    validar(contrato, "SectorColeccion", datos)
    assert set(datos) == requeridas(contrato, "SectorColeccion")
    assert datos["type"] == "FeatureCollection"
    for feature in datos["features"]:
        assert set(feature) == requeridas(contrato, "SectorFeature")
        assert set(feature["properties"]) == requeridas(contrato, "SectorPropiedades")
        assert feature["geometry"]["type"] == "Polygon"


def test_sectores_son_los_de_la_bd_ordenados_por_id(sectores):
    features = sectores_serializados()["features"]
    ids_esperados = list(Sector.objects.order_by("id").values_list("id", flat=True))

    assert len(ids_esperados) == 5
    assert [feature["id"] for feature in features] == ids_esperados
    for feature in features:
        assert feature["id"] == feature["properties"]["id"]


def test_sectores_total_arboles_cuenta_lo_que_hay_en_la_bd(arbol_completo, arbol_muerto):
    totales = {
        feature["id"]: feature["properties"]["total_arboles"]
        for feature in sectores_serializados()["features"]
    }

    assert totales == {1: 2, 2: 0, 3: 0, 4: 0, 5: 0}


def test_sectores_poligono_en_wgs84_con_seis_decimales_como_maximo(sectores):
    for feature in sectores_serializados()["features"]:
        for anillo in feature["geometry"]["coordinates"]:
            for longitud, latitud in anillo:
                assert longitud == pytest.approx(LONGITUD_CAMPUS, abs=TOLERANCIA_GRADOS)
                assert latitud == pytest.approx(LATITUD_CAMPUS, abs=TOLERANCIA_GRADOS)
                assert decimales(longitud) <= DECIMALES_COORDENADAS
                assert decimales(latitud) <= DECIMALES_COORDENADAS


def test_color_null_es_valido_y_un_color_puesto_se_entrega_tal_cual(contrato, sectores):
    sin_color = sectores_serializados()
    Sector.objects.filter(id=2).update(color="copa-carmin")
    con_color = sectores_serializados()

    validar(contrato, "SectorColeccion", sin_color)
    validar(contrato, "SectorColeccion", con_color)
    assert [f["properties"]["color"] for f in sin_color["features"]] == [None] * 5
    assert [f["properties"]["color"] for f in con_color["features"]] == [None, "copa-carmin"] + [
        None
    ] * 3
