"""Controladores del censo. Delgados: validan la ruta, piden al selector y devuelven el DTO."""

import re

from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.censo.api.serializers import (
    ArbolResumenColeccionSerializer,
    ArbolSerializer,
    SectorColeccionSerializer,
)
from apps.censo.selectores import arbol_por_codigo, arboles_de_sector, sectores_con_total
from config.constantes import PATRON_CODIGO_ARBOL


@api_view(["GET"])
def sectores(request):
    """Los sectores del campus como GeoJSON, con su total de árboles."""
    return Response(SectorColeccionSerializer(sectores_con_total()).data)


@api_view(["GET"])
def arboles_de_un_sector(request, sector_id):
    """Los árboles de un sector como GeoJSON; un sector que no existe es un 404."""
    arboles = arboles_de_sector(sector_id)
    if arboles is None:
        raise NotFound()
    return Response(ArbolResumenColeccionSerializer(arboles).data)


@api_view(["GET"])
def arbol(request, codigo):
    """La cartilla de un árbol. Un código mal formado ni se busca: da 404 como uno ausente."""
    if not re.fullmatch(PATRON_CODIGO_ARBOL, codigo):
        raise NotFound()
    arbol_encontrado = arbol_por_codigo(codigo)
    if arbol_encontrado is None:
        raise NotFound()
    return Response(ArbolSerializer(arbol_encontrado).data)
