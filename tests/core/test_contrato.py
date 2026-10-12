"""Tests del contrato `contrato/openapi.yaml` y de sus ejemplos (sin base de datos)."""

import importlib.util
import json
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


def test_la_version_del_contrato_es_la_vigente(contrato):
    assert contrato["info"]["version"] == "0.5.0"


@pytest.mark.parametrize("nombre_schema", ["Arbol", "ArbolResumen"])
def test_el_arbol_exige_uid_y_marca_de_destacado(contrato, nombre_schema):
    requeridos = set(contrato["components"]["schemas"][nombre_schema]["required"])

    assert {"uid", "destacado", "motivo_destacado"} <= requeridos


@pytest.mark.parametrize("nombre_schema", ["Arbol", "ArbolResumen"])
def test_el_uid_es_un_uuid_de_solo_lectura(contrato, nombre_schema):
    propiedad = contrato["components"]["schemas"][nombre_schema]["properties"]["uid"]

    assert propiedad["type"] == "string"
    assert propiedad["format"] == "uuid"
    assert propiedad["readOnly"] is True


@pytest.mark.parametrize("nombre_schema", ["Arbol", "ArbolResumen"])
def test_la_marca_de_destacado_tiene_el_tipo_del_contrato(contrato, nombre_schema):
    propiedades = contrato["components"]["schemas"][nombre_schema]["properties"]

    assert propiedades["destacado"]["type"] == "boolean"
    assert propiedades["motivo_destacado"]["type"] == ["string", "null"]


@pytest.mark.parametrize("nombre_schema", ["Arbol", "ArbolResumen"])
def test_la_descripcion_del_destacado_no_escribe_el_tope(contrato, nombre_schema):
    propiedades = contrato["components"]["schemas"][nombre_schema]["properties"]
    descripciones = [
        propiedades[clave]["description"] for clave in ("destacado", "motivo_destacado")
    ]

    assert not any(caracter.isdigit() for texto in descripciones for caracter in texto)


def test_la_cartilla_exige_las_capsulas_y_la_ficha_pero_no_el_resumen(contrato):
    esquemas = contrato["components"]["schemas"]

    assert {"capsulas", "ficha_especie"} <= set(esquemas["Arbol"]["required"])
    assert not {"capsulas", "ficha_especie"} & set(esquemas["ArbolResumen"]["properties"])


def test_la_capsula_exige_campo_titulo_y_que_es_y_admite_en_este_arbol_nulo(contrato):
    capsula = contrato["components"]["schemas"]["Capsula"]

    assert set(capsula["required"]) == {"campo", "titulo", "que_es", "en_este_arbol"}
    assert capsula["properties"]["en_este_arbol"]["type"] == ["string", "null"]
    assert contrato["components"]["schemas"]["Arbol"]["properties"]["capsulas"]["type"] == "array"


def test_la_ficha_de_especie_exige_sus_claves_y_la_fuente_no_vacia(contrato):
    ficha = contrato["components"]["schemas"]["FichaEspecie"]
    propiedades = ficha["properties"]

    assert set(ficha["required"]) == {
        "nombre_cientifico",
        "nombre_comun",
        "beneficios",
        "dato_curioso",
        "cuidados",
        "fuente",
    }
    assert propiedades["beneficios"]["type"] == "array"
    assert propiedades["beneficios"]["items"]["type"] == "string"
    assert propiedades["dato_curioso"]["type"] == ["string", "null"]
    assert propiedades["cuidados"]["type"] == ["string", "null"]
    assert propiedades["fuente"]["minLength"] == 1


def test_la_ficha_de_la_cartilla_puede_ser_nula(contrato):
    opciones = contrato["components"]["schemas"]["Arbol"]["properties"]["ficha_especie"]["oneOf"]

    assert {"type": "null"} in opciones
    assert {"$ref": "#/components/schemas/FichaEspecie"} in opciones


@pytest.mark.parametrize("archivo", ["arbol-real.json", "arbol-demo.json"])
def test_las_capsulas_de_un_ejemplo_no_repiten_campo(archivo):
    ruta = validar_contrato.CARPETA_EJEMPLOS / archivo
    campos = [capsula["campo"] for capsula in json.loads(ruta.read_text("utf-8"))["capsulas"]]

    assert campos
    assert len(campos) == len(set(campos))


def test_la_cartilla_y_el_resumen_exigen_el_co2_y_su_marca_de_simulado(contrato):
    esquemas = contrato["components"]["schemas"]
    claves_del_co2 = {"co2_almacenado_kg", "co2_captura_anual_kg", "co2_simulado"}

    assert claves_del_co2 <= set(esquemas["Arbol"]["required"])
    assert claves_del_co2 <= set(esquemas["ArbolResumen"]["required"])


@pytest.mark.parametrize("nombre_schema", ["Arbol", "ArbolResumen"])
def test_el_co2_tiene_el_tipo_del_contrato(contrato, nombre_schema):
    propiedades = contrato["components"]["schemas"][nombre_schema]["properties"]

    assert propiedades["co2_simulado"]["type"] == "boolean"
    for clave in ("co2_almacenado_kg", "co2_captura_anual_kg"):
        assert propiedades[clave]["type"] == ["number", "null"]
        assert propiedades[clave]["minimum"] == 0
