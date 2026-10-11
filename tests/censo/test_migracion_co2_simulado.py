"""Migración 0008: marca como simulado el CO₂ de los árboles que ya lo tenían (BE-015).

Se ejerce de verdad: se vuelve al estado 0007 dentro de la transacción del test, se crean árboles
con el esquema viejo, se migra a 0008 y se mira el resultado. Todo se deshace al terminar.
"""

import pytest
from django.contrib.gis.geos import Polygon
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from config.constantes import SRID_UTM_CENSO

ANTES = [("censo", "0007_calidad_del_registro")]
DESPUES = [("censo", "0008_co2_simulado")]
FUENTE = "Prueba de la migración"


def _migrar_a(objetivo):
    ejecutor = MigrationExecutor(connection)
    ejecutor.migrate(objetivo)
    return MigrationExecutor(connection).loader.project_state(objetivo).apps


@pytest.fixture
def esquema_viejo(db):
    """Las apps del estado 0007; al terminar, el esquema vuelve al último estado."""
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    apps_viejas = _migrar_a(ANTES)
    yield apps_viejas
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    _migrar_a(MigrationExecutor(connection).loader.graph.leaf_nodes())


def _arbol_viejo(apps_viejas, codigo, **extra):
    Sector = apps_viejas.get_model("censo", "Sector")
    Arbol = apps_viejas.get_model("censo", "Arbol")
    cuadrado = Polygon.from_bbox((300000, 8673000, 300100, 8673100))
    cuadrado.srid = SRID_UTM_CENSO
    sector, _ = Sector.objects.get_or_create(
        id=1, defaults={"nombre": "Sector 1", "geom": cuadrado, "fuente": FUENTE}
    )
    return Arbol.objects.create(codigo=codigo, sector=sector, fuente=FUENTE, **extra)


def test_marca_como_simulado_todo_arbol_con_algun_co2_y_solo_esos(esquema_viejo):
    _arbol_viejo(esquema_viejo, "S01-A001", co2_almacenado_kg=10, co2_captura_anual_kg=2)
    _arbol_viejo(esquema_viejo, "S01-A002", co2_captura_anual_kg=2)
    _arbol_viejo(esquema_viejo, "S01-A003", demo=True, co2_almacenado_kg=5)
    _arbol_viejo(esquema_viejo, "S01-A004")

    apps_nuevas = _migrar_a(DESPUES)

    Arbol = apps_nuevas.get_model("censo", "Arbol")
    marcas = dict(Arbol.objects.values_list("codigo", "co2_simulado"))
    assert marcas == {
        "S01-A001": True,
        "S01-A002": True,
        "S01-A003": True,
        "S01-A004": False,
    }


def test_marca_tambien_a_los_arboles_de_la_papelera(esquema_viejo):
    _arbol_viejo(
        esquema_viejo, "S01-A001", co2_almacenado_kg=10, eliminado_en="2026-10-01T10:00:00Z"
    )

    apps_nuevas = _migrar_a(DESPUES)

    assert apps_nuevas.get_model("censo", "Arbol").objects.get().co2_simulado is True


def test_la_restriccion_queda_puesta_y_la_reversa_no_rompe(esquema_viejo):
    apps_nuevas = _migrar_a(DESPUES)
    Arbol = apps_nuevas.get_model("censo", "Arbol")
    nombres = {restriccion.name for restriccion in Arbol._meta.constraints}

    assert "arbol_demo_con_co2_es_simulado" in nombres
    _migrar_a(ANTES)
    assert "co2_simulado" not in {c.name for c in _columnas_de_arbol()}


def _columnas_de_arbol():
    with connection.cursor() as cursor:
        return connection.introspection.get_table_description(cursor, "censo_arbol")
