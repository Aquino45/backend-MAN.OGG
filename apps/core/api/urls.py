"""Rutas de la app core."""

from django.urls import path

from apps.core.api.views import salud

urlpatterns = [
    path("salud", salud, name="salud"),
]
