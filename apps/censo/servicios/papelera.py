"""Papelera de árboles: mandar a la papelera, restaurar y eliminar en definitiva.

Nada aquí sabe de HTTP. Cada paso queda en el historial con quién lo hizo y por qué. Los errores
de uso salen como ValueError con un mensaje claro para la persona que usa el panel.
"""

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.censo.models import Arbol
from config.constantes.general import TOPE_DESTACADOS_POR_SECTOR
from config.constantes.panel import MENSAJE_MOTIVO_OBLIGATORIO


@dataclass
class ResultadoRestauracion:
    """El árbol restaurado y si tuvo que volver sin la marca de destacado."""

    arbol: Arbol
    perdio_destacado: bool = False


def mover_a_papelera(arbol, usuario, motivo):
    """Manda el árbol a la papelera con su motivo (obligatorio); la fila no se borra."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError(MENSAJE_MOTIVO_OBLIGATORIO)
    if arbol.eliminado_en is not None:
        raise ValueError(f"El árbol {arbol.codigo} ya está en la papelera.")
    arbol.eliminado_en = timezone.now()
    arbol.eliminado_por = usuario
    arbol.motivo_eliminacion = motivo
    _guardar(arbol, usuario, f"Pasó a la papelera: {motivo}")
    return arbol


def restaurar(arbol, usuario):
    """Saca el árbol de la papelera; si el sector de un destacado está lleno, vuelve sin marca."""
    if arbol.eliminado_en is None:
        raise ValueError(f"El árbol {arbol.codigo} no está en la papelera.")
    arbol.eliminado_en = None
    arbol.eliminado_por = None
    arbol.motivo_eliminacion = None
    perdio_destacado = arbol.destacado and _sector_lleno(arbol)
    if perdio_destacado:
        arbol.destacado = False
        arbol.motivo_destacado = None
    _guardar(arbol, usuario, "Restaurado de la papelera")
    return ResultadoRestauracion(arbol=arbol, perdio_destacado=perdio_destacado)


def eliminar_definitivamente(arbol, usuario=None):
    """Borra en definitiva un árbol que ya está en la papelera.

    Los árboles de ejemplo no se borran desde aquí: se quitan solo con `cargar_demo --borrar`.
    """
    if arbol.eliminado_en is None:
        raise ValueError(f"El árbol {arbol.codigo} no está en la papelera: no se elimina.")
    if arbol.demo:
        raise ValueError(
            f"El árbol {arbol.codigo} es un dato de ejemplo: se quita con cargar_demo --borrar."
        )
    arbol._history_user = usuario
    arbol._change_reason = "Eliminado en definitiva desde la papelera"
    arbol.delete()


def _sector_lleno(arbol):
    """True si el sector ya tiene el tope de destacados vigentes (sin contar este árbol)."""
    otros = Arbol.objects.filter(sector_id=arbol.sector_id, destacado=True).exclude(pk=arbol.pk)
    return otros.count() >= TOPE_DESTACADOS_POR_SECTOR


def _guardar(arbol, usuario, razon):
    """Valida con el modelo y guarda, dejando en el historial el usuario y la razón."""
    arbol._history_user = usuario
    arbol._change_reason = razon
    try:
        arbol.full_clean()
    except ValidationError as error:
        raise ValueError(f"{arbol.codigo}: " + "; ".join(error.messages)) from error
    arbol.save()
