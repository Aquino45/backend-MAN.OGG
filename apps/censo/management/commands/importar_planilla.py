"""Comando: importa la planilla de la brigada (ver servicios/importar_planilla.py)."""

from django.core.management.base import BaseCommand, CommandError

from apps.censo.servicios.importar_planilla import importar_planilla


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
