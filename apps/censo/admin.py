"""Panel de administración temporal (la v1 usa el admin de Django).

Aquí se ven y se editan árboles y sectores con el mapa, se manda a la papelera en vez de borrar y
cada cambio queda en el historial. Los permisos de cada rol vienen de la migración de grupos.
"""

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.contrib.gis.admin.options import GeoModelAdminMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from apps.censo import admin_capsulas  # noqa: F401  (registra las cápsulas en el panel)
from apps.censo.admin_calidad import (
    FIELDSET_ESTADO_REGISTRO,
    CalidadDelRegistroAdmin,
    FiltroEstadoRegistro,
)
from apps.censo.models import Arbol, ArbolEnPapelera, Sector
from apps.censo.servicios import papelera
from config.constantes import (
    AVISO_ARBOL_DE_EJEMPLO,
    AYUDA_CO2_ADMIN,
    CAMPO_MOTIVO_ELIMINACION,
    CAMPOS_FUERA_DE_LA_REVERSION,
    DESCRIPCION_DESTACADO_ADMIN,
    MAPA_ADMIN_LAT,
    MAPA_ADMIN_LON,
    MAPA_ADMIN_ZOOM,
    MENSAJE_MOTIVO_OBLIGATORIO,
    MENSAJE_RESTAURADO_SIN_DESTACADO,
    PERMISO_CAMBIAR_DEMO,
    TITULO_ADMIN,
    TOPE_DESTACADOS_POR_SECTOR,
)

admin.site.site_header = TITULO_ADMIN
admin.site.site_title = TITULO_ADMIN
admin.site.index_title = TITULO_ADMIN

FormularioDeAcciones = type(
    "FormularioDeAcciones",
    (ActionForm,),
    {
        CAMPO_MOTIVO_ELIMINACION: forms.CharField(
            required=False, label="Motivo (para mandar a la papelera)"
        )
    },
)
"""Barra de acciones del listado de árboles, con el campo del motivo."""


class MapaDelCampus(GeoModelAdminMixin):
    """Los mapas del panel abren centrados en el campus (grados WGS 84)."""

    gis_widget_kwargs = {
        "attrs": {
            "default_lon": MAPA_ADMIN_LON,
            "default_lat": MAPA_ADMIN_LAT,
            "default_zoom": MAPA_ADMIN_ZOOM,
        }
    }


@admin.register(Sector)
class SectorAdmin(MapaDelCampus, SimpleHistoryAdmin):
    """Los sectores se editan (con su geometría) pero no se borran desde el panel."""

    list_display = ("id", "nombre", "provisional")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Arbol)
