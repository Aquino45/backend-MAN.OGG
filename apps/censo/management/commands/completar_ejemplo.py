"""Comando: completa los árboles de ejemplo (ver servicios/completar_ejemplo.py)."""

from django.core.management.base import BaseCommand, CommandError

from apps.censo.servicios.completar_ejemplo import completar_ejemplo


def lineas_del_reporte(reporte):
    """Resumen legible en español del reporte."""
    lineas = [
        f"Archivo: {reporte.archivo}",
        f"Registros leídos: {reporte.registros}",
        f"Árboles completados: {len(reporte.completados)}",
        f"Sin cambios: {reporte.sin_cambios}",
        f"Publicados: {reporte.publicados}, en revisión: {reporte.en_revision}",
        f"No se pisa (la BD ya tiene otro valor): {len(reporte.no_se_pisa)}",
    ]
    lineas += [
        f"  {v.codigo} · {v.campo}: hay «{v.actual}», el archivo trae «{v.propuesto}»"
        for v in reporte.no_se_pisa
    ]
    lineas.append(f"Árboles reales que no se tocan: {len(reporte.reales_sin_tocar)}")
    lineas += [f"  {codigo}" for codigo in reporte.reales_sin_tocar]
    return lineas


class Command(BaseCommand):
    help = "Completa los árboles de ejemplo con los datos que les faltan (repetible, no pisa)."

    def add_arguments(self, parser):
        parser.add_argument("ruta", help="Ruta del archivo .json con los datos a completar")

    def handle(self, *args, **opciones):
        try:
            reporte = completar_ejemplo(opciones["ruta"])
        except ValueError as error:
            raise CommandError(str(error)) from error
        for linea in lineas_del_reporte(reporte):
            self.stdout.write(linea)
