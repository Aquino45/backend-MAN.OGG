"""Geometrías del mapa del panel: conversión UTM y grados, caja del campus y contexto.

Todo se guarda en UTM 18S (`SRID_UTM_CENSO`); el mapa dibuja en grados. La conversión de un punto
la hace PostGIS (`ST_Transform`); el contexto sale ya en grados para dibujarlo tal cual.
"""

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from django.contrib.gis.db.models import Extent
from django.contrib.gis.db.models.functions import Transform
from django.contrib.gis.geos import Point
from django.db import connection, transaction

from apps.censo.models import Arbol, Sector
from apps.censo.servicios.calidad_registro import CAMPOS_DEL_ESTADO, aplicar, cargar_catalogo
from apps.censo.servicios.resolver_campos import RELACIONES_DEL_ARBOL
from config.constantes import (
    ATRIBUCION_ESRI,
    ATRIBUCION_ESRI_URL,
    ATRIBUCION_OSM,
    ATRIBUCION_OSM_URL,
    DECIMALES_COORDENADAS,
    DECIMALES_UTM,
    ESRI_URL_MOSAICOS,
    ESTADO_REGISTRO_EN_REVISION,
    ESTADO_REGISTRO_PUBLICADO,
    ID_CAPA_CALLES,
    ID_CAPA_SATELITE,
    MARGEN_CAMPUS_M,
    MOTIVO_HISTORIAL_FRONTERA_SECTOR,
    NOMBRE_CAPA_CALLES,
    NOMBRE_CAPA_SATELITE,
    OSM_URL_MOSAICOS,
    SRID_MAPA,
    SRID_UTM_CENSO,
    TIPO_CONTEXTO_ARBOL,
    TIPO_CONTEXTO_SECTOR,
    TOLERANCIA_FUERA_DE_SECTOR_M,
)

# --- conversión de coordenadas ----------------------------------------------------------------


