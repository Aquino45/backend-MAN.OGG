"""Tests de los selectores del censo: orden, totales, transformación a WGS84 y casos vacíos."""

import pytest
from django.contrib.gis.geos import Point

from apps.censo.models import Arbol, Sector
from apps.censo.selectores import arbol_por_codigo, arboles_de_sector, sectores_con_total
from config.constantes import SRID_MAPA, SRID_UTM_CENSO

FUENTE_PRUEBA = "Prueba de selectores"
LONGITUD_CAMPUS = -76.8
LATITUD_CAMPUS = -12.0
TOLERANCIA_GRADOS = 0.2


def crear_arbol(codigo, sector_id=1, ubicacion=None, **extra):
    """Árbol de prueba: siempre con fuente y `demo=True`."""
    return Arbol.objects.create(
        codigo=codigo,
        sector_id=sector_id,
        ubicacion=ubicacion,
        fuente=FUENTE_PRUEBA,
        demo=True,
        **extra,
    )


def punto_utm(coordenadas):
    return Point(*coordenadas, srid=SRID_UTM_CENSO)


def test_sectores_ordenados_por_id(sectores):
    ids = [sector.id for sector in sectores_con_total()]
    assert ids == sorted(ids)
    assert len(ids) == Sector.objects.count()


def test_total_arboles_cuenta_los_del_sector_y_los_muertos(sectores, punto_dentro):
    crear_arbol("S01-A001", ubicacion=punto_utm(punto_dentro), dap_cm=30)
    crear_arbol("S01-A002")
    crear_arbol("S01-A003", dap_cm=None, nombre_comun=None)  # «muerto»: sin dato, se cuenta
    crear_arbol("S02-A001", sector_id=2)
    totales = {sector.id: sector.total_arboles for sector in sectores_con_total()}
    assert totales[1] == 3
    assert totales[2] == 1
    assert totales[3] == 0


def test_sectores_con_total_hace_una_sola_consulta(sectores, django_assert_num_queries):
    crear_arbol("S01-A001")
    with django_assert_num_queries(1):
        filas = list(sectores_con_total())
        assert [sector.total_arboles for sector in filas][0] == 1
        assert all(sector.geom_mapa is not None for sector in filas)


def test_geom_mapa_viene_en_wgs84(sectores):
    for sector in sectores_con_total():
        assert sector.geom_mapa.srid == SRID_MAPA
        assert sector.geom.srid == SRID_UTM_CENSO


def test_arboles_ordenados_por_codigo(sectores):
    for codigo in ("S01-A003", "S01-A001", "S01-A002"):
        crear_arbol(codigo)
    codigos = [arbol.codigo for arbol in arboles_de_sector(1)]
    assert codigos == ["S01-A001", "S01-A002", "S01-A003"]


def test_arboles_de_sector_no_incluye_los_de_otro_sector(sectores):
    crear_arbol("S01-A001")
    crear_arbol("S02-A001", sector_id=2)
    assert [arbol.codigo for arbol in arboles_de_sector(1)] == ["S01-A001"]
    assert [arbol.codigo for arbol in arboles_de_sector(2)] == ["S02-A001"]


def test_sector_sin_arboles_da_lista_vacia(sectores):
    assert list(arboles_de_sector(3)) == []


def test_sector_inexistente_da_none(sectores):
    assert arboles_de_sector(99) is None


def test_ubicacion_mapa_cae_dentro_del_sector_en_wgs84(sectores, punto_dentro):
    crear_arbol("S01-A001", ubicacion=punto_utm(punto_dentro))
    arbol = arboles_de_sector(1)[0]
    sector = next(sector for sector in sectores_con_total() if sector.id == 1)
    assert arbol.ubicacion_mapa.srid == SRID_MAPA
    assert sector.geom_mapa.contains(arbol.ubicacion_mapa)
    assert arbol.ubicacion_mapa.x == pytest.approx(LONGITUD_CAMPUS, abs=TOLERANCIA_GRADOS)
    assert arbol.ubicacion_mapa.y == pytest.approx(LATITUD_CAMPUS, abs=TOLERANCIA_GRADOS)


def test_arbol_sin_ubicacion_tiene_ubicacion_mapa_none(sectores):
    crear_arbol("S01-A001")
    assert arboles_de_sector(1)[0].ubicacion_mapa is None
    assert arbol_por_codigo("S01-A001").ubicacion_mapa is None


def test_arbol_muerto_se_devuelve_tal_cual(sectores):
    crear_arbol("S01-A009", dap_cm=None, nombre_comun=None, nombre_cientifico=None)
    arbol = arbol_por_codigo("S01-A009")
    assert arbol.dap_cm is None
    assert arbol.nombre_comun is None
    assert arbol.ubicacion is None
    assert [a.codigo for a in arboles_de_sector(1)] == ["S01-A009"]


def test_arbol_por_codigo_trae_ubicacion_mapa(sectores, punto_dentro):
    crear_arbol("S01-A001", ubicacion=punto_utm(punto_dentro))
    arbol = arbol_por_codigo("S01-A001")
    assert arbol.codigo == "S01-A001"
    assert arbol.ubicacion_mapa.srid == SRID_MAPA


def test_codigo_inexistente_da_none(sectores):
    assert arbol_por_codigo("S01-Z999") is None
