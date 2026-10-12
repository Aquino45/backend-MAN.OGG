"""Mapa editable del panel: el widget con capas, el contexto, las coordenadas y la marca.

El widget es el de GeoDjango (OpenLayers) con capas de fondo (Esri si hay clave, OpenStreetMap si
no), los sectores y los demás árboles de referencia y la sincronía entre el pin y las coordenadas.
Dos endpoints JSON del propio admin convierten coordenadas y entregan el contexto. La lógica vive
en `servicios/geometrias.py`.
"""

from decimal import Decimal, InvalidOperation
from urllib.parse import quote

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

from apps.censo.servicios import geometrias
from config import constantes

CAMPOS_DEL_MAPA = {
    campo: f"id_{campo}"
    for campo in (
        constantes.CAMPO_UTM_ESTE_ADMIN,
        constantes.CAMPO_UTM_NORTE_ADMIN,
        constantes.CAMPO_LATITUD_ADMIN,
        constantes.CAMPO_LONGITUD_ADMIN,
    )
}
"""Identificador (en la página) de cada campo que acompaña al pin."""

FIELDSET_UBICACION = (
    "Ubicación",
    {
        "fields": (
            "ubicacion",
            (constantes.CAMPO_UTM_ESTE_ADMIN, constantes.CAMPO_UTM_NORTE_ADMIN),
            (constantes.CAMPO_LATITUD_ADMIN, constantes.CAMPO_LONGITUD_ADMIN),
            "ubicacion_editada_en_panel",
            "fecha_ubicacion_editada",
        ),
        "description": constantes.AYUDA_UBICACION_ADMIN,
    },
)
"""Sección «Ubicación» del formulario del árbol."""


# --- el widget ---------------------------------------------------------------------------------


class MapaEditable(OpenLayersWidget):
    """OpenLayers con capas de fondo, contexto de solo lectura y sincronía con las coordenadas."""

    template_name = "admin/censo/mapa/widget.html"
    map_srid = constantes.SRID_MAPA_ADMIN
    vinculos = None

    def configurar(self, url_convertir, url_contexto, parametros_contexto, campos=None):
        """Las rutas y los campos con que el JavaScript del mapa habla con el panel."""
        self.vinculos = {
            "url_convertir": url_convertir,
            "url_contexto": url_contexto,
            "parametros_contexto": parametros_contexto,
            "campos": campos,
        }

    def capas(self):
        """Las capas de fondo disponibles: satélite si hay clave de Esri, y siempre las calles."""
        calles = {
            "id": constantes.ID_CAPA_CALLES,
            "nombre": constantes.NOMBRE_CAPA_CALLES,
            "url": constantes.OSM_URL_MOSAICOS,
            "atribucion": constantes.ATRIBUCION_OSM,
            "atribucion_url": constantes.ATRIBUCION_OSM_URL,
        }
        if not settings.ESRI_CLAVE:
            return [calles]
        satelite = {
            "id": constantes.ID_CAPA_SATELITE,
            "nombre": constantes.NOMBRE_CAPA_SATELITE,
            "url": constantes.ESRI_URL_MOSAICOS.replace(
                "{clave}", quote(settings.ESRI_CLAVE, safe="")
            ),
            "atribucion": constantes.ATRIBUCION_ESRI,
            "atribucion_url": constantes.ATRIBUCION_ESRI_URL,
        }
        return [satelite, calles]

    def get_context(self, name, value, attrs):
        contexto = super().get_context(name, value, attrs)
        capas = self.capas()
        contexto["capas"] = capas
        contexto["id_configuracion"] = f"{contexto['id']}_configuracion"
        contexto["ancho_px"], contexto["alto_px"] = (
            constantes.MAPA_ADMIN_ANCHO_PX,
            constantes.MAPA_ADMIN_ALTO_PX,
        )
        contexto["configuracion"] = {
            "capas": capas,
            "capa_inicial": capas[0]["id"],
            "zoom_maximo": constantes.ZOOM_MAXIMO_MAPA_ADMIN,
            "srid_mapa": self.map_srid,
            "estilos": constantes.ESTILOS_MAPA_ADMIN,
            "textos": constantes.TEXTOS_MAPA_ADMIN,
            **(self.vinculos or {}),
        }
        return contexto


