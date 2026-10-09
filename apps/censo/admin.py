"""Admin de GeoDjango para Sector y Arbol."""

from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from apps.censo.models import Arbol, Sector


@admin.register(Sector)
class SectorAdmin(GISModelAdmin):
    list_display = ("id", "nombre", "provisional")


@admin.register(Arbol)
class ArbolAdmin(GISModelAdmin):
    list_display = ("codigo", "sector", "nombre_comun", "nombre_cientifico", "demo")
    list_filter = ("sector", "demo")
    search_fields = ("codigo", "nombre_comun")
    readonly_fields = ("fuente", "fila_origen", "creado_en", "actualizado_en")
