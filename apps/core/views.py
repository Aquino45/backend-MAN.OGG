"""Vistas de la app core. Delgadas: solo comprueban y responden."""

from django.db import OperationalError, connection
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def salud(request):
    """Confirma que la API y la base de datos PostGIS responden."""
    try:
        with connection.cursor():
            version_postgis = connection.ops.postgis_version()
    except OperationalError:
        return Response(
            {"estado": "error", "base_de_datos": "sin conexión"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({"estado": "ok", "base_de_datos": "ok", "postgis": version_postgis})