def _transformar(x, y, srid_origen, srid_destino):
    """`(x, y)` de un punto en otro sistema de coordenadas, calculado por PostGIS."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ST_X(punto), ST_Y(punto) FROM "
            "(SELECT ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), %s), %s) AS punto) AS c",
            [float(x), float(y), srid_origen, srid_destino],
        )
        return cursor.fetchone()


def utm_a_grados(este_m, norte_m):
    """`(latitud, longitud)` en grados WGS 84 de un punto UTM 18S."""
    longitud, latitud = _transformar(este_m, norte_m, SRID_UTM_CENSO, SRID_MAPA)
    return latitud, longitud


def grados_a_utm(latitud, longitud):
    """`(este_m, norte_m)` en UTM 18S de un punto en grados WGS 84."""
    return _transformar(longitud, latitud, SRID_MAPA, SRID_UTM_CENSO)


# --- el campus -----------------------------------------------------------------------------------


def caja_del_campus():
    """`(este_min, norte_min, este_max, norte_max)` en UTM: los sectores más el margen; o None."""
    caja = Sector.objects.aggregate(caja=Extent("geom"))["caja"]
    if caja is None:
        return None
    este_min, norte_min, este_max, norte_max = caja
    return (
        este_min - MARGEN_CAMPUS_M,
        norte_min - MARGEN_CAMPUS_M,
        este_max + MARGEN_CAMPUS_M,
        norte_max + MARGEN_CAMPUS_M,
    )


def _en_utm(punto):
    return punto if punto.srid == SRID_UTM_CENSO else punto.transform(SRID_UTM_CENSO, clone=True)


def esta_en_el_campus(punto):
    """True si el punto cae dentro de la caja de los sectores con su margen."""
    caja = caja_del_campus()
    if caja is None:
        return False
    punto = _en_utm(punto)
    return caja[0] <= punto.x <= caja[2] and caja[1] <= punto.y <= caja[3]


def sector_que_contiene(punto):
    """El sector cuyo polígono contiene el punto (el de menor número si hay varios), o None."""
    return Sector.objects.filter(geom__covers=_en_utm(punto)).order_by("id").first()


def describir_punto(este_m, norte_m):
    """Lo que el panel muestra de un punto UTM: sus grados, si está en el campus y su sector."""
    punto = Point(float(este_m), float(norte_m), srid=SRID_UTM_CENSO)
    latitud, longitud = utm_a_grados(este_m, norte_m)
    sector = sector_que_contiene(punto)
    return {
        "utm_este_m": round(punto.x, DECIMALES_UTM),
        "utm_norte_m": round(punto.y, DECIMALES_UTM),
        "latitud": round(latitud, DECIMALES_COORDENADAS),
        "longitud": round(longitud, DECIMALES_COORDENADAS),
        "dentro_del_campus": esta_en_el_campus(punto),
        "sector_id": sector.id if sector else None,
    }


# --- contexto del mapa ----------------------------------------------------------------------------


def contexto_del_mapa(sector_id=None, arbol_id=None):
    """Los sectores y los árboles como GeoJSON en grados, para verlos de fondo sin editarlos.

    Con `sector_id` (se edita ese sector) trae sus vecinos y solo sus árboles; con `arbol_id` (se
    edita ese árbol) trae los cinco sectores y los demás árboles. Los árboles de la papelera y los
    que no tienen ubicación no salen.
    """
    sectores = Sector.objects.annotate(geom_mapa=Transform("geom", SRID_MAPA))
    arboles = Arbol.objects.filter(ubicacion__isnull=False)
    if sector_id is not None:
        sectores = sectores.exclude(pk=sector_id)
        arboles = arboles.filter(sector_id=sector_id)
    if arbol_id is not None:
        arboles = arboles.exclude(pk=arbol_id)
    elementos = [
        _elemento(
            sector.geom_mapa,
            {"tipo": TIPO_CONTEXTO_SECTOR, "id": sector.id, "nombre": sector.nombre},
        )
        for sector in sectores
    ]
    arboles = arboles.annotate(punto_mapa=Transform("ubicacion", SRID_MAPA))
    elementos += [
        _elemento(arbol.punto_mapa, {"tipo": TIPO_CONTEXTO_ARBOL, "codigo": arbol.codigo})
        for arbol in arboles.only("codigo")
    ]
    return {"type": "FeatureCollection", "features": elementos}


def _elemento(geometria, propiedades):
    return {"type": "Feature", "geometry": json.loads(geometria.json), "properties": propiedades}


# --- capas de fondo y lectura de números -------------------------------------------------------


def capas_de_fondo(clave_esri):
    """Las capas de fondo del mapa: el satélite de Esri si hay clave, y siempre las calles."""
    calles = {
        "id": ID_CAPA_CALLES,
        "nombre": NOMBRE_CAPA_CALLES,
        "url": OSM_URL_MOSAICOS,
        "atribucion": ATRIBUCION_OSM,
        "atribucion_url": ATRIBUCION_OSM_URL,
    }
    if not clave_esri:
        return [calles]
    satelite = {
        "id": ID_CAPA_SATELITE,
        "nombre": NOMBRE_CAPA_SATELITE,
        "url": ESRI_URL_MOSAICOS.replace("{clave}", quote(clave_esri, safe="")),
        "atribucion": ATRIBUCION_ESRI,
        "atribucion_url": ATRIBUCION_ESRI_URL,
    }
    return [satelite, calles]


def leer_numero(texto):
    """El texto como número (con coma o punto decimal), o None si falta o no es un número."""
    try:
        numero = Decimal((texto or "").strip().replace(",", "."))
    except InvalidOperation:
        return None
    return float(numero) if numero.is_finite() else None


def en_rango(numero, rango, excluye_maximo=False):
    """True si el número existe y cae en `(mínimo, máximo)`."""
    if numero is None:
        return False
    minimo, maximo = rango
    return minimo <= numero < maximo if excluye_maximo else minimo <= numero <= maximo


# --- fronteras de un sector -----------------------------------------------------------------------


@dataclass
class ResultadoRecalculo:
    """Cuántos árboles de un sector cambiaron de estado al recalcular su calidad."""

    a_revision: int = 0
    publicados: int = 0


def contar_arboles_fuera(sector_id, poligono):
    """Cuántos árboles del sector quedarían a más de la tolerancia del polígono (en UTM)."""
    cerca = Arbol.objects.filter(sector_id=sector_id, ubicacion__isnull=False)
    return cerca.exclude(ubicacion__dwithin=(poligono, TOLERANCIA_FUERA_DE_SECTOR_M)).count()


def recalcular_calidad_del_sector(sector):
    """Aplica la regla de calidad a los árboles del sector y guarda solo los que cambian.

    Cada cambio queda en el historial del árbol. Devuelve cuántos pasaron a revisión y cuántos
    volvieron a publicarse.
    """
    catalogo = cargar_catalogo()
    resultado = ResultadoRecalculo()
    arboles = Arbol.objects.filter(sector=sector).select_related("sector", *RELACIONES_DEL_ARBOL)
    with transaction.atomic():
        for arbol in arboles:
            antes = {campo: getattr(arbol, campo) for campo in CAMPOS_DEL_ESTADO}
            aplicar(arbol, catalogo, sector.geom)
            if antes == {campo: getattr(arbol, campo) for campo in CAMPOS_DEL_ESTADO}:
                continue
            arbol._change_reason = MOTIVO_HISTORIAL_FRONTERA_SECTOR.format(sector_id=sector.id)
            arbol.save(update_fields=CAMPOS_DEL_ESTADO)
            if antes["estado_registro"] == arbol.estado_registro:
                continue
            if arbol.estado_registro == ESTADO_REGISTRO_EN_REVISION:
                resultado.a_revision += 1
            elif arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO:
                resultado.publicados += 1
    return resultado
