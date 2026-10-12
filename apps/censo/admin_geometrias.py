"""Mapa editable del panel: el widget con capas, el contexto, las coordenadas y la marca.

El widget es el de GeoDjango (OpenLayers) con capas de fondo (Esri si hay clave, OpenStreetMap si
no), los sectores y los demás árboles de referencia y la sincronía entre el pin y las coordenadas.
Dos endpoints JSON del propio admin convierten coordenadas y entregan el contexto. La lógica vive
en `servicios/geometrias.py`.
"""

from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.gis.admin.options import GeoModelAdminMixin
from django.contrib.gis.forms import OpenLayersWidget
from django.contrib.gis.geos import Point
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils import timezone

import config.constantes.general as constantes_general
import config.constantes.geometrias as constantes_geometrias
import config.constantes.mapa as constantes_mapa
import config.constantes.permisos as constantes_permisos
from apps.censo.servicios import geometrias

CAMPOS_DEL_MAPA = {
    campo: f"id_{campo}"
    for campo in (
        constantes_mapa.CAMPO_UTM_ESTE_ADMIN,
        constantes_mapa.CAMPO_UTM_NORTE_ADMIN,
        constantes_mapa.CAMPO_LATITUD_ADMIN,
        constantes_mapa.CAMPO_LONGITUD_ADMIN,
    )
}
"""Identificador (en la página) de cada campo que acompaña al pin."""

FIELDSET_UBICACION = (
    "Ubicación",
    {
        "fields": (
            "ubicacion",
            (constantes_mapa.CAMPO_UTM_ESTE_ADMIN, constantes_mapa.CAMPO_UTM_NORTE_ADMIN),
            (constantes_mapa.CAMPO_LATITUD_ADMIN, constantes_mapa.CAMPO_LONGITUD_ADMIN),
            "ubicacion_editada_en_panel",
            "fecha_ubicacion_editada",
        ),
        "description": constantes_mapa.AYUDA_UBICACION_ADMIN,
    },
)
"""Sección «Ubicación» del formulario del árbol."""


# --- el widget ---------------------------------------------------------------------------------


class MapaEditable(OpenLayersWidget):
    """OpenLayers con capas de fondo, contexto de solo lectura y sincronía con las coordenadas."""

    template_name = "admin/censo/mapa/widget.html"
    map_srid = constantes_mapa.SRID_MAPA_ADMIN
    vinculos = None

    def configurar(self, url_convertir, url_contexto, parametros_contexto, campos=None):
        """Las rutas y los campos con que el JavaScript del mapa habla con el panel."""
        self.vinculos = {
            "url_convertir": url_convertir,
            "url_contexto": url_contexto,
            "parametros_contexto": parametros_contexto,
            "campos": campos,
        }

    def get_context(self, name, value, attrs):
        contexto = super().get_context(name, value, attrs)
        capas = geometrias.capas_de_fondo(settings.ESRI_CLAVE)
        contexto["capas"] = capas
        contexto["id_configuracion"] = f"{contexto['id']}_configuracion"
        contexto["ancho_px"], contexto["alto_px"] = (
            constantes_mapa.MAPA_ADMIN_ANCHO_PX,
            constantes_mapa.MAPA_ADMIN_ALTO_PX,
        )
        contexto["configuracion"] = {
            "capas": capas,
            "capa_inicial": capas[0]["id"],
            "zoom_maximo": constantes_mapa.ZOOM_MAXIMO_MAPA_ADMIN,
            "srid_mapa": self.map_srid,
            "estilos": constantes_mapa.ESTILOS_MAPA_ADMIN,
            "textos": constantes_mapa.TEXTOS_MAPA_ADMIN,
            **(self.vinculos or {}),
        }
        return contexto


# --- el formulario del árbol ---------------------------------------------------------------------


def _coordenada(etiqueta):
    return forms.DecimalField(
        label=etiqueta,
        required=False,
        max_digits=constantes_mapa.DIGITOS_FORMULARIO_UTM,
        decimal_places=constantes_mapa.DECIMALES_FORMULARIO_UTM,
    )


