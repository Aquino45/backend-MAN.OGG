"""Tests del contrato `contrato/openapi.yaml` y de sus ejemplos (sin base de datos)."""

import importlib.util
from pathlib import Path

import pytest
from jsonschema import ValidationError

CLAVES_DE_LA_CARTILLA_NUEVAS = {
    "identificacion",
    "origen",
    "observaciones",
    "utm_este_m",
    "utm_norte_m",
}
RUTA_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validar_contrato.py"


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


def test_el_yaml_es_openapi_valido(contrato):
    validar_contrato.validar_openapi(contrato)


@pytest.mark.parametrize(("archivo", "nombre_schema"), validar_contrato.EJEMPLOS.items())
def test_cada_ejemplo_cumple_su_schema(contrato, archivo, nombre_schema):
    errores = validar_contrato.errores_de_ejemplos(contrato)[archivo]

    assert errores == [], f"{archivo} no cumple {nombre_schema}"


def test_la_cartilla_exige_las_claves_de_contexto_y_utm_pero_no_el_resumen(contrato):
    esquemas = contrato["components"]["schemas"]

    assert CLAVES_DE_LA_CARTILLA_NUEVAS <= set(esquemas["Arbol"]["required"])
    assert not CLAVES_DE_LA_CARTILLA_NUEVAS & set(esquemas["ArbolResumen"]["required"])


def test_codigo_bien_formado_se_acepta(contrato):
    validador = validar_contrato.validador_de_schema(contrato, "CodigoArbol")

    validador.validate("S01-A001")


def test_codigo_mal_formado_se_rechaza(contrato):
    validador = validar_contrato.validador_de_schema(contrato, "CodigoArbol")

    with pytest.raises(ValidationError):
        validador.validate("S01-A0010")


def _valores_de_external_value(nodo):
    """Recorre el contrato y devuelve todos los valores de `externalValue`."""
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            if clave == "externalValue":
                yield valor
            else:
                yield from _valores_de_external_value(valor)
    elif isinstance(nodo, list):
        for elemento in nodo:
            yield from _valores_de_external_value(elemento)


def test_todo_external_value_esta_en_la_lista_de_ejemplos(contrato):
    archivos_referidos = {Path(valor).name for valor in _valores_de_external_value(contrato)}

    assert archivos_referidos, "el contrato no referencia ningún ejemplo"
    assert archivos_referidos <= set(validar_contrato.EJEMPLOS)
