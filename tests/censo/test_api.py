"""Tests de las 3 rutas del censo con APIClient: forma del contrato, 404, solo lectura y límite."""

import importlib.util
from pathlib import Path

import pytest
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.urls import reverse

from apps.censo.models import Arbol
from apps.core.seguridad import LimiteAnonimo
from config.constantes import DECIMALES_COORDENADAS, DECIMALES_UTM, SRID_UTM_CENSO

RUTA_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validar_contrato.py"
FUENTE_PRUEBA = "Prueba de la API del censo"
SECTOR_INEXISTENTE = 99
CODIGO_INEXISTENTE = "S01-Z999"
CODIGOS_MAL_FORMADOS = ["S01-A0010", "abc"]
METODOS_DE_ESCRITURA = ["post", "put", "patch", "delete"]
LLAVES_DE_ARBOL_EN_EL_CONTRATO = 28
CAMPOS_UTM = ("utm_este_m", "utm_norte_m")
IDENTIFICACION_COMPLETA = "Identificada"
ORIGEN_COMPLETO = "Nativa"
OBSERVACIONES_COMPLETAS = "Junto a la banca"
TASA_BAJA = "2/min"


def _cargar_script():
    """Carga scripts/validar_contrato.py como módulo, igual que tests/core/test_contrato.py."""
    especificacion = importlib.util.spec_from_file_location("validar_contrato", RUTA_SCRIPT)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


validar_contrato = _cargar_script()


