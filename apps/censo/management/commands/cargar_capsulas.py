"""Comando: carga las cápsulas de ayuda desde un .json (ver servicios/capsulas.py)."""

from django.core.management.base import BaseCommand, CommandError

from apps.censo.servicios.capsulas import cargar_capsulas


def lineas_del_reporte(reporte):
    """Resumen legible en español del reporte de la carga."""
    return [
        f"Archivo: {reporte.archivo}",
        f"Ayudas: {reporte.ayudas.creados} creadas, {reporte.ayudas.actualizados} actualizadas, "
        f"{reporte.ayudas.omitidos} omitidas",
        f"Valores del catálogo: {reporte.valores.creados} creados, "
        f"{reporte.valores.actualizados} actualizados, {reporte.valores.omitidos} omitidos",
        f"Fichas de especie: {reporte.fichas.creados} creadas, "
        f"{reporte.fichas.actualizados} actualizadas, {reporte.fichas.omitidos} omitidas",
    ]


class Command(BaseCommand):
    help = "Carga las ayudas, el catálogo de valores y las fichas de especie desde un .json."

    def add_arguments(self, parser):
        parser.add_argument("ruta", help="Ruta del archivo .json de cápsulas")
        parser.add_argument(
            "--actualizar",
            action="store_true",
            help="Sobrescribe los textos que ya existen (conserva si la ficha está publicada)",
        )

    def handle(self, *args, **opciones):
        try:
            reporte = cargar_capsulas(opciones["ruta"], actualizar=opciones["actualizar"])
        except ValueError as error:
            raise CommandError(str(error)) from error
        for linea in lineas_del_reporte(reporte):
            self.stdout.write(linea)
