"""Comando: importa los sectores desde un GeoJSON (ver servicios/importar_sectores.py)."""

from django.core.management.base import BaseCommand, CommandError

from apps.censo.servicios.importar_sectores import importar_sectores


class Command(BaseCommand):
    help = "Importa los sectores desde un GeoJSON en UTM. Se puede repetir sin duplicar."

    def add_arguments(self, parser):
        parser.add_argument("ruta", help="Ruta del archivo .geojson")

    def handle(self, *args, **opciones):
        try:
            reporte = importar_sectores(opciones["ruta"])
        except ValueError as error:
            raise CommandError(str(error)) from error
        for linea in reporte.lineas():
            self.stdout.write(linea)
