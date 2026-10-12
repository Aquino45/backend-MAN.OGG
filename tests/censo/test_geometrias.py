"""Tests del servicio de geometrías: conversión UTM y grados, campus y contexto del mapa."""

import pytest
from django.contrib.gis.geos import Point

from apps.censo.models import Sector
from apps.censo.servicios import geometrias
from apps.censo.servicios.papelera import mover_a_papelera
from config.constantes.general import SRID_MAPA, SRID_UTM_CENSO
from config.constantes.geometrias import MARGEN_CAMPUS_M
from tests.censo.conftest import arbol_evaluado


def punto_utm(este, norte):
    return Point(este, norte, srid=SRID_UTM_CENSO)


# --- conversión ----------------------------------------------------------------------------


def test_utm_a_grados_coincide_con_el_proj_de_geos(punto_dentro):
    este, norte = punto_dentro
    esperado = punto_utm(este, norte).transform(SRID_MAPA, clone=True)

    latitud, longitud = geometrias.utm_a_grados(este, norte)

    assert (latitud, longitud) == pytest.approx((esperado.y, esperado.x), abs=1e-8)
    assert -12.1 < latitud < -11.9 and -77 < longitud < -76.7


def test_grados_a_utm_es_la_inversa_de_utm_a_grados(punto_dentro):
    este, norte = punto_dentro
    latitud, longitud = geometrias.utm_a_grados(este, norte)

    assert geometrias.grados_a_utm(latitud, longitud) == pytest.approx((este, norte), abs=1e-4)


# --- caja del campus ---------------------------------------------------------------------------


def test_la_caja_del_campus_es_la_extension_de_los_sectores_con_el_margen(sectores):
    extension = Sector.objects.first().geom.extent
    for sector in Sector.objects.all():
        extension = (
            min(extension[0], sector.geom.extent[0]),
            min(extension[1], sector.geom.extent[1]),
            max(extension[2], sector.geom.extent[2]),
            max(extension[3], sector.geom.extent[3]),
        )

    caja = geometrias.caja_del_campus()

    assert caja == pytest.approx(
        (
            extension[0] - MARGEN_CAMPUS_M,
            extension[1] - MARGEN_CAMPUS_M,
            extension[2] + MARGEN_CAMPUS_M,
            extension[3] + MARGEN_CAMPUS_M,
        )
    )


def test_un_punto_dentro_del_campus_y_otro_a_kilometros_de_distancia(punto_dentro):
    este, norte = punto_dentro

    assert geometrias.esta_en_el_campus(punto_utm(este, norte)) is True
    assert geometrias.esta_en_el_campus(punto_utm(este + 10_000, norte)) is False


def test_dentro_del_margen_aun_cuenta_como_campus(sectores):
    caja = geometrias.caja_del_campus()
    borde_norte = caja[3]

    assert geometrias.esta_en_el_campus(punto_utm(caja[0] + 1, borde_norte - 1)) is True
    assert geometrias.esta_en_el_campus(punto_utm(caja[0] + 1, borde_norte + 1)) is False


def test_sin_sectores_ningun_punto_esta_en_el_campus(db):
    assert geometrias.esta_en_el_campus(punto_utm(299_000, 8_673_000)) is False


# --- sector de un punto ------------------------------------------------------------------------


def test_el_sector_que_contiene_un_punto(sectores):
    for sector in Sector.objects.all():
        assert geometrias.sector_que_contiene(sector.geom.point_on_surface) == sector


def test_un_punto_fuera_de_todos_los_sectores_no_tiene_sector(punto_dentro):
    este, norte = punto_dentro

    assert geometrias.sector_que_contiene(punto_utm(este + 10_000, norte)) is None


def test_describir_un_punto_da_grados_sector_y_si_esta_en_el_campus(punto_dentro):
    este, norte = punto_dentro

    descripcion = geometrias.describir_punto(este, norte)

    assert descripcion["utm_este_m"] == pytest.approx(este, abs=0.01)
    assert descripcion["utm_norte_m"] == pytest.approx(norte, abs=0.01)
    assert descripcion["dentro_del_campus"] is True
    assert descripcion["sector_id"] == 1
    assert (descripcion["latitud"], descripcion["longitud"]) == pytest.approx(
        geometrias.utm_a_grados(este, norte), abs=1e-6
    )


# --- contexto del mapa -------------------------------------------------------------------------


def clasificar(coleccion):
    por_tipo = {}
    for elemento in coleccion["features"]:
        por_tipo.setdefault(elemento["properties"]["tipo"], []).append(elemento)
    return por_tipo


def test_el_contexto_trae_los_cinco_sectores_y_los_arboles_en_grados(sectores):
    arbol_evaluado("S01-A001")
    arbol_evaluado("S02-A001", sector_id=2)

    por_tipo = clasificar(geometrias.contexto_del_mapa())

    assert len(por_tipo["sector"]) == 5
    assert {e["properties"]["nombre"] for e in por_tipo["sector"]} == set(
        Sector.objects.values_list("nombre", flat=True)
    )
    assert {e["properties"]["codigo"] for e in por_tipo["arbol"]} == {"S01-A001", "S02-A001"}
    longitud, latitud = por_tipo["arbol"][0]["geometry"]["coordinates"]
    assert -77 < longitud < -76.7 and -12.1 < latitud < -11.9


def test_el_contexto_del_arbol_deja_fuera_al_arbol_que_se_edita(sectores):
    editado = arbol_evaluado("S01-A001")
    arbol_evaluado("S01-A002")

    por_tipo = clasificar(geometrias.contexto_del_mapa(arbol_id=editado.pk))

    assert len(por_tipo["sector"]) == 5
    assert [e["properties"]["codigo"] for e in por_tipo["arbol"]] == ["S01-A002"]


def test_el_contexto_del_sector_trae_los_vecinos_y_solo_los_arboles_de_ese_sector(sectores):
    arbol_evaluado("S01-A001")
    arbol_evaluado("S02-A001", sector_id=2)

    por_tipo = clasificar(geometrias.contexto_del_mapa(sector_id=1))

    assert sorted(e["properties"]["id"] for e in por_tipo["sector"]) == [2, 3, 4, 5]
    assert [e["properties"]["codigo"] for e in por_tipo["arbol"]] == ["S01-A001"]


def test_el_contexto_no_trae_arboles_de_la_papelera_ni_sin_ubicacion(sectores, usuario_editor):
    en_papelera = arbol_evaluado("S01-A001")
    arbol_evaluado("S01-A002", ubicacion=None)
    mover_a_papelera(en_papelera, usuario_editor, "Prueba")

    por_tipo = clasificar(geometrias.contexto_del_mapa())

    assert "arbol" not in por_tipo