# --- el formulario del árbol ---------------------------------------------------------------------


def _coordenada(etiqueta):
    return forms.DecimalField(
        label=etiqueta,
        required=False,
        max_digits=constantes.DIGITOS_FORMULARIO_UTM,
        decimal_places=constantes.DECIMALES_FORMULARIO_UTM,
    )


class FormularioDeArbol(forms.ModelForm):
    """El árbol con su ubicación por pin o por coordenadas UTM; la latitud y la longitud se leen."""

    utm_este_m = _coordenada(constantes.ETIQUETA_UTM_ESTE_ADMIN)
    utm_norte_m = _coordenada(constantes.ETIQUETA_UTM_NORTE_ADMIN)
    latitud = forms.CharField(
        label=constantes.ETIQUETA_LATITUD_ADMIN, required=False, disabled=True
    )
    longitud = forms.CharField(
        label=constantes.ETIQUETA_LONGITUD_ADMIN, required=False, disabled=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inicial = self.instance.ubicacion
        self._ubicacion_inicial = inicial.clone() if inicial else None
        self.ubicacion_cambio = False
        if inicial is not None:
            latitud, longitud = geometrias.utm_a_grados(inicial.x, inicial.y)
            decimales = constantes.DECIMALES_FORMULARIO_UTM
            self.initial[constantes.CAMPO_UTM_ESTE_ADMIN] = round(Decimal(inicial.x), decimales)
            self.initial[constantes.CAMPO_UTM_NORTE_ADMIN] = round(Decimal(inicial.y), decimales)
            self.initial[constantes.CAMPO_LATITUD_ADMIN] = f"{latitud:.6f}"
            self.initial[constantes.CAMPO_LONGITUD_ADMIN] = f"{longitud:.6f}"

    def clean(self):
        datos = super().clean()
        este, norte = (
            datos.get(constantes.CAMPO_UTM_ESTE_ADMIN),
            datos.get(constantes.CAMPO_UTM_NORTE_ADMIN),
        )
        if (este is None) != (norte is None):
            raise ValidationError(constantes.MENSAJE_PIDE_ESTE_Y_NORTE)
        escritas = {constantes.CAMPO_UTM_ESTE_ADMIN, constantes.CAMPO_UTM_NORTE_ADMIN} & set(
            self.changed_data
        )
        if este is not None and escritas:
            datos["ubicacion"] = Point(float(este), float(norte), srid=constantes.SRID_UTM_CENSO)
            self._errors.pop("ubicacion", None)
        nueva = datos.get("ubicacion")
        self.ubicacion_cambio = self._cambio_la_ubicacion(nueva)
        if self.ubicacion_cambio and nueva is not None and not geometrias.esta_en_el_campus(nueva):
            self.add_error(
                "ubicacion",
                constantes.MENSAJE_FUERA_DEL_CAMPUS.format(margen_m=constantes.MARGEN_CAMPUS_M),
            )
        return datos

    def _cambio_la_ubicacion(self, nueva):
        inicial = self._ubicacion_inicial
        if nueva is None:
            return False
        if inicial is None:
            return True
        return inicial.distance(nueva) > constantes.TOLERANCIA_MISMA_UBICACION_M


# --- el admin ----------------------------------------------------------------------------------


def _numero(texto):
    """El texto como número (con coma o punto decimal), o None si falta o no es un número."""
    try:
        numero = Decimal((texto or "").strip().replace(",", "."))
    except InvalidOperation:
        return None
    return float(numero) if numero.is_finite() else None


def _en_rango(numero, rango, excluye_maximo=False):
    if numero is None:
        return False
    minimo, maximo = rango
    return minimo <= numero < maximo if excluye_maximo else minimo <= numero <= maximo


class MapaEditableAdmin(GeoModelAdminMixin):
    """Mezcla de los admins con mapa: widget, rutas JSON y configuración del widget por registro."""

    gis_widget = MapaEditable
    gis_widget_kwargs = {
        "attrs": {
            "default_lon": constantes.MAPA_ADMIN_LON,
            "default_lat": constantes.MAPA_ADMIN_LAT,
            "default_zoom": constantes.MAPA_ADMIN_ZOOM,
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
        este = _numero(request.GET.get(constantes.CAMPO_UTM_ESTE_ADMIN))
        norte = _numero(request.GET.get(constantes.CAMPO_UTM_NORTE_ADMIN))
        latitud = _numero(request.GET.get(constantes.CAMPO_LATITUD_ADMIN))
        longitud = _numero(request.GET.get(constantes.CAMPO_LONGITUD_ADMIN))
        if _en_rango(latitud, constantes.RANGO_LATITUD_VALIDA_GRADOS) and _en_rango(
            longitud, constantes.RANGO_LONGITUD_VALIDA_GRADOS
        ):
            este, norte = geometrias.grados_a_utm(latitud, longitud)
        if not (
            _en_rango(este, constantes.RANGO_UTM_ESTE_M, True)
            and _en_rango(norte, constantes.RANGO_UTM_NORTE_M, True)
        ):
            return JsonResponse({"mensaje": constantes.MENSAJE_COORDENADAS_ILEGIBLES}, status=400)
        descripcion = geometrias.describir_punto(este, norte)
        fuera = not descripcion["dentro_del_campus"]
        mensaje = (
            constantes.MENSAJE_FUERA_DEL_CAMPUS.format(margen_m=constantes.MARGEN_CAMPUS_M)
            if fuera
            else ""
        )
        return JsonResponse({**descripcion, "mensaje": mensaje})

    def contexto_del_mapa(self, request):
        """Los sectores y los árboles de referencia, sin el registro que se está editando."""
        self._exigir_cambio(request)
        parametro = request.GET.get(self.parametro_de_contexto)
        identificador = int(parametro) if parametro and parametro.isdigit() else None
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
        permiso = f"{self.opts.app_label}.{constantes.PERMISO_EDITAR_MARCA_UBICACION}"
        if not request.user.has_perm(permiso):
            campos.append("ubicacion_editada_en_panel")
        return campos

    def save_model(self, request, obj, form, change):
        """Una ubicación nueva marca el árbol (salvo que la casilla se cambie a la vez) y avisa."""
        cambio = getattr(form, "ubicacion_cambio", False)
        if cambio and "ubicacion_editada_en_panel" not in form.changed_data:
            obj.ubicacion_editada_en_panel = True
            obj.fecha_ubicacion_editada = timezone.now()
        super().save_model(request, obj, form, change)
        if cambio and obj.ubicacion is not None:
            self._avisar_sector(request, obj)

    def _avisar_sector(self, request, arbol):
        sector = geometrias.sector_que_contiene(arbol.ubicacion)
        datos = {"codigo": arbol.codigo, "sector_id": arbol.sector_id}
        if sector is None:
            self.message_user(
                request, constantes.MENSAJE_PUNTO_SIN_SECTOR.format(**datos), messages.WARNING
            )
        elif sector.id != arbol.sector_id:
            aviso = constantes.MENSAJE_PUNTO_EN_OTRO_SECTOR.format(cae_en=sector.id, **datos)
            self.message_user(request, aviso, messages.WARNING)
        else:
            self.message_user(
                request, constantes.MENSAJE_PUNTO_EN_SECTOR.format(nombre=sector.nombre, **datos)
            )