class FormularioDeArbol(forms.ModelForm):
    """El árbol con su ubicación por pin o por coordenadas UTM; la latitud y la longitud se leen."""

    utm_este_m = _coordenada(constantes_mapa.ETIQUETA_UTM_ESTE_ADMIN)
    utm_norte_m = _coordenada(constantes_mapa.ETIQUETA_UTM_NORTE_ADMIN)
    latitud = forms.CharField(
        label=constantes_mapa.ETIQUETA_LATITUD_ADMIN, required=False, disabled=True
    )
    longitud = forms.CharField(
        label=constantes_mapa.ETIQUETA_LONGITUD_ADMIN, required=False, disabled=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inicial = self.instance.ubicacion
        self._ubicacion_inicial = inicial.clone() if inicial else None
        self.ubicacion_cambio = False
        if inicial is not None:
            latitud, longitud = geometrias.utm_a_grados(inicial.x, inicial.y)
            decimales = constantes_mapa.DECIMALES_FORMULARIO_UTM
            self.initial[constantes_mapa.CAMPO_UTM_ESTE_ADMIN] = round(
                Decimal(inicial.x), decimales
            )
            self.initial[constantes_mapa.CAMPO_UTM_NORTE_ADMIN] = round(
                Decimal(inicial.y), decimales
            )
            self.initial[constantes_mapa.CAMPO_LATITUD_ADMIN] = f"{latitud:.6f}"
            self.initial[constantes_mapa.CAMPO_LONGITUD_ADMIN] = f"{longitud:.6f}"

    def clean(self):
        datos = super().clean()
        este, norte = (
            datos.get(constantes_mapa.CAMPO_UTM_ESTE_ADMIN),
            datos.get(constantes_mapa.CAMPO_UTM_NORTE_ADMIN),
        )
        if (este is None) != (norte is None):
            raise ValidationError(constantes_geometrias.MENSAJE_PIDE_ESTE_Y_NORTE)
        escritas = {
            constantes_mapa.CAMPO_UTM_ESTE_ADMIN,
            constantes_mapa.CAMPO_UTM_NORTE_ADMIN,
        } & set(self.changed_data)
        if este is not None and escritas:
            datos["ubicacion"] = Point(
                float(este), float(norte), srid=constantes_general.SRID_UTM_CENSO
            )
            self._errors.pop("ubicacion", None)
        nueva = datos.get("ubicacion")
        self.ubicacion_cambio = self._cambio_la_ubicacion(nueva)
        if self.ubicacion_cambio and nueva is not None and not geometrias.esta_en_el_campus(nueva):
            self.add_error(
                "ubicacion",
                constantes_geometrias.MENSAJE_FUERA_DEL_CAMPUS.format(
                    margen_m=constantes_geometrias.MARGEN_CAMPUS_M
                ),
            )
        return datos

    def _cambio_la_ubicacion(self, nueva):
        inicial = self._ubicacion_inicial
        if nueva is None:
            return False
        if inicial is None:
            return True
        return inicial.distance(nueva) > constantes_geometrias.TOLERANCIA_MISMA_UBICACION_M


# --- el admin ----------------------------------------------------------------------------------


class MapaEditableAdmin(GeoModelAdminMixin):
    """Mezcla de los admins con mapa: widget, rutas JSON y configuración del widget por registro."""

    gis_widget = MapaEditable
    gis_widget_kwargs = {
        "attrs": {
            "default_lon": constantes_mapa.MAPA_ADMIN_LON,
            "default_lat": constantes_mapa.MAPA_ADMIN_LAT,
            "default_zoom": constantes_mapa.MAPA_ADMIN_ZOOM,
        }
    }
    campo_del_mapa = "ubicacion"
    parametro_de_contexto = "arbol"
    con_coordenadas = False

    def _nombre(self, sufijo):
        return f"{self.opts.app_label}_{self.opts.model_name}_{sufijo}"

    def get_urls(self):
        vistas = (
            ("mapa/convertir/", self.convertir_coordenadas, "convertir_coordenadas"),
            ("mapa/contexto/", self.contexto_del_mapa, "contexto_del_mapa"),
        )
        propias = [
            path(ruta, self.admin_site.admin_view(vista), name=self._nombre(nombre))
            for ruta, vista, nombre in vistas
        ]
        return [*propias, *super().get_urls()]

    def get_form(self, request, obj=None, change=False, **kwargs):
        formulario = super().get_form(request, obj, change=change, **kwargs)
        campo = formulario.base_fields.get(self.campo_del_mapa)
        if campo is not None and isinstance(campo.widget, MapaEditable):
            registro = {self.parametro_de_contexto: obj.pk} if obj and obj.pk else {}
            campo.widget.configurar(
                reverse(f"admin:{self._nombre('convertir_coordenadas')}"),
                reverse(f"admin:{self._nombre('contexto_del_mapa')}"),
                registro,
                CAMPOS_DEL_MAPA if self.con_coordenadas else None,
            )
        return formulario

    # --- rutas JSON ---------------------------------------------------------------------------

    def convertir_coordenadas(self, request):
        """Convierte UTM a grados (o al revés) y dice si el punto cae en el campus."""
        self._exigir_cambio(request)
        respuesta = geometrias.convertir_parametros(request.GET)
        return JsonResponse(respuesta, status=400 if "utm_este_m" not in respuesta else 200)

    def contexto_del_mapa(self, request):
        """Los sectores y los árboles de referencia, sin el registro que se está editando."""
        self._exigir_cambio(request)
        parametro = request.GET.get(self.parametro_de_contexto)
        try:
            identificador = int(parametro) if parametro else None
        except ValueError:
            identificador = -1
        if identificador is not None and identificador < 0 or not (parametro or "").isascii():
            return JsonResponse(
                {"mensaje": constantes_geometrias.MENSAJE_IDENTIFICADOR_ILEGIBLE}, status=400
            )
        argumentos = {f"{self.parametro_de_contexto}_id": identificador}
        return JsonResponse(geometrias.contexto_del_mapa(**argumentos))

    def _exigir_cambio(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied


class UbicacionDelArbolAdmin(MapaEditableAdmin):
    """El admin de árboles: coordenadas con el pin, marca de ubicación y aviso de sector."""

    con_coordenadas = True
    form = FormularioDeArbol

    def get_readonly_fields(self, request, obj=None):
        """La fecha nunca se edita; la marca, solo quien también edita las fronteras."""
        campos = [*super().get_readonly_fields(request, obj), "fecha_ubicacion_editada"]
        permiso = f"{self.opts.app_label}.{constantes_permisos.PERMISO_EDITAR_MARCA_UBICACION}"
        if not request.user.has_perm(permiso):
            campos.append("ubicacion_editada_en_panel")
        return campos

    def save_model(self, request, obj, form, change):
        """Una ubicación nueva marca el árbol (salvo que la casilla se cambie a la vez) y avisa."""
        cambio = getattr(form, "ubicacion_cambio", False)
        if cambio and "ubicacion_editada_en_panel" not in form.changed_data:
            obj.ubicacion_editada_en_panel = True
            obj.fecha_ubicacion_editada = timezone.now()
        if "ubicacion_editada_en_panel" in form.changed_data:
            obj.fecha_ubicacion_editada = geometrias.fecha_de_la_marca(
                obj.ubicacion_editada_en_panel, timezone.now()
            )
        super().save_model(request, obj, form, change)
        if cambio and obj.ubicacion is not None:
            texto, es_aviso = geometrias.mensaje_de_sector(obj)
            self.message_user(request, texto, messages.WARNING if es_aviso else messages.INFO)


# --- las fronteras del sector --------------------------------------------------------------------


class FormularioDeSector(forms.ModelForm):
    """El sector con vista previa: si el polígono nuevo deja árboles fuera, pide «Guardar igual»."""

    pide_confirmar = False

    def clean(self):
        datos = super().clean()
        nuevo = datos.get("geom")
        if self.instance.pk is None or nuevo is None or "geom" not in self.changed_data:
            return datos
        cuantos = geometrias.contar_arboles_fuera(self.instance.pk, nuevo)
        if cuantos and not self.data.get(constantes_geometrias.CAMPO_GUARDAR_IGUAL):
            self.pide_confirmar = True
            raise ValidationError(geometrias.mensaje_vista_previa(cuantos))
        return datos


class FronterasDelSectorAdmin(MapaEditableAdmin):
    """Los sectores con su frontera editable en el mapa; al guardarla se recalcula su calidad."""

    campo_del_mapa = "geom"
    parametro_de_contexto = "sector"
    form = FormularioDeSector
    change_form_template = "admin/censo/sector/change_form.html"

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        textos = {
            "campo_guardar_igual": constantes_geometrias.CAMPO_GUARDAR_IGUAL,
            "etiqueta_guardar_igual": constantes_geometrias.ETIQUETA_GUARDAR_IGUAL,
        }
        return super().changeform_view(
            request, object_id, form_url, {**textos, **(extra_context or {})}
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change or "geom" not in form.changed_data:
            return
        resultado = geometrias.recalcular_calidad_del_sector(obj)
        if resultado.a_revision:
            aviso = geometrias.mensaje_a_revision(resultado.a_revision)
            self.message_user(request, aviso, messages.WARNING)
