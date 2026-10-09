"""Importa los sectores desde un GeoJSON. Se puede repetir sin duplicar (upsert por `id`)."""

from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

from django.contrib.gis.gdal import DataSource, GDALException
from django.contrib.gis.geos import Polygon
from django.db import transaction

from apps.censo.models import Sector
from config.constantes import M2_POR_HECTAREA, PROPIEDADES_OBLIGATORIAS_SECTOR, SRID_UTM_CENSO


@dataclass
class SectorImportado:
    """Una línea del reporte: un sector y su área."""

    id: int
    nombre: str
    hectareas: float
    creado: bool


@dataclass
class ReporteSectores:
    """Resultado de importar los sectores."""

    sectores: list[SectorImportado] = field(default_factory=list)

    @property
    def creados(self):
        return sum(1 for sector in self.sectores if sector.creado)

    @property
    def actualizados(self):
        return sum(1 for sector in self.sectores if not sector.creado)

    @property
    def hectareas_totales(self):
        return sum(sector.hectareas for sector in self.sectores)

    def lineas(self):
        """Resumen legible en español."""
        lineas = [
            f"Sectores creados: {self.creados}",
            f"Sectores actualizados: {self.actualizados}",
        ]
        lineas += [
            f"  Sector {sector.id} ({sector.nombre}): {sector.hectareas:.2f} ha"
            for sector in self.sectores
        ]
        lineas.append(f"Área total: {self.hectareas_totales:.2f} ha")
        return lineas


def importar_sectores(ruta):
    """Lee el GeoJSON, lo valida y hace upsert por `id`. Todo o nada: ante un error no escribe.

    Lanza ValueError con un mensaje claro si el archivo no sirve.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ValueError(f"No existe el archivo: {ruta}")
    try:
        fuente_datos = DataSource(str(ruta))
    except GDALException as error:
        raise ValueError(f"GDAL no pudo leer {ruta.name}: {error}") from error

    capa = fuente_datos[0]
    srid_archivo = capa.srs.srid if capa.srs else None
    if srid_archivo != SRID_UTM_CENSO:
        raise ValueError(
            f"El GeoJSON viene en el SRID {srid_archivo} y se esperaba {SRID_UTM_CENSO} (UTM 18S)."
        )

    sectores = [_leer_sector(rasgo) for rasgo in capa]
    _validar_sin_traslapes(sectores)

    reporte = ReporteSectores()
    with transaction.atomic():
        for datos in sectores:
            sector, creado = Sector.objects.update_or_create(id=datos.pop("id"), defaults=datos)
            reporte.sectores.append(
                SectorImportado(
                    id=sector.id,
                    nombre=sector.nombre,
                    hectareas=sector.geom.area / M2_POR_HECTAREA,
                    creado=creado,
                )
            )
    return reporte


def _leer_sector(rasgo):
    """Convierte un feature en los datos del modelo, validando lo que trae."""
    nombres = set(rasgo.fields)
    faltan = [nombre for nombre in PROPIEDADES_OBLIGATORIAS_SECTOR if nombre not in nombres]
    if faltan:
        raise ValueError(f"Un sector no trae las propiedades: {', '.join(faltan)}.")
    id_sector = int(rasgo.get("id"))
    geometria = rasgo.geom.geos
    if not isinstance(geometria, Polygon):
        raise ValueError(f"El sector {id_sector} no es un Polygon (es {geometria.geom_type}).")
    if not geometria.valid:
        raise ValueError(
            f"El polígono del sector {id_sector} no es válido: {geometria.valid_reason}"
        )
    datos = {
        "id": id_sector,
        "nombre": rasgo.get("nombre"),
        "geom": geometria,
        "provisional": bool(rasgo.get("provisional")),
        "fuente": rasgo.get("fuente"),
    }
    # El color solo se toca si el archivo lo trae: así reimportar no borra el que se puso a mano.
    if "color" in nombres:
        datos["color"] = rasgo.get("color") or None
    return datos


def _validar_sin_traslapes(sectores):
    """Falla con ids repetidos o si dos sectores comparten área (tocarse por el borde vale)."""
    ids = [datos["id"] for datos in sectores]
    repetidos = sorted({id_sector for id_sector in ids if ids.count(id_sector) > 1})
    if repetidos:
        raise ValueError(f"El GeoJSON repite el id de sector: {', '.join(map(str, repetidos))}.")
    for uno, otro in combinations(sectores, 2):
        area_comun = uno["geom"].intersection(otro["geom"]).area
        if area_comun > 0:
            raise ValueError(
                f"Los sectores {uno['id']} y {otro['id']} se traslapan en {area_comun:.2f} m²."
            )
