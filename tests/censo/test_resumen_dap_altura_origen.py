"""La lista de árboles de un sector trae DAP, altura y origen iguales a los de la cartilla."""

import importlib.util
from pathlib import Path

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.censo.models import Arbol
from config.constantes import VALOR_TIPO_JUVENIL
from tests.censo.conftest import arbol_de_ejemplo

RUTA_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validar_contrato.py"
CAMPOS_DEL_RESUMEN = ("dap_cm", "altura_total_m", "origen")
ORIGEN_DE_LA_PLANILLA = "Introducida / exótica"
CANTIDAD_BASE = 3


def _cargar_script():
    especificacion = importlib.util.spec_from_file_location("validar_contrato", RUTA_SCRIPT)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


validar_contrato = _cargar_script()


def _lista_del_sector(cliente_api, sector_id=1):
    return cliente_api.get(reverse("arboles-de-sector", kwargs={"sector_id": sector_id}))


def _cartilla(cliente_api, codigo):
    return cliente_api.get(reverse("arbol", kwargs={"codigo": codigo})).json()


@pytest.fixture
def arboles_variados(sectores):
    """Un árbol completo, un juvenil sin DAP, uno exótico y uno con origen de la planilla."""
    arbol_de_ejemplo("S01-A001")
    arbol_de_ejemplo("S01-A002", dap_cm=None, tipo_individuo=VALOR_TIPO_JUVENIL)
    arbol_de_ejemplo("S01-A003", origen="Introducida / exótica")
    de_la_planilla = arbol_de_ejemplo("S01-A004")
    de_la_planilla.especie.origen = None
    de_la_planilla.especie.save()
    de_la_planilla.valores_originales = {"origen": ORIGEN_DE_LA_PLANILLA}
    Arbol.objects.filter(pk=de_la_planilla.pk).update(
        valores_originales=de_la_planilla.valores_originales
    )


def test_la_lista_valida_contra_el_contrato(cliente_api, arboles_variados):
    contrato = validar_contrato.cargar_contrato()

    respuesta = _lista_del_sector(cliente_api)

    assert respuesta.status_code == 200
    validar_contrato.validador_de_schema(contrato, "ArbolResumenColeccion").validate(
        respuesta.json()
    )


def test_cada_arbol_de_la_lista_iguala_su_cartilla(cliente_api, arboles_variados):
    features = _lista_del_sector(cliente_api).json()["features"]

    assert len(features) == 4
    for feature in features:
        cartilla = _cartilla(cliente_api, feature["id"])
        for campo in CAMPOS_DEL_RESUMEN:
            assert feature["properties"][campo] == cartilla[campo], (feature["id"], campo)


def test_los_casos_null_y_los_origenes_llegan_a_la_lista(cliente_api, arboles_variados):
    por_codigo = {
        f["id"]: f["properties"] for f in _lista_del_sector(cliente_api).json()["features"]
    }

    assert por_codigo["S01-A001"]["dap_cm"] == 35.25
    assert por_codigo["S01-A001"]["altura_total_m"] == 8.5
    assert por_codigo["S01-A002"]["dap_cm"] is None
    assert por_codigo["S01-A002"]["altura_total_m"] == 8.5
    assert por_codigo["S01-A003"]["origen"] == ORIGEN_DE_LA_PLANILLA
    assert por_codigo["S01-A001"]["origen"] == "Nativa"
    assert por_codigo["S01-A004"]["origen"] == ORIGEN_DE_LA_PLANILLA


def _consultas_de_la_lista(cliente_api):
    with CaptureQueriesContext(connection) as consultas:
        assert _lista_del_sector(cliente_api).status_code == 200
    return len(consultas)


def test_las_consultas_de_la_lista_no_crecen_con_los_arboles(cliente_api, sectores):
    for numero in range(1, CANTIDAD_BASE + 1):
        arbol_de_ejemplo(f"S01-A{numero:03d}")
    con_n = _consultas_de_la_lista(cliente_api)

    for numero in range(CANTIDAD_BASE + 1, 2 * CANTIDAD_BASE + 1):
        arbol_de_ejemplo(f"S01-A{numero:03d}")
    con_2n = _consultas_de_la_lista(cliente_api)

    assert con_2n == con_n