@pytest.fixture(autouse=True)
def cache_limpia():
    """El contador del throttling vive en la caché: cada test arranca de cero."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(scope="module")
def contrato():
    return validar_contrato.cargar_contrato()


@pytest.fixture
def cumple_schema(contrato):
    """Devuelve una función que valida un JSON contra un schema del contrato."""

    def validar(documento, nombre_schema):
        validar_contrato.validador_de_schema(contrato, nombre_schema).validate(documento)

    return validar


def crear_arbol(codigo, sector_id=1, ubicacion_utm=None, **extra):
    """Árbol de prueba: siempre con fuente y `demo=True`."""
    ubicacion = Point(*ubicacion_utm, srid=SRID_UTM_CENSO) if ubicacion_utm else None
    return Arbol.objects.create(
        codigo=codigo,
        sector_id=sector_id,
        ubicacion=ubicacion,
        fuente=FUENTE_PRUEBA,
        demo=True,
        **extra,
    )


@pytest.fixture
def arboles_del_sector_1(punto_dentro):
    """Tres árboles del S1 fuera de orden: uno completo, uno sin coordenadas y uno «muerto»."""
    crear_arbol("S01-A003", dap_cm=None)  # «muerto»: sin DAP, especie ni coordenadas
    crear_arbol(
        "S01-A001",
        ubicacion_utm=punto_dentro,
        nombre_comun="Molle",
        nombre_cientifico="Schinus molle",
        dap_cm="35.250",
        altura_total_m="8.500",
        identificacion=IDENTIFICACION_COMPLETA,
        origen=ORIGEN_COMPLETO,
        estado_general="Bueno",
        observaciones=OBSERVACIONES_COMPLETAS,
        brigada="Brigada A",
        foto_archivo="IMG_0001.jpg",
    )
    crear_arbol("S01-A002", nombre_comun="Palma real")


def url_sectores():
    return reverse("sectores")


def url_arboles_de_sector(sector_id):
    return reverse("arboles-de-sector", kwargs={"sector_id": sector_id})


def url_arbol(codigo):
    return reverse("arbol", kwargs={"codigo": codigo})


# --- GET /sectores ---------------------------------------------------------------------------


def test_sectores_200_con_la_forma_del_contrato(cliente_api, sectores, cumple_schema):
    respuesta = cliente_api.get(url_sectores())

    assert respuesta.status_code == 200
    cumple_schema(respuesta.json(), "SectorColeccion")
    assert len(respuesta.json()["features"]) == 5


def test_sectores_ordenados_por_id_y_con_su_total(
    cliente_api, arboles_del_sector_1, django_assert_num_queries
):
    with django_assert_num_queries(1):
        respuesta = cliente_api.get(url_sectores())

    features = respuesta.json()["features"]
    ids = [feature["id"] for feature in features]
    totales = {feature["id"]: feature["properties"]["total_arboles"] for feature in features}
    assert ids == sorted(ids)
    assert totales[1] == 3
    assert totales[2] == 0


def test_sectores_entrega_wgs84_con_los_decimales_del_contrato(cliente_api, sectores):
    features = cliente_api.get(url_sectores()).json()["features"]

    for feature in features:
        for anillo in feature["geometry"]["coordinates"]:
            for longitud, latitud in anillo:
                assert -180 <= longitud <= 180
                assert -90 <= latitud <= 90
                assert longitud == round(longitud, DECIMALES_COORDENADAS)
                assert latitud == round(latitud, DECIMALES_COORDENADAS)


# --- GET /sectores/{sector_id}/arboles -------------------------------------------------------


def test_arboles_de_sector_200_con_la_forma_del_contrato(
    cliente_api, arboles_del_sector_1, cumple_schema
):
    respuesta = cliente_api.get(url_arboles_de_sector(1))

    assert respuesta.status_code == 200
    cumple_schema(respuesta.json(), "ArbolResumenColeccion")
    assert len(respuesta.json()["features"]) == 3


def test_arboles_de_sector_ordenados_por_codigo(cliente_api, arboles_del_sector_1):
    features = cliente_api.get(url_arboles_de_sector(1)).json()["features"]

    assert [feature["id"] for feature in features] == ["S01-A001", "S01-A002", "S01-A003"]


def test_arbol_sin_coordenadas_sale_en_la_lista_con_geometry_null(
    cliente_api, arboles_del_sector_1
):
    features = cliente_api.get(url_arboles_de_sector(1)).json()["features"]
    geometrias = {feature["id"]: feature["geometry"] for feature in features}

    assert geometrias["S01-A001"]["type"] == "Point"
    assert geometrias["S01-A002"] is None
    assert geometrias["S01-A003"] is None


def test_arboles_de_sector_sin_arboles_da_features_vacio(cliente_api, sectores, cumple_schema):
    respuesta = cliente_api.get(url_arboles_de_sector(2))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"type": "FeatureCollection", "features": []}
    cumple_schema(respuesta.json(), "ArbolResumenColeccion")


def test_arboles_de_sector_inexistente_da_404_con_detail(cliente_api, sectores):
    respuesta = cliente_api.get(url_arboles_de_sector(SECTOR_INEXISTENTE))

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "No encontrado."}


def test_resumen_no_expone_campos_fuera_del_contrato(cliente_api, arboles_del_sector_1):
    feature = cliente_api.get(url_arboles_de_sector(1)).json()["features"][0]

    assert set(feature["properties"]) == {
        "codigo",
        "sector",
        "nombre_comun",
        "nombre_cientifico",
        "estado_general",
        "foto_miniatura_url",
        "demo",
    }


# --- GET /arboles/{codigo} -------------------------------------------------------------------


def test_arbol_200_con_la_forma_del_contrato(cliente_api, arboles_del_sector_1, cumple_schema):
    respuesta = cliente_api.get(url_arbol("S01-A001"))
    cartilla = respuesta.json()

    assert respuesta.status_code == 200
    cumple_schema(cartilla, "Arbol")
    assert len(cartilla) == LLAVES_DE_ARBOL_EN_EL_CONTRATO
    assert cartilla["sector"] == 1
    assert cartilla["dap_cm"] == 35.25
    assert cartilla["altura_total_m"] == 8.5
    assert cartilla["demo"] is True
    assert cartilla["fuente"] == FUENTE_PRUEBA
    assert cartilla["foto_url"] is None
    assert cartilla["foto_miniatura_url"] is None


def test_arbol_entrega_lat_y_lon_en_wgs84_dentro_del_campus(cliente_api, arboles_del_sector_1):
    cartilla = cliente_api.get(url_arbol("S01-A001")).json()

    assert -12.1 < cartilla["lat"] < -11.9
    assert -76.9 < cartilla["lon"] < -76.7
    assert cartilla["lat"] == round(cartilla["lat"], DECIMALES_COORDENADAS)
    assert cartilla["lon"] == round(cartilla["lon"], DECIMALES_COORDENADAS)


def test_arbol_no_expone_campos_fuera_del_contrato(cliente_api, arboles_del_sector_1):
    cartilla = cliente_api.get(url_arbol("S01-A001")).json()

    for campo in ("brigada", "foto_archivo", "ubicacion", "fila_origen"):
        assert campo not in cartilla


def test_arbol_entrega_contexto_de_campo_y_utm_guardadas(
    cliente_api, arboles_del_sector_1, punto_dentro
):
    cartilla = cliente_api.get(url_arbol("S01-A001")).json()

    assert cartilla["identificacion"] == IDENTIFICACION_COMPLETA
    assert cartilla["origen"] == ORIGEN_COMPLETO
    assert cartilla["observaciones"] == OBSERVACIONES_COMPLETAS
    este_guardado, norte_guardado = punto_dentro
    tolerancia_metros = 10**-DECIMALES_UTM
    assert cartilla["utm_este_m"] == pytest.approx(este_guardado, abs=tolerancia_metros)
    assert cartilla["utm_norte_m"] == pytest.approx(norte_guardado, abs=tolerancia_metros)


def test_arbol_sin_ubicacion_ni_contexto_trae_las_claves_nuevas_en_null(
    cliente_api, arboles_del_sector_1, cumple_schema
):
    cartilla = cliente_api.get(url_arbol("S01-A003")).json()

    cumple_schema(cartilla, "Arbol")
    for campo in ("identificacion", "origen", "observaciones", *CAMPOS_UTM):
        assert campo in cartilla
        assert cartilla[campo] is None


def test_arbol_sin_dato_sale_en_null_y_no_se_inventa(cliente_api, arboles_del_sector_1):
    cartilla = cliente_api.get(url_arbol("S01-A003")).json()

    assert cartilla["lat"] is None
    assert cartilla["lon"] is None
    assert cartilla["dap_cm"] is None
    assert cartilla["nombre_comun"] is None
    assert cartilla["fecha_registro"] is None


def test_arbol_inexistente_da_404_con_detail(cliente_api, sectores):
    respuesta = cliente_api.get(url_arbol(CODIGO_INEXISTENTE))

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "No encontrado."}


@pytest.mark.parametrize("codigo", CODIGOS_MAL_FORMADOS)
def test_codigo_mal_formado_da_404_sin_tocar_la_bd(
    cliente_api, sectores, codigo, django_assert_num_queries
):
    with django_assert_num_queries(0):
        respuesta = cliente_api.get(url_arbol(codigo))

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "No encontrado."}


# --- Solo lectura y límite de peticiones -----------------------------------------------------


@pytest.mark.parametrize("metodo", METODOS_DE_ESCRITURA)
@pytest.mark.parametrize(
    "url",
    [
        pytest.param(lambda: url_sectores(), id="sectores"),
        pytest.param(lambda: url_arboles_de_sector(1), id="arboles-de-sector"),
        pytest.param(lambda: url_arbol("S01-A001"), id="arbol"),
    ],
)
def test_escritura_se_rechaza_con_detail(cliente_api, sectores, url, metodo):
    respuesta = getattr(cliente_api, metodo)(url(), {}, format="json")

    assert respuesta.status_code in (403, 405)
    assert list(respuesta.json()) == ["detail"]


def test_el_limite_anonimo_esta_en_los_throttles_por_defecto():
    from rest_framework.settings import api_settings

    assert LimiteAnonimo in api_settings.DEFAULT_THROTTLE_CLASSES


def test_pasado_el_limite_una_ruta_del_censo_responde_429(monkeypatch, cliente_api, sectores):
    monkeypatch.setattr(LimiteAnonimo, "THROTTLE_RATES", {LimiteAnonimo.scope: TASA_BAJA})

    codigos = [cliente_api.get(url_sectores()).status_code for _ in range(2)]
    tercera = cliente_api.get(url_sectores())

    assert codigos == [200, 200]
    assert tercera.status_code == 429
    assert list(tercera.json()) == ["detail"]
