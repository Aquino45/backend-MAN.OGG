"""Formato único de errores: siempre `{"detail": "<texto en español>"}`, sin trazas."""

import logging

from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)

DETALLE_NO_ENCONTRADO = "No encontrado."
"""Texto de toda respuesta 404, de DRF o de una ruta que no existe."""

DETALLE_ERROR_INTERNO = "Error interno del servidor."
"""Texto de toda respuesta 500: nunca lleva el mensaje ni la traza del fallo."""

SEPARADOR_MENSAJES = " "
"""Une los mensajes cuando una validación trae varios."""


def _textos(contenido):
    """Recorre el contenido de un error de DRF y devuelve todos sus mensajes."""
    if isinstance(contenido, dict):
        for valor in contenido.values():
            yield from _textos(valor)
    elif isinstance(contenido, (list, tuple)):
        for elemento in contenido:
            yield from _textos(elemento)
    else:
        yield str(contenido)


def manejar_excepcion(exc, context):
    """Manejador de DRF: todo error sale como `{"detail": ...}`; lo inesperado es un 500 limpio."""
    respuesta = exception_handler(exc, context)
    if respuesta is None:
        logger.exception("Error no controlado en la API", exc_info=exc)
        return Response(
            {"detail": DETALLE_ERROR_INTERNO},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if not (isinstance(respuesta.data, dict) and list(respuesta.data) == ["detail"]):
        respuesta.data = {"detail": SEPARADOR_MENSAJES.join(_textos(respuesta.data))}
    return respuesta


def no_encontrado(request, exception):
    """`handler404` de Django: una ruta que no existe responde JSON, no una página HTML."""
    return JsonResponse({"detail": DETALLE_NO_ENCONTRADO}, status=status.HTTP_404_NOT_FOUND)


def error_interno(request):
    """`handler500` de Django: un fallo fuera de DRF también sale como JSON sin detalles."""
    return JsonResponse(
        {"detail": DETALLE_ERROR_INTERNO}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
