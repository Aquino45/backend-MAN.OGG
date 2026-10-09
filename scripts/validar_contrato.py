"""Valida `contrato/openapi.yaml` y sus ejemplos.

Comprueba que el YAML es OpenAPI 3.1 válido y que cada ejemplo cumple el schema que le toca
(JSON Schema Draft 2020-12). Sale con código 1 si algo falla.
"""

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

CARPETA_CONTRATO = Path(__file__).resolve().parent.parent / "contrato"
RUTA_CONTRATO = CARPETA_CONTRATO / "openapi.yaml"
CARPETA_EJEMPLOS = CARPETA_CONTRATO / "ejemplos"
URI_CONTRATO = "urn:manogg:contrato"

# Cada ejemplo con el schema de `components/schemas` contra el que se valida.
EJEMPLOS = {
    "sectores.json": "SectorColeccion",
    "sector-1-arboles.json": "ArbolResumenColeccion",
    "arbol-real.json": "Arbol",
    "arbol-demo.json": "Arbol",
}


def cargar_contrato():
    """Lee `contrato/openapi.yaml` y lo devuelve como diccionario."""
    with RUTA_CONTRATO.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo)


def validar_openapi(contrato):
    """Lanza una excepción si el contrato no es un OpenAPI válido."""
    validate(contrato)


def validador_de_schema(contrato, nombre_schema):
    """Arma el validador de un schema de `components/schemas`.

    El contrato entero se registra como recurso para que se resuelvan los `$ref` internos
    (`#/components/schemas/...`).
    """
    recurso = Resource.from_contents(contrato, default_specification=DRAFT202012)
    registro = Registry().with_resource(URI_CONTRATO, recurso)
    referencia = {"$ref": f"{URI_CONTRATO}#/components/schemas/{nombre_schema}"}
    return Draft202012Validator(
        referencia,
        registry=registro,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def errores_de_ejemplos(contrato):
    """Devuelve `{archivo: [mensajes]}` con los errores de cada ejemplo (vacío si todo cumple)."""
    errores_por_ejemplo = {}
    for archivo, nombre_schema in EJEMPLOS.items():
        with (CARPETA_EJEMPLOS / archivo).open(encoding="utf-8") as ejemplo:
            documento = json.load(ejemplo)
        validador = validador_de_schema(contrato, nombre_schema)
        errores = sorted(validador.iter_errors(documento), key=lambda error: list(error.path))
        errores_por_ejemplo[archivo] = [
            f"{'/'.join(str(parte) for parte in error.path) or '(raíz)'}: {error.message}"
            for error in errores
        ]
    return errores_por_ejemplo


def main():
    """Valida el contrato y los ejemplos; devuelve 0 si todo está bien y 1 si algo falla."""
    contrato = cargar_contrato()
    try:
        validar_openapi(contrato)
    except Exception as error:
        print(f"ERROR contrato/openapi.yaml: {error}")
        return 1
    print("OK contrato/openapi.yaml (OpenAPI 3.1)")

    hubo_errores = False
    for archivo, errores in errores_de_ejemplos(contrato).items():
        if errores:
            hubo_errores = True
            print(f"ERROR ejemplos/{archivo} → {EJEMPLOS[archivo]}")
            for mensaje in errores:
                print(f"  - {mensaje}")
        else:
            print(f"OK ejemplos/{archivo} → {EJEMPLOS[archivo]}")
    return 1 if hubo_errores else 0


if __name__ == "__main__":
    sys.exit(main())
