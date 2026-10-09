"""Lecturas del censo: las consultas que alimentan el mapa y la cartilla de cada árbol.

Aquí no se sabe de HTTP ni se escribe en la BD. Las coordenadas se guardan en UTM y se
entregan en WGS 84 (`SRID_MAPA`), transformadas por PostGIS; el redondeo lo hace el serializer.
"""

from django.contrib.gis.db.models.functions import Transform
from django.db.models import Count

from apps.censo.models import Arbol, Sector
from config.constantes import SRID_MAPA


def sectores_con_total():
    """Los sectores del campus por `id`, con su total de árboles y su polígono para el mapa.

    Cuenta todo lo que hay en la BD (también los árboles sin datos) y lo hace en una sola consulta.
    """
    return Sector.objects.annotate(
        total_arboles=Count("arboles"),
        geom_mapa=Transform("geom", SRID_MAPA),
    ).order_by("id")


def arboles_de_sector(sector_id):
    """Los árboles de un sector por `codigo`, con su posición lista para el mapa.

    Devuelve `None` si el sector no existe. Un árbol sin coordenadas aparece igual, con
    `ubicacion_mapa` en null: está en la lista pero no en el mapa.
    """
    if not Sector.objects.filter(id=sector_id).exists():
        return None
    arboles = Arbol.objects.filter(sector_id=sector_id)
    return arboles.annotate(**_con_ubicacion_mapa()).order_by("codigo")


def arbol_por_codigo(codigo):
    """La cartilla de un árbol con su posición lista para el mapa, o `None` si no existe."""
    return Arbol.objects.annotate(**_con_ubicacion_mapa()).filter(codigo=codigo).first()


def _con_ubicacion_mapa():
    """Anotación común: la ubicación del árbol transformada a WGS 84."""
    return {"ubicacion_mapa": Transform("ubicacion", SRID_MAPA)}
