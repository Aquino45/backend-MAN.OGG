"""Rutas de la app core."""

from django.urls import path

from apps.core.views import salud

urlpatterns = [
    path("salud", salud, name="salud"),
]
