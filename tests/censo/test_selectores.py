"""Tests de los selectores del censo: orden, totales, transformación a WGS84 y casos vacíos."""

from datetime import UTC, datetime

import pytest
from django.contrib.gis.geos import Point

from apps.censo.models import Sector
from apps.censo.selectores import (
    arbol_por_codigo,
    arboles_de_sector,
    publicados,
    sectores_con_total,
)
from config.constantes import ESTADO_REGISTRO_EN_REVISION, SRID_MAPA, SRID_UTM_CENSO
from tests.censo.conftest import arbol_evaluado

LONGITUD_CAMPUS = -76.8
LATITUD_CAMPUS = -12.0
TOLERANCIA_GRADOS = 0.2
CONSULTAS_DE_LA_CARTILLA = 1 + 3  # el árbol, más ayudas, valores y fichas


def crear_arbol(codigo, sector_id=1, **extra):
    """Árbol de prueba completo y publicado (`demo=True`, sin brigada); con `extra` se cambia."""
    extra.setdefault("brigada", None)
    return arbol_evaluado(codigo, sector_id, demo=True, **extra)


def punto_utm(coordenadas):
    return Point(*coordenadas, srid=SRID_UTM_CENSO)


def test_sectores_ordenados_por_id(sectores):
    ids = [sector.id for sector in sectores_con_total()]
    assert ids == sorted(ids)
    assert len(ids) == Sector.objects.count()


def test_total_arboles_cuenta_solo_los_publicados_de_cada_sector(sectores, punto_dentro):
    crear_arbol("S01-A001", ubicacion=punto_utm(punto_dentro), dap_cm=30)
    crear_arbol("S01-A002")
    crear_arbol("S01-A003", dap_cm=None, nombre_comun=None)  # «muerto»: en revisión, no cuenta
    crear_arbol("S02-A001", sector_id=2)
    totales = {sector.id: sector.total_arboles for sector in sectores_con_total()}
    assert totales[1] == 2
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


def test_un_arbol_en_revision_no_sale_en_la_lista_ni_en_la_cartilla(sectores):
    crear_arbol("S01-A001")
    en_revision = crear_arbol("S01-A009", dap_cm=None, nombre_comun=None, nombre_cientifico=None)

    assert en_revision.estado_registro == ESTADO_REGISTRO_EN_REVISION
    assert arbol_por_codigo("S01-A009") is None
    assert [a.codigo for a in arboles_de_sector(1)] == ["S01-A001"]


def test_publicados_es_el_unico_punto_y_excluye_revision_y_papelera(sectores):
    crear_arbol("S01-A001")
    crear_arbol("S01-A002", nombre_comun=None)
    crear_arbol("S01-A003", eliminado_en=datetime.now(tz=UTC), motivo_eliminacion="Duplicado")

    assert [arbol.codigo for arbol in publicados()] == ["S01-A001"]


def test_arbol_por_codigo_trae_ubicacion_mapa(sectores, punto_dentro):
    crear_arbol("S01-A001", ubicacion=punto_utm(punto_dentro))
    arbol = arbol_por_codigo("S01-A001")
    assert arbol.codigo == "S01-A001"
    assert arbol.ubicacion_mapa.srid == SRID_MAPA


def test_codigo_inexistente_da_none(sectores):
    assert arbol_por_codigo("S01-Z999") is None


def test_arbol_por_codigo_trae_la_ubicacion_utm_tal_como_se_guardo(sectores, punto_dentro):
    crear_arbol("S01-A001", ubicacion=punto_utm(punto_dentro))
    arbol = arbol_por_codigo("S01-A001")
    assert arbol.ubicacion.srid == SRID_UTM_CENSO
    assert (arbol.ubicacion.x, arbol.ubicacion.y) == pytest.approx(punto_dentro)


def test_la_lista_y_la_cartilla_traen_uid_y_destacado_sin_consultas_extra(
    sectores, django_assert_num_queries
):
    motivo = "Ejemplar de mayor copa del sector"
    crear_arbol("S01-A001", destacado=True, motivo_destacado=motivo)
    crear_arbol("S01-A002")
    with django_assert_num_queries(2):
        arboles = list(arboles_de_sector(1))
    with django_assert_num_queries(CONSULTAS_DE_LA_CARTILLA):
        cartilla = arbol_por_codigo("S01-A001")

    with django_assert_num_queries(0):
        assert [(a.destacado, a.motivo_destacado) for a in arboles] == [
            (True, motivo),
            (False, None),
        ]
        assert arboles[0].uid != arboles[1].uid
        assert (cartilla.uid, cartilla.destacado) == (arboles[0].uid, True)


def test_la_papelera_no_cuenta_en_los_totales_ni_sale_en_las_lecturas(sectores):
    crear_arbol("S01-A001")
    crear_arbol("S01-A002", eliminado_en=datetime.now(tz=UTC), motivo_eliminacion="Duplicado")

    totales = {sector.id: sector.total_arboles for sector in sectores_con_total()}

    assert totales[1] == 1
    assert [arbol.codigo for arbol in arboles_de_sector(1)] == ["S01-A001"]
    assert arbol_por_codigo("S01-A002") is None
