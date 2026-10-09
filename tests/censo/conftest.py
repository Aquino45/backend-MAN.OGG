"""Ayudas compartidas de los tests del censo: planillas de prueba y sectores reales.

Las planillas se arman con openpyxl, como la real: encabezados en la fila 1, código como
fórmula COUNTIF sin valor guardado y listas de catálogo en las validaciones de datos.
Nunca se usa el archivo real.
"""

from pathlib import Path

import pytest
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from apps.censo.models import Sector
from apps.censo.servicios.importar_sectores import importar_sectores
from config.constantes import COLUMNAS_PLANILLA, HOJA_PLANILLA

RUTA_GEOJSON = (
    Path(__file__).resolve().parents[2] / "datos" / "sectores" / "sectores-utm18s-v0.geojson"
)
CATALOGOS = {
    "estado_general": "Bueno,Regular,Malo",
    "estado_copa": "Completa,Parcial,Escasa",
    "origen": "Nativa,Introducida",
}
FILAS_CON_VALIDACION = 3000
NOMBRE_ARCHIVO = "arb-prueba.xlsx"
FORMULA_CODIGO = '=IF(B{n}="","","S"&TEXT(B{n},"00")&"-A"&TEXT(COUNTIF(B$2:B{n},B{n}),"000"))'

# Valores de una fila completa (nombres de campo del modelo), usados por el test de fila completa.
TEXTOS_FILA_COMPLETA = {
    "tipo_individuo": "Árbol",
    "nombre_comun": "Molle",
    "nombre_cientifico": "Schinus molle",
    "identificacion": "Confirmada",
    "origen": "Nativa",
    "condicion_conservacion": "Sin categoría",
    "estado_general": "Bueno",
    "estado_copa": "Completa",
    "tronco_danos": "Sin daños",
    "raices_base": "Sanas",
    "interferencia_entorno": "Ninguna",
    "foto_archivo": "IMG_0001.jpg",
    "foto_detalle_archivo": "IMG_0002.jpg",
    "observaciones": "Junto a la banca",
}
MEDIDAS_FILA_COMPLETA = {
    "altura_total_m": 8.5,
    "dap_cm": 35.25,
    "copa_ns_m": 4.5,
    "copa_eo_m": 5,
    "co2_almacenado_kg": 120.5,
    "co2_captura_anual_kg": 10.25,
}


def crear_planilla(ruta, filas, sin_columnas=()):
    """Escribe una planilla de prueba; cada fila es {campo: valor}.

    Sin `codigo` en la fila se escribe la fórmula de la planilla real (sin valor guardado).
    """
    libro = Workbook()
    hoja = libro.active
    hoja.title = HOJA_PLANILLA
    encabezados = [enc for enc in COLUMNAS_PLANILLA if enc not in sin_columnas]
    hoja.append(encabezados)
    columna_por_campo = {
        COLUMNAS_PLANILLA[enc]: indice for indice, enc in enumerate(encabezados, start=1)
    }
    for numero_fila, fila in enumerate(filas, start=2):
        for campo, valor in fila.items():
            if campo in columna_por_campo:
                hoja.cell(row=numero_fila, column=columna_por_campo[campo], value=valor)
        if "codigo" not in fila and "codigo" in columna_por_campo:
            hoja.cell(
                row=numero_fila,
                column=columna_por_campo["codigo"],
                value=FORMULA_CODIGO.format(n=numero_fila),
            )
    for campo, lista in CATALOGOS.items():
        if campo in columna_por_campo:
            letra = get_column_letter(columna_por_campo[campo])
            validacion = DataValidation(type="list", formula1=f'"{lista}"')
            validacion.add(f"{letra}2:{letra}{FILAS_CON_VALIDACION + 1}")
            hoja.add_data_validation(validacion)
    libro.save(ruta)
    return ruta


@pytest.fixture
def sectores(db):
    """Los 5 sectores reales del GeoJSON del repo."""
    importar_sectores(RUTA_GEOJSON)


@pytest.fixture
def punto_dentro(sectores):
    """Coordenadas UTM de un punto dentro del sector 1."""
    punto = Sector.objects.get(id=1).geom.point_on_surface
    return punto.x, punto.y


@pytest.fixture
def ruta_planilla(tmp_path):
    return tmp_path / NOMBRE_ARCHIVO


def fila(**extra):
    datos = {"sector": 1, "brigada": "Brigada A"}
    datos.update(extra)
    return datos