class ArbolAdmin(CalidadDelRegistroAdmin, MapaDelCampus, SimpleHistoryAdmin):
    """Árboles vigentes. «Eliminar» manda a la papelera: nunca borra la fila."""

    list_display = (
        "codigo",
        "sector",
        "nombre_comun",
        "estado_general",
        "estado_del_registro",
        "motivos_de_revision",
        "destacado",
        "demo",
    )
    list_filter = (
        FiltroEstadoRegistro,
        "sector",
        "estado_general",
        "destacado",
        "demo",
        "co2_simulado",
    )
    search_fields = ("codigo", "nombre_comun", "nombre_cientifico")
    readonly_fields = (
        "tipo_de_dato",
        "bloque_estado_registro",
        "uid",
        "fila_origen",
        "creado_en",
        "actualizado_en",
        "eliminado_en",
        "eliminado_por",
        "motivo_eliminacion",
    )
    action_form = FormularioDeAcciones
    actions = ["mandar_a_la_papelera"]
    fieldsets = (
        FIELDSET_ESTADO_REGISTRO,
        (
            "Identificación",
            {
                "fields": (
                    "tipo_de_dato",
                    ("codigo", "uid"),
                    "sector",
                    "fecha_registro",
                    "brigada",
                    "tipo_individuo",
                    ("nombre_comun", "nombre_cientifico"),
                    "identificacion",
                    "origen",
                    "condicion_conservacion",
                )
            },
        ),
        ("Ubicación", {"fields": ("ubicacion",)}),
        ("Medidas", {"fields": ("altura_total_m", "dap_cm", "copa_ns_m", "copa_eo_m")}),
        (
            "Estado",
            {
                "fields": (
                    "estado_general",
                    "estado_copa",
                    "tronco_danos",
                    "raices_base",
                    "interferencia_entorno",
                    "observaciones",
                )
            },
        ),
        (
            "CO₂",
            {
                "fields": ("co2_almacenado_kg", "co2_captura_anual_kg", "co2_simulado"),
                "description": AYUDA_CO2_ADMIN,
            },
        ),
        (
            "Destacado",
            {
                "fields": ("destacado", "motivo_destacado"),
                "description": DESCRIPCION_DESTACADO_ADMIN.format(tope=TOPE_DESTACADOS_POR_SECTOR),
            },
        ),
        (
            "Trazabilidad",
            {
                "fields": (
                    "fuente",
                    "fila_origen",
                    "demo",
                    "creado_en",
                    "actualizado_en",
                    "eliminado_en",
                    "eliminado_por",
                    "motivo_eliminacion",
                )
            },
        ),
    )

    @admin.display(description="Tipo de dato")
    def tipo_de_dato(self, arbol):
        if arbol.demo:
            return format_html('<p class="errornote">{}</p>', AVISO_ARBOL_DE_EJEMPLO)
        return "Dato del censo"

    def get_readonly_fields(self, request, obj=None):
        """La marca `demo` es de solo lectura para quien no tiene el permiso `cambiar_demo`."""
        campos = list(super().get_readonly_fields(request, obj))
        sin_permiso = not request.user.has_perm(f"{self.opts.app_label}.{PERMISO_CAMBIAR_DEMO}")
        if sin_permiso or self._es_reversion(request):
            campos.append("demo")
        return campos

    def _es_reversion(self, request):
        """True en la pantalla de volver a una versión anterior del historial."""
        coincidencia = request.resolver_match
        nombre = f"{self.opts.app_label}_{self.opts.model_name}_simple_history"
        return coincidencia is not None and coincidencia.url_name == nombre

    def get_form(self, request, obj=None, change=False, **kwargs):
        """Al volver a una versión, lo que no es del formulario se queda como está hoy."""
        if obj is not None and obj.pk is not None and self._es_reversion(request):
            actual = Arbol.todos.get(pk=obj.pk)
            for nombre in CAMPOS_FUERA_DE_LA_REVERSION:
                atributo = Arbol._meta.get_field(nombre).attname
                setattr(obj, atributo, getattr(actual, atributo))
        return super().get_form(request, obj, change=change, **kwargs)

    def get_actions(self, request):
        """Sin el borrado masivo de Django: la acción propia manda a la papelera."""
        acciones = super().get_actions(request)
        acciones.pop("delete_selected", None)
        return acciones

    @admin.action(description="Mandar a la papelera los árboles elegidos", permissions=["delete"])
    def mandar_a_la_papelera(self, request, queryset):
        self.delete_queryset(request, queryset)

    def delete_view(self, request, object_id, extra_context=None):
        """Sin motivo no se manda nada a la papelera: se vuelve a pedir."""
        if request.method == "POST" and not self._motivo(request):
            self.message_user(request, MENSAJE_MOTIVO_OBLIGATORIO, messages.ERROR)
            return HttpResponseRedirect(request.get_full_path())
        contexto = {"campo_motivo": CAMPO_MOTIVO_ELIMINACION, **(extra_context or {})}
        return super().delete_view(request, object_id, contexto)

    def response_delete(self, request, obj_display, obj_id):
        if Arbol.todos.filter(pk=obj_id, eliminado_en__isnull=False).exists():
            self.message_user(
                request, f"{obj_display} está en la papelera; puede restaurarse.", messages.SUCCESS
            )
        return HttpResponseRedirect(reverse("admin:censo_arbol_changelist"))

    def delete_model(self, request, obj):
        try:
            papelera.mover_a_papelera(obj, request.user, self._motivo(request))
        except ValueError as error:
            self.message_user(request, str(error), messages.ERROR)

    def delete_queryset(self, request, queryset):
        motivo = self._motivo(request)
        if not motivo:
            self.message_user(request, MENSAJE_MOTIVO_OBLIGATORIO, messages.ERROR)
            return
        arboles = list(queryset)
        try:
            with transaction.atomic():  # todo o nada: si uno falla, ninguno se mueve
                for arbol in arboles:
                    papelera.mover_a_papelera(arbol, request.user, motivo)
        except ValueError as error:
            self.message_user(request, f"No se movió ninguno. {error}", messages.ERROR)
            return
        self.message_user(request, f"{len(arboles)} árbol(es) en la papelera.", messages.SUCCESS)

    @staticmethod
    def _motivo(request):
        return request.POST.get(CAMPO_MOTIVO_ELIMINACION, "").strip()


@admin.register(ArbolEnPapelera)
class PapeleraAdmin(admin.ModelAdmin):
    """Los árboles eliminados: quién, cuándo y por qué. Se restauran o se eliminan en definitiva."""

    list_display = (
        "codigo",
        "sector",
        "nombre_comun",
        "eliminado_por",
        "eliminado_en",
        "motivo_eliminacion",
    )
    list_filter = ("sector", "demo")
    search_fields = ("codigo", "nombre_comun", "motivo_eliminacion")
    ordering = ("-eliminado_en",)
    actions = ["restaurar"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        """La papelera solo se mira: no se edita (restaurar es una acción aparte)."""
        return False

    def has_restaurar_permission(self, request):
        return request.user.has_perm(f"{self.opts.app_label}.change_arbolenpapelera")

    def get_actions(self, request):
        acciones = super().get_actions(request)
        if "delete_selected" in acciones:
            funcion, nombre, _ = acciones["delete_selected"]
            acciones["delete_selected"] = (funcion, nombre, "Eliminar definitivamente")
        return acciones

    @admin.action(description="Restaurar los árboles elegidos", permissions=["restaurar"])
    def restaurar(self, request, queryset):
        claves = list(queryset.values_list("pk", flat=True))
        for arbol in Arbol.todos.filter(pk__in=claves):
            resultado = papelera.restaurar(arbol, request.user)
            if resultado.perdio_destacado:
                aviso = MENSAJE_RESTAURADO_SIN_DESTACADO.format(
                    codigo=arbol.codigo, tope=TOPE_DESTACADOS_POR_SECTOR
                )
                self.message_user(request, aviso, messages.WARNING)
        self.message_user(request, f"{len(claves)} árbol(es) restaurado(s).", messages.SUCCESS)

    def delete_model(self, request, obj):
        self.delete_queryset(request, [obj])

    def delete_queryset(self, request, queryset):
        """Eliminar en definitiva: se pasa por el servicio para dejar el rastro en el historial."""
        for proxy in list(queryset):
            try:
                papelera.eliminar_definitivamente(Arbol.todos.get(pk=proxy.pk), request.user)
            except ValueError as error:
                self.message_user(request, str(error), messages.ERROR)
