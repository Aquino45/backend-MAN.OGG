"""Ida y vuelta UTM y grados sobre un punto real del campus, por las dos rutas de conversión.

La planilla convierte grados a UTM con GEOS y GDAL; el panel convierte UTM y grados con PostGIS.
"""

import pytest
from django.contrib.gis.geos import Point

from apps.censo.servicios import geometrias
from apps.censo.servicios.lectura_planilla import leer
from config.constantes import SRID_MAPA, SRID_UTM_CENSO
from tests.censo.conftest import crear_planilla, fila

ESTE_M = 299536
NORTE_M = 8673480
TOLERANCIA_M = 0.01
DECIMALES_DE_LA_CELDA = 9
"""Los grados se escriben en la celda con nueve decimales (menos de un milímetro)."""


def test_planilla_grados_a_utm_vuelve_al_punto_real_con_geos(ruta_planilla):
    punto = Point(ESTE_M, NORTE_M, srid=SRID_UTM_CENSO).transform(SRID_MAPA, clone=True)
    latitud, longitud = (round(valor, DECIMALES_DE_LA_CELDA) for valor in (punto.y, punto.x))
    crear_planilla(
        ruta_planilla,
        [fila(utm_este_m=latitud, utm_norte_m=longitud)],
        renombrar={"UTM Este (m)": "Latitud", "UTM Norte (m)": "Longitud"},
    )

    datos = leer(ruta_planilla).filas[0][1]

    assert float(datos["utm_este_m"]) == pytest.approx(ESTE_M, abs=TOLERANCIA_M)
    assert float(datos["utm_norte_m"]) == pytest.approx(NORTE_M, abs=TOLERANCIA_M)


def test_panel_utm_a_grados_y_de_vuelta_a_utm_con_postgis(db):
    latitud, longitud = geometrias.utm_a_grados(ESTE_M, NORTE_M)

    este, norte = geometrias.grados_a_utm(latitud, longitud)

    assert (este, norte) == pytest.approx((ESTE_M, NORTE_M), abs=TOLERANCIA_M)


def test_las_dos_rutas_dan_los_mismos_grados_y_el_mismo_utm(db):
    geos = Point(ESTE_M, NORTE_M, srid=SRID_UTM_CENSO).transform(SRID_MAPA, clone=True)

    latitud, longitud = geometrias.utm_a_grados(ESTE_M, NORTE_M)

    assert (latitud, longitud) == pytest.approx((geos.y, geos.x), abs=1e-9)
