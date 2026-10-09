"""Rutas raíz: toda la API cuelga de PREFIJO_API."""

from django.contrib import admin
from django.urls import include, path

from config.constantes import PREFIJO_API

urlpatterns = [
    path("admin/", admin.site.urls),
    path(PREFIJO_API, include("apps.core.urls")),
]
