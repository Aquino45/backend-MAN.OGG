"""Comando: importa la planilla de la brigada (ver servicios/importar_planilla.py)."""

from django.core.management.base import BaseCommand, CommandError

from apps.censo.servicios.importar_planilla import importar_planilla
from apps.censo.servicios.lectura_planilla import ENCABEZADO_POR_CAMPO
from config.constantes.carga import AVISO_UBICACION_DEL_PANEL
from config.constantes.catalogos import (
    CAMPO_BRIGADA,
    CAMPO_GRUPO,
    TITULO_SIN_RESOLVER_BRIGADA,
    TITULO_SIN_RESOLVER_CATALOGO,
)


def lineas_del_reporte(reporte):
    """Resumen legible en español del reporte de la importación."""
    aviso_seco = " (simulacro: no se escribió nada)" if reporte.seco else ""
    lineas = [
        f"Planilla: {reporte.archivo}{aviso_seco}",
        f"Filas leídas: {reporte.filas_leidas}",
        f"Árboles creados: {reporte.creados}",
        f"Árboles actualizados: {reporte.actualizados}",
        f"Sin coordenadas: {reporte.sin_coordenadas}",
        f"Códigos calculados: {reporte.codigos_calculados}",
    ]
    for titulo, valores in (
        ("Números no válidos", reporte.numeros_no_validos),
        ("Fechas no válidas", reporte.fechas_no_validas),
        ("Valores fuera de catálogo", reporte.fuera_de_catalogo),
    ):
        lineas.append(f"{titulo}: {len(valores)}")
        lineas += [f"  {v.codigo} · {v.columna}: «{v.texto}»" for v in valores]
    lineas.append(f"Árboles fuera de su sector: {len(reporte.fuera_de_sector)}")
    lineas += [
        f"  {a.codigo} (sector {a.sector}): a {a.distancia_m:.2f} m de su polígono"
        for a in reporte.fuera_de_sector
    ]
    lineas += _lineas_de_avisos(reporte)
    lineas += _lineas_sin_resolver(reporte)
    lineas += _lineas_de_calidad(reporte)
    return lineas


def _lineas_de_avisos(reporte):
    """Los avisos de la planilla y los árboles cuya ubicación del panel se mantuvo."""
    lineas = list(reporte.avisos)
    if reporte.ubicaciones_del_panel:
        lineas.append(f"{AVISO_UBICACION_DEL_PANEL}: {len(reporte.ubicaciones_del_panel)}")
        lineas += [f"  {codigo}" for codigo in reporte.ubicaciones_del_panel]
    return lineas


def _lineas_sin_resolver(reporte):
    """Los textos que no coinciden con una especie, un valor del catálogo, una brigada o un grupo.

    Los de brigada y grupo solo se informan: el grupo es opcional y no manda a revisión.
    """
    encabezados_brigada = {ENCABEZADO_POR_CAMPO[CAMPO_BRIGADA], ENCABEZADO_POR_CAMPO[CAMPO_GRUPO]}
    lineas = []
    for titulo, es_de_brigada in (
        (TITULO_SIN_RESOLVER_CATALOGO, False),
        (TITULO_SIN_RESOLVER_BRIGADA, True),
    ):
        textos = [
            v for v in reporte.sin_resolver if (v.columna in encabezados_brigada) == es_de_brigada
        ]
        lineas.append(f"{titulo}: {len(textos)}")
        lineas += [f"  {v.codigo} · {v.columna}: «{v.texto}»" for v in textos]
    return lineas


def _lineas_de_calidad(reporte):
    """Cuántos salen en la web, cuáles quedan en revisión (con motivos) y qué no se incorporó."""
    lineas = [
        f"{reporte.publicados} publicados, {len(reporte.en_revision)} en revisión, "
        f"{len(reporte.duplicados)} duplicados no incorporados, "
        f"{len(reporte.ejemplo_sin_cambios)} de ejemplo sin cambios"
    ]
    for registro in reporte.en_revision:
        lineas.append(f"  En revisión {registro.codigo}: " + "; ".join(registro.motivos))
    lineas += [f"  Duplicado {d.codigo}: {d.motivo}" for d in reporte.duplicados]
    lineas += [f"  De ejemplo sin cambios: {codigo}" for codigo in reporte.ejemplo_sin_cambios]
    if reporte.ejemplo_reemplazados:
        lineas.append("Reemplazados por datos de la planilla (eran de ejemplo):")
        lineas += [f"  {codigo}" for codigo in reporte.ejemplo_reemplazados]
    if reporte.catalogo_sin_cargar:
        lineas.append(reporte.catalogo_sin_cargar)
    return lineas


class Command(BaseCommand):
    help = "Importa la planilla de la brigada (.xlsx). Se puede repetir sin duplicar."

    def add_arguments(self, parser):
        parser.add_argument("ruta", help="Ruta local del archivo .xlsx (no entra al repo)")
        parser.add_argument(
            "--seco",
            action="store_true",
            help="Valida y muestra el reporte sin escribir en la BD",
        )

    def handle(self, *args, **opciones):
        try:
            reporte = importar_planilla(opciones["ruta"], seco=opciones["seco"])
        except ValueError as error:
            raise CommandError(str(error)) from error
        for linea in lineas_del_reporte(reporte):
            self.stdout.write(linea)
