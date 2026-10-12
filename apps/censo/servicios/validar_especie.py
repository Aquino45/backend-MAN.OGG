"""Que los nombres de una especie no choquen con los de otra.

La ingesta busca el texto de la planilla en el nombre científico, el nombre común y el alias de
las especies. Si dos especies comparten uno de esos nombres, el árbol queda sin especie. Aquí se
impide al guardar: el nombre científico no puede ser el alias ni el nombre común de otra especie,
y un alias no puede ser el nombre científico, el nombre común ni el alias de otra. Los nombres
comunes sí pueden repetirse. Se comparan normalizados (sin mayúsculas, tildes ni espacios de más).
"""

from django.core.exceptions import ValidationError

from apps.censo.models import Especie
from apps.censo.servicios.normalizacion import lineas_de, normalizar
from config.constantes.catalogos import MENSAJE_ALIAS_REPETIDO, MENSAJE_NOMBRE_CIENTIFICO_REPETIDO


def _normalizados(nombres):
    return {normalizar(nombre) for nombre in nombres if normalizar(nombre)}


def validar_nombres_de_especie(nombre_cientifico, alias, pk=None):
    """Lanza ValidationError, con el campo y la especie que ya usa el nombre, si hay un choque.

    `pk` es la especie que se guarda (None si es nueva): no choca consigo misma.
    """
    cientifico = normalizar(nombre_cientifico)
    alias_propios = {normalizar(texto): texto for texto in lineas_de(alias)}
    errores = {}
    for otra in Especie.objects.exclude(pk=pk):
        alias_de_otra = _normalizados(lineas_de(otra.alias))
        nombres_de_otra = _normalizados([otra.nombre_cientifico, otra.nombre_comun]) | alias_de_otra
        if cientifico and cientifico in nombres_de_otra:
            errores["nombre_cientifico"] = MENSAJE_NOMBRE_CIENTIFICO_REPETIDO.format(
                nombre=nombre_cientifico, especie=otra
            )
        repetidos = set(alias_propios) & nombres_de_otra
        if repetidos:
            texto = alias_propios[sorted(repetidos)[0]]
            errores["alias"] = MENSAJE_ALIAS_REPETIDO.format(alias=texto, especie=otra)
    if errores:
        raise ValidationError(errores)


def validar_nombres_de_ficha(datos, especie):
    """Lo mismo para la ficha de un archivo de cápsulas; si choca, lanza ValueError."""
    try:
        validar_nombres_de_especie(
            datos["nombre_cientifico"], datos["alias"], None if especie is None else especie.pk
        )
    except ValidationError as error:
        problemas = " ".join(sum(error.message_dict.values(), []))
        raise ValueError(f"Ficha «{datos['nombre_cientifico']}»: {problemas}") from error
