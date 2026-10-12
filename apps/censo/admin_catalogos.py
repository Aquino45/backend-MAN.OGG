"""Panel de las tablas de referencia: especies, brigadas (con sus grupos) y sectores.

En especies y brigadas el Administrador hace todo; el Editor agrega, edita y ve (los permisos
vienen de la migración de roles). Cada guardado pasa por `full_clean()` y queda en el historial.
Los sectores suman el mapa editable de sus fronteras (`admin_geometrias`); aquí también están las
columnas que el árbol toma de su especie.
"""

from django import forms
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.censo.admin_geometrias import FronterasDelSectorAdmin
from apps.censo.models import Brigada, Especie, GrupoBrigada, Sector
from apps.censo.servicios.resolver_campos import texto_de_especie
from apps.censo.servicios.validar_especie import validar_nombres_de_especie
from config.constantes import (
    CAMPO_ORIGEN,
    TEXTO_ORIGEN_SIN_DATO,
)


class ColumnasDeEspecie:
    """Lo que el árbol toma de su especie, para mostrarlo (de solo lectura) en su panel."""

    @admin.display(description="Nombre común", ordering="especie__nombre_comun")
    def nombre_comun(self, arbol):
        return arbol.especie.nombre_comun if arbol.especie else None

    @admin.display(description="Origen (el de su especie)", ordering="especie__origen__valor")
    def origen_de_la_especie(self, arbol):
        return texto_de_especie(arbol.especie, CAMPO_ORIGEN) or TEXTO_ORIGEN_SIN_DATO


@admin.register(Sector)
class SectorAdmin(FronterasDelSectorAdmin, SimpleHistoryAdmin):
    """Los sectores se editan (con su geometría) pero no se borran desde el panel."""

    list_display = ("id", "nombre", "provisional")

    def has_delete_permission(self, request, obj=None):
        return False


class _ValidaAlGuardar(SimpleHistoryAdmin):
    """Base: valida el modelo entero al guardar, además del formulario."""

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)


class EspecieForm(forms.ModelForm):
    """Formulario de la especie: sus nombres y alias no pueden chocar con los de otra."""

    class Meta:
        model = Especie
        fields = (
            "nombre_cientifico",
            "nombre_comun",
            "alias",
            "familia",
            "origen",
            "forma",
            "densidad_madera_g_cm3",
            "fuente_densidad",
            "beneficios",
            "dato_curioso",
            "cuidados",
            "fuente_ficha",
            "ficha_publicada",
            "revisada",
        )

    def clean(self):
        datos = super().clean()
        validar_nombres_de_especie(
            datos.get("nombre_cientifico"), datos.get("alias"), self.instance.pk
        )
        return datos


@admin.register(Especie)
class EspecieAdmin(_ValidaAlGuardar):
    form = EspecieForm
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
