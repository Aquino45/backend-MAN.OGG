"""Rutas raíz: toda la API cuelga de PREFIJO_API y el admin de ADMIN_RUTA."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from config.constantes import PREFIJO_API

handler404 = "apps.core.excepciones.no_encontrado"
handler500 = "apps.core.excepciones.error_interno"

urlpatterns = [
    path(settings.ADMIN_RUTA, admin.site.urls),
    path(PREFIJO_API, include("apps.core.api.urls")),
    path(PREFIJO_API, include("apps.censo.api.urls")),
]
