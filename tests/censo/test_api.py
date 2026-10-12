"""Tests de las 3 rutas del censo con APIClient: forma del contrato, 404, solo lectura y límite."""

import importlib.util
import json
from pathlib import Path

import pytest
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.urls import reverse

from apps.censo.models import Arbol, Especie
from apps.censo.servicios.calidad_registro import aplicar
from apps.censo.servicios.capsulas import cargar_capsulas
from apps.core.seguridad import LimiteAnonimo
from config.constantes.general import DECIMALES_COORDENADAS, DECIMALES_UTM, SRID_UTM_CENSO
from tests.censo.conftest import arbol_evaluado

RUTA_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validar_contrato.py"
FUENTE_PRUEBA = "Prueba de la API del censo"
SECTOR_INEXISTENTE = 99
CODIGO_INEXISTENTE = "S01-Z999"
CODIGOS_MAL_FORMADOS = ["S01-A0010", "abc"]
METODOS_DE_ESCRITURA = ["post", "put", "patch", "delete"]
LLAVES_DE_ARBOL_EN_EL_CONTRATO = 34
CAMPOS_UTM = ("utm_este_m", "utm_norte_m")
IDENTIFICACION_COMPLETA = "Identificada"
ORIGEN_COMPLETO = "Nativa"
OBSERVACIONES_COMPLETAS = "Junto a la banca"
TASA_BAJA = "2/min"
MOTIVO_DESTACADO = "Ejemplar de mayor copa del sector"
RUTA_CAPSULAS = Path(__file__).resolve().parents[2] / "datos" / "capsulas" / "capsulas-v0.json"
TOTAL_DE_AYUDAS_DEL_ARCHIVO = 18


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
    """Árbol de prueba completo y publicado: `demo=True`, sin brigada y con fuente."""
    if ubicacion_utm:
        extra["ubicacion"] = Point(*ubicacion_utm, srid=SRID_UTM_CENSO)
    extra.setdefault("brigada", None)
    extra.setdefault("fuente", FUENTE_PRUEBA)
    return arbol_evaluado(codigo, sector_id, demo=True, **extra)


@pytest.fixture
def arboles_del_sector_1(punto_dentro):
    """Tres árboles publicados del S1 fuera de orden y uno en revisión (que no debe salir)."""
    crear_arbol(
        "S01-A003",
        observaciones=None,
        fecha_registro=None,
        condicion_conservacion=None,
        foto_archivo=None,
    )  # solo con los opcionales vacíos: se publica
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
    crear_arbol("S01-A002", nombre_comun="Palma real", nombre_cientifico="Roystonea regia")
    crear_arbol("S01-A009", dap_cm=None, nombre_comun=None)  # «muerto»: queda en revisión


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


def test_arbol_en_revision_no_sale_en_la_lista(cliente_api, arboles_del_sector_1):
    features = cliente_api.get(url_arboles_de_sector(1)).json()["features"]

    assert "S01-A009" not in [feature["id"] for feature in features]
    assert all(feature["geometry"]["type"] == "Point" for feature in features)


def test_arbol_en_revision_da_404_en_la_cartilla(cliente_api, arboles_del_sector_1):
    respuesta = cliente_api.get(url_arbol("S01-A009"))

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "No encontrado."}


def test_arbol_en_revision_no_cuenta_en_el_total_del_sector(cliente_api, arboles_del_sector_1):
    features = cliente_api.get(url_sectores()).json()["features"]
    totales = {feature["id"]: feature["properties"]["total_arboles"] for feature in features}

    assert totales[1] == 3


def test_al_corregir_un_arbol_en_revision_empieza_a_salir(cliente_api, arboles_del_sector_1):
    arbol = Arbol.objects.get(codigo="S01-A009")
    arbol.nombre_comun, arbol.dap_cm = "Molle", 20
    aplicar(arbol)
    arbol.save()

    assert cliente_api.get(url_arbol("S01-A009")).status_code == 200


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
        "uid",
        "sector",
        "nombre_comun",
        "nombre_cientifico",
        "origen",
        "altura_total_m",
        "dap_cm",
        "estado_general",
        "foto_miniatura_url",
        "demo",
        "destacado",
        "motivo_destacado",
        "co2_almacenado_kg",
        "co2_captura_anual_kg",
        "co2_simulado",
    }


# --- GET /arboles/{codigo} -------------------------------------------------------------------


def explicacion_del_catalogo(campo, valor):
    """La explicación tal como está en el archivo de cápsulas (la fuente de la carga)."""
    valores = json.loads(RUTA_CAPSULAS.read_text(encoding="utf-8"))["valores"]
    return next(v["explicacion"] for v in valores if (v["campo"], v["valor"]) == (campo, valor))


