"""Comando: evalúa la calidad de todos los árboles (ver servicios/calidad_registro.py).

Se corre después de migrar y cada vez que cambia el catálogo. Se puede repetir.
"""

from django.core.management.base import BaseCommand

from apps.censo.servicios.calidad_registro import (
    aviso_catalogo_sin_cargar,
    cargar_catalogo,
    recalcular_calidad,
)


def lineas_del_reporte(reporte, aviso_catalogo):
    """Resumen legible en español del recálculo."""
    lineas = [
        f"Árboles revisados: {reporte.revisados}",
        f"Publicados: {reporte.publicados}",
        f"En revisión: {reporte.en_revision}",
        f"Cambiaron de estado o de motivos: {reporte.cambiaron}",
    ]
    if aviso_catalogo:
        lineas.append(aviso_catalogo)
    return lineas


class Command(BaseCommand):
    help = "Aplica la regla de calidad a todos los árboles (repetible)."

    def handle(self, *args, **opciones):
        reporte = recalcular_calidad()
        for linea in lineas_del_reporte(reporte, aviso_catalogo_sin_cargar(cargar_catalogo())):
            self.stdout.write(linea)
