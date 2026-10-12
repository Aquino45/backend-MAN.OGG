"""Panel de las especies y las brigadas (con sus grupos).

El Administrador hace todo; el Editor agrega, edita y ve (los permisos vienen de la migración de
roles). Cada guardado pasa por `full_clean()` y queda en el historial.
"""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.censo.models import Brigada, Especie, GrupoBrigada


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
