"""Rutas raíz: toda la API cuelga de PREFIJO_API."""

from django.urls import include, path

from config.constantes import PREFIJO_API

urlpatterns = [
    path(PREFIJO_API, include("apps.core.urls")),
]
