"""Comando: carga o borra los árboles simulados (ver servicios/cargar_demo.py)."""

from django.core.management.base import BaseCommand, CommandError

from apps.censo.servicios.cargar_demo import borrar_demo, cargar_demo


def lineas_del_reporte(reporte):
    """Resumen legible en español del reporte de la carga."""
    lineas = [
        f"Archivo: {reporte.archivo}",
        f"Árboles creados: {reporte.creados}",
        f"Árboles actualizados: {reporte.actualizados}",
        "Destacados por sector:",
    ]
    lineas += [
        f"  Sector {sector}: {total}" for sector, total in reporte.destacados_por_sector.items()
    ]
    lineas.append(f"Árboles fuera de su sector: {len(reporte.fuera_de_sector)}")
    lineas += [
        f"  {a.codigo} (sector {a.sector}): a {a.distancia_m:.2f} m de su polígono"
        for a in reporte.fuera_de_sector
    ]
    return lineas


class Command(BaseCommand):
    help = "Carga los árboles simulados desde un .json (repetible) o los borra con --borrar."

    def add_arguments(self, parser):
        parser.add_argument("ruta", nargs="?", help="Ruta del archivo .json de árboles simulados")
        parser.add_argument(
            "--borrar",
            action="store_true",
            help="Borra en definitivo solo los árboles simulados (nunca los reales)",
        )

    def handle(self, *args, **opciones):
        ruta, borrar = opciones["ruta"], opciones["borrar"]
        if borrar == (ruta is not None):
            raise CommandError("Indica la ruta del archivo o --borrar, pero no ambos ni ninguno.")
        if borrar:
            self.stdout.write(f"Árboles simulados borrados: {borrar_demo()}")
            return
        try:
            reporte = cargar_demo(ruta)
        except ValueError as error:
            raise CommandError(str(error)) from error
        for linea in lineas_del_reporte(reporte):
            self.stdout.write(linea)