def test_la_cartilla_cumple_el_contrato_con_capsulas_y_ficha_reales(
    cliente_api, arboles_del_sector_1, cumple_schema
):
    cargar_capsulas(RUTA_CAPSULAS)
    Especie.objects.filter(nombre_cientifico="Schinus molle").update(ficha_publicada=True)

    cartilla = cliente_api.get(url_arbol("S01-A001")).json()
    sin_ficha = cliente_api.get(url_arbol("S01-A002")).json()

    cumple_schema(cartilla, "Arbol")
    cumple_schema(sin_ficha, "Arbol")
    assert len(cartilla) == LLAVES_DE_ARBOL_EN_EL_CONTRATO
    assert len(cartilla["capsulas"]) == TOTAL_DE_AYUDAS_DEL_ARCHIVO
    por_campo = {c["campo"]: c["en_este_arbol"] for c in cartilla["capsulas"]}
    assert por_campo["estado_general"] == explicacion_del_catalogo("estado_general", "Bueno")
    assert por_campo["origen"] == explicacion_del_catalogo("origen", "Nativa")
    assert por_campo["estado_copa"] == explicacion_del_catalogo("estado_copa", "Buena")
    assert cartilla["ficha_especie"]["nombre_cientifico"] == "Schinus molle"
    assert cartilla["ficha_especie"]["fuente"]
    assert sin_ficha["ficha_especie"] is None


def test_arbol_200_con_la_forma_del_contrato(cliente_api, arboles_del_sector_1, cumple_schema):
    respuesta = cliente_api.get(url_arbol("S01-A001"))
    cartilla = respuesta.json()

    assert respuesta.status_code == 200
    cumple_schema(cartilla, "Arbol")
    assert len(cartilla) == LLAVES_DE_ARBOL_EN_EL_CONTRATO
    assert cartilla["capsulas"] == []
    assert cartilla["ficha_especie"] is None
    assert cartilla["sector"] == 1
    assert cartilla["dap_cm"] == 35.25
    assert cartilla["altura_total_m"] == 8.5
    assert cartilla["demo"] is True
    assert cartilla["fuente"] == FUENTE_PRUEBA
    assert cartilla["foto_url"] is None
    assert cartilla["foto_miniatura_url"] is None


def test_lista_trae_el_co2_y_su_marca_sin_sumar_consultas(
    cliente_api, arboles_del_sector_1, django_assert_max_num_queries, cumple_schema
):
    with django_assert_max_num_queries(2):
        respuesta = cliente_api.get(url_arboles_de_sector(1))

    cumple_schema(respuesta.json(), "ArbolResumenColeccion")
    for feature in respuesta.json()["features"]:
        propiedades = feature["properties"]
        assert propiedades["co2_almacenado_kg"] == 120.5
        assert propiedades["co2_captura_anual_kg"] == 10.25
        assert propiedades["co2_simulado"] is True


def test_la_cartilla_trae_la_marca_de_co2_simulado(cliente_api, arboles_del_sector_1):
    cartilla = cliente_api.get(url_arbol("S01-A001")).json()

    assert cartilla["co2_simulado"] is True
    assert cartilla["co2_almacenado_kg"] == 120.5


def test_arbol_trae_uid_y_destacado_en_la_cartilla(cliente_api, arboles_del_sector_1):
    Arbol.objects.filter(codigo="S01-A001").update(
        destacado=True, motivo_destacado=MOTIVO_DESTACADO
    )

    cartilla = cliente_api.get(url_arbol("S01-A001")).json()

    assert cartilla["uid"] == str(Arbol.objects.get(codigo="S01-A001").uid)
    assert (cartilla["destacado"], cartilla["motivo_destacado"]) == (True, MOTIVO_DESTACADO)
    assert cliente_api.get(url_arbol("S01-A002")).json()["destacado"] is False


def test_lista_trae_uid_y_destacado_sin_consultas_extra(
    cliente_api, arboles_del_sector_1, django_assert_num_queries
):
    Arbol.objects.filter(codigo="S01-A001").update(
        destacado=True, motivo_destacado=MOTIVO_DESTACADO
    )

    with django_assert_num_queries(2):
        respuesta = cliente_api.get(url_arboles_de_sector(1))

    propiedades = {f["id"]: f["properties"] for f in respuesta.json()["features"]}
    assert propiedades["S01-A001"]["destacado"] is True
    assert propiedades["S01-A001"]["motivo_destacado"] == MOTIVO_DESTACADO
    assert propiedades["S01-A002"]["destacado"] is False
    assert propiedades["S01-A002"]["motivo_destacado"] is None
    uids = [p["uid"] for p in propiedades.values()]
    assert len(set(uids)) == len(uids) == 3


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


def test_arbol_con_los_opcionales_vacios_trae_las_claves_en_null(
    cliente_api, arboles_del_sector_1, cumple_schema
):
    cartilla = cliente_api.get(url_arbol("S01-A003")).json()

    cumple_schema(cartilla, "Arbol")
    for campo in ("observaciones", "fecha_registro", "condicion_conservacion", "foto_url"):
        assert campo in cartilla
        assert cartilla[campo] is None
    for campo in CAMPOS_UTM:
        assert cartilla[campo] is not None


def test_arbol_sin_dato_opcional_sale_en_null_y_no_se_inventa(cliente_api, arboles_del_sector_1):
    cartilla = cliente_api.get(url_arbol("S01-A003")).json()

    assert cartilla["fecha_registro"] is None
    assert cartilla["observaciones"] is None
    assert cartilla["condicion_conservacion"] is None


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
