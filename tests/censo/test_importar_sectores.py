"""Tests del importador de sectores (GeoJSON en UTM 18S)."""

import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.censo.models import Sector
from apps.censo.servicios.importar_sectores import importar_sectores
from config.constantes import SRID_UTM_CENSO

RUTA_GEOJSON = (
    Path(__file__).resolve().parents[2] / "datos" / "sectores" / "sectores-utm18s-v0.geojson"
)
ESTE_BASE = 300000.0
NORTE_BASE = 8673000.0


def _cuadrado(este, norte, lado=100.0):
    """Anillo cerrado de un cuadrado con esquina inferior izquierda en (este, norte)."""
    return [
        [este, norte],
        [este + lado, norte],
        [este + lado, norte + lado],
        [este, norte + lado],
        [este, norte],
    ]


def _escribir_geojson(ruta, anillos_por_id, epsg=SRID_UTM_CENSO):
    """Arma un GeoJSON de prueba; con epsg=None no declara CRS."""
    rasgos = [
        {
            "type": "Feature",
            "properties": {
                "id": id_sector,
                "nombre": f"Sector {id_sector}",
                "provisional": id_sector > 1,
                "fuente": "Prueba",
            },
            "geometry": {"type": "Polygon", "coordinates": [anillo]},
        }
        for id_sector, anillo in anillos_por_id.items()
    ]
    contenido = {"type": "FeatureCollection", "features": rasgos}
    if epsg is not None:
        contenido["crs"] = {"type": "name", "properties": {"name": f"urn:ogc:def:crs:EPSG::{epsg}"}}
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    return ruta


@pytest.mark.django_db
def test_importa_los_5_sectores_con_sus_areas():
    reporte = importar_sectores(RUTA_GEOJSON)

    assert Sector.objects.count() == 5
    assert reporte.creados == 5
    assert reporte.actualizados == 0
    hectareas = {sector.id: sector.hectareas for sector in reporte.sectores}
    assert hectareas[1] == pytest.approx(3.60, abs=0.005)
    assert reporte.hectareas_totales == pytest.approx(50.16, abs=0.005)
    assert Sector.objects.get(id=1).geom.srid == SRID_UTM_CENSO
    provisionales = Sector.objects.filter(provisional=True).values_list("id", flat=True)
    assert list(provisionales) == [2, 3, 4, 5]


@pytest.mark.django_db
def test_importar_dos_veces_no_duplica():
    importar_sectores(RUTA_GEOJSON)

    reporte = importar_sectores(RUTA_GEOJSON)

    assert Sector.objects.count() == 5
    assert reporte.creados == 0
    assert reporte.actualizados == 5


@pytest.mark.django_db
def test_reimportar_conserva_el_color_puesto_a_mano():
    importar_sectores(RUTA_GEOJSON)
    Sector.objects.filter(id=1).update(color="copa-carmin")

    importar_sectores(RUTA_GEOJSON)

    assert Sector.objects.get(id=1).color == "copa-carmin"


@pytest.mark.django_db
@pytest.mark.parametrize("epsg", [32717, 4326, None])
def test_rechaza_geojson_con_otro_srid(tmp_path, epsg):
    ruta = _escribir_geojson(tmp_path / "otro.geojson", {1: _cuadrado(ESTE_BASE, NORTE_BASE)}, epsg)

    with pytest.raises(ValueError, match="SRID"):
        importar_sectores(ruta)

    assert Sector.objects.count() == 0


@pytest.mark.django_db
def test_rechaza_sectores_que_se_traslapan(tmp_path):
    ruta = _escribir_geojson(
        tmp_path / "traslape.geojson",
        {1: _cuadrado(ESTE_BASE, NORTE_BASE), 2: _cuadrado(ESTE_BASE + 50, NORTE_BASE)},
    )

    with pytest.raises(ValueError, match="se traslapan"):
        importar_sectores(ruta)

    assert Sector.objects.count() == 0


@pytest.mark.django_db
def test_acepta_sectores_que_solo_comparten_borde(tmp_path):
    ruta = _escribir_geojson(
        tmp_path / "vecinos.geojson",
        {1: _cuadrado(ESTE_BASE, NORTE_BASE), 2: _cuadrado(ESTE_BASE + 100, NORTE_BASE)},
    )

    importar_sectores(ruta)

    assert Sector.objects.count() == 2


@pytest.mark.django_db
def test_rechaza_poligono_invalido(tmp_path):
    corbata = [
        [ESTE_BASE, NORTE_BASE],
        [ESTE_BASE + 100, NORTE_BASE + 100],
        [ESTE_BASE + 100, NORTE_BASE],
        [ESTE_BASE, NORTE_BASE + 100],
        [ESTE_BASE, NORTE_BASE],
    ]
    ruta = _escribir_geojson(tmp_path / "corbata.geojson", {1: corbata})

    with pytest.raises(ValueError, match="no es válido"):
        importar_sectores(ruta)


def test_archivo_inexistente_da_error_claro(tmp_path):
    with pytest.raises(ValueError, match="No existe el archivo"):
        importar_sectores(tmp_path / "no-existe.geojson")


@pytest.mark.django_db
def test_comando_imprime_el_resumen_en_espanol():
    salida = StringIO()

    call_command("importar_sectores", str(RUTA_GEOJSON), stdout=salida)

    texto = salida.getvalue()
    assert "Sectores creados: 5" in texto
    assert "Área total: 50.16 ha" in texto


@pytest.mark.django_db
def test_comando_convierte_el_error_en_command_error(tmp_path):
    ruta = _escribir_geojson(tmp_path / "otro.geojson", {1: _cuadrado(ESTE_BASE, NORTE_BASE)}, 4326)

    with pytest.raises(CommandError, match="SRID"):
        call_command("importar_sectores", str(ruta))
