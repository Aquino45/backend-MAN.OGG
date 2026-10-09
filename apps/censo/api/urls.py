"""Rutas del censo, colgadas de PREFIJO_API."""

from django.urls import path

from apps.censo.api import views

urlpatterns = [
    path("sectores", views.sectores, name="sectores"),
    path(
        "sectores/<int:sector_id>/arboles",
        views.arboles_de_un_sector,
        name="arboles-de-sector",
    ),
    path("arboles/<str:codigo>", views.arbol, name="arbol"),
]
