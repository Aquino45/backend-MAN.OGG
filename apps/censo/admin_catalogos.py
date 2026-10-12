"""Panel de las tablas de referencia: especies, brigadas (con sus grupos) y sectores.

En especies y brigadas el Administrador hace todo; el Editor agrega, edita y ve (los permisos
vienen de la migración de roles). Cada guardado pasa por `full_clean()` y queda en el historial.
También están aquí las piezas que comparten con el panel de árboles: el mapa centrado en el campus
y las columnas que el árbol toma de su especie.
"""

from django.contrib import admin
from django.contrib.gis.admin.options import GeoModelAdminMixin
from simple_history.admin import SimpleHistoryAdmin

from apps.censo.models import Brigada, Especie, GrupoBrigada, Sector
from apps.censo.servicios.resolver_campos import texto_de_especie
from config.constantes import (
    CAMPO_ORIGEN,
    MAPA_ADMIN_LAT,
    MAPA_ADMIN_LON,
    MAPA_ADMIN_ZOOM,
    TEXTO_ORIGEN_SIN_DATO,
)


class MapaDelCampus(GeoModelAdminMixin):
    """Los mapas del panel abren centrados en el campus (grados WGS 84)."""

    gis_widget_kwargs = {
        "attrs": {
            "default_lon": MAPA_ADMIN_LON,
            "default_lat": MAPA_ADMIN_LAT,
            "default_zoom": MAPA_ADMIN_ZOOM,
        }
    }


class ColumnasDeEspecie:
    """Lo que el árbol toma de su especie, para mostrarlo (de solo lectura) en su panel."""

    @admin.display(description="Nombre común", ordering="especie__nombre_comun")
    def nombre_comun(self, arbol):
        return arbol.especie.nombre_comun if arbol.especie else None

    @admin.display(description="Origen (el de su especie)", ordering="especie__origen__valor")
    def origen_de_la_especie(self, arbol):
        return texto_de_especie(arbol.especie, CAMPO_ORIGEN) or TEXTO_ORIGEN_SIN_DATO


@admin.register(Sector)
class SectorAdmin(MapaDelCampus, SimpleHistoryAdmin):
    """Los sectores se editan (con su geometría) pero no se borran desde el panel."""

    list_display = ("id", "nombre", "provisional")

    def has_delete_permission(self, request, obj=None):
        return False


class _ValidaAlGuardar(SimpleHistoryAdmin):
    """Base: valida el modelo entero al guardar, además del formulario."""

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(Especie)
class EspecieAdmin(_ValidaAlGuardar):
    list_display = ("nombre_cientifico", "nombre_comun", "origen", "ficha_publicada", "revisada")
    list_filter = ("revisada", "ficha_publicada", "forma")
    search_fields = ("nombre_cientifico", "nombre_comun", "alias")
    list_select_related = ("origen",)


class GrupoBrigadaInline(admin.TabularInline):
    model = GrupoBrigada
    extra = 0


@admin.register(Brigada)
class BrigadaAdmin(_ValidaAlGuardar):
    list_display = ("nombre", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre",)
    inlines = [GrupoBrigadaInline]
