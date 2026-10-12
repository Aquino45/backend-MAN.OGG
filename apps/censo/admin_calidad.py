"""Panel de la calidad del registro: filtro, columna, bloque de motivos y aviso en el índice.

El estado (`publicado` / `en_revision`) lo calcula la regla de calidad al guardar; el panel solo
lo muestra. El índice avisa cuántos registros están en revisión y si falta cargar el catálogo.
"""

from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.text import Truncator

from apps.censo.models import Arbol
from apps.censo.servicios.calidad_registro import (
    aplicar,
    campos_sin_catalogo,
    cargar_catalogo,
)
from apps.censo.servicios.capsulas import lineas_de
from config.constantes.calidad import (
    AVISO_CATALOGO_SIN_CARGAR,
    AVISO_INDICE_REGISTROS_EN_REVISION,
    AVISO_INDICE_UN_REGISTRO_EN_REVISION,
    AYUDA_BLOQUE_ESTADO_REGISTRO,
    ESTADO_REGISTRO_EN_REVISION,
    ESTADO_REGISTRO_PUBLICADO,
    ESTADOS_REGISTRO,
    ETIQUETA_BLOQUE_ESTADO_REGISTRO,
    ETIQUETA_COLUMNA_ESTADO_REGISTRO,
    ETIQUETA_COLUMNA_MOTIVOS_REVISION,
    ETIQUETA_FILTRO_ESTADO_REGISTRO,
    LARGO_MOTIVOS_EN_LISTA,
    MENSAJE_REGISTRO_EN_REVISION,
    MENSAJE_REGISTRO_PUBLICADO,
    PARAMETRO_FILTRO_ESTADO_REGISTRO,
    PLANTILLA_INDICE_ADMIN,
    TEXTO_ESTADO_SE_CALCULA_AL_GUARDAR,
    TEXTO_SIN_MOTIVOS,
)
from config.constantes.catalogos import ETIQUETAS_DE_CAMPOS_CON_AYUDA
from config.constantes.general import SEPARADOR_DE_LINEAS

FIELDSET_ESTADO_REGISTRO = (
    ETIQUETA_BLOQUE_ESTADO_REGISTRO,
    {"fields": ("bloque_estado_registro",), "description": AYUDA_BLOQUE_ESTADO_REGISTRO},
)
"""Bloque de solo lectura del formulario de un árbol."""


class FiltroEstadoRegistro(admin.SimpleListFilter):
    """Filtra la lista de árboles por publicado o en revisión."""

    title = ETIQUETA_FILTRO_ESTADO_REGISTRO
    parameter_name = PARAMETRO_FILTRO_ESTADO_REGISTRO

    def lookups(self, request, model_admin):
        return ESTADOS_REGISTRO

    def queryset(self, request, queryset):
        if self.value() in dict(ESTADOS_REGISTRO):
            return queryset.filter(estado_registro=self.value())
        return queryset


class CalidadDelRegistroAdmin:
    """Mezcla para el admin de árboles: columnas, bloque de solo lectura y recálculo al guardar."""

    @admin.display(description=ETIQUETA_COLUMNA_ESTADO_REGISTRO, ordering="estado_registro")
    def estado_del_registro(self, arbol):
        return arbol.get_estado_registro_display()

    @admin.display(description=ETIQUETA_COLUMNA_MOTIVOS_REVISION)
    def motivos_de_revision(self, arbol):
        motivos = " · ".join(lineas_de(arbol.motivos_revision))
        return Truncator(motivos).chars(LARGO_MOTIVOS_EN_LISTA)

    @admin.display(description=ETIQUETA_BLOQUE_ESTADO_REGISTRO)
    def bloque_estado_registro(self, arbol):
        if arbol.pk is None:
            return TEXTO_ESTADO_SE_CALCULA_AL_GUARDAR
        motivos = lineas_de(arbol.motivos_revision)
        if not motivos:
            return format_html(
                "<strong>{}</strong>. {}", arbol.get_estado_registro_display(), TEXTO_SIN_MOTIVOS
            )
        lista = format_html_join("", "<li>{}</li>", ((motivo,) for motivo in motivos))
        return format_html(
            "<strong>{}</strong><ul>{}</ul>", arbol.get_estado_registro_display(), lista
        )

    def save_model(self, request, obj, form, change):
        """Aplica la regla antes de guardar y avisa si el árbol quedó publicado o qué le falta."""
        aplicar(obj)
        super().save_model(request, obj, form, change)
        if obj.estado_registro == ESTADO_REGISTRO_PUBLICADO:
            self.message_user(request, MENSAJE_REGISTRO_PUBLICADO.format(codigo=obj.codigo))
            return
        motivos = SEPARADOR_DE_LINEAS.join(lineas_de(obj.motivos_revision))
        aviso = MENSAJE_REGISTRO_EN_REVISION.format(codigo=obj.codigo, motivos=motivos)
        self.message_user(request, aviso, messages.WARNING)


def _aviso_catalogo_sin_cargar():
    """El aviso de catálogo vacío con el nombre legible de cada dato."""
    campos = campos_sin_catalogo(cargar_catalogo())
    nombres = [ETIQUETAS_DE_CAMPOS_CON_AYUDA.get(campo, campo) for campo in campos]
    return AVISO_CATALOGO_SIN_CARGAR.format(campos=", ".join(nombres)) if nombres else None


def contexto_del_indice():
    """Lo que el índice del panel muestra de la calidad: registros en revisión y catálogo vacío."""
    total = Arbol.objects.filter(estado_registro=ESTADO_REGISTRO_EN_REVISION).count()
    aviso_en_revision = None
    if total:
        aviso_en_revision = (
            AVISO_INDICE_UN_REGISTRO_EN_REVISION
            if total == 1
            else AVISO_INDICE_REGISTROS_EN_REVISION.format(total=total)
        )
    enlace = reverse("admin:censo_arbol_changelist")
    filtro = f"{PARAMETRO_FILTRO_ESTADO_REGISTRO}={ESTADO_REGISTRO_EN_REVISION}"
    return {
        "aviso_registros_en_revision": aviso_en_revision,
        "enlace_registros_en_revision": f"{enlace}?{filtro}",
        "aviso_catalogo_sin_cargar": _aviso_catalogo_sin_cargar(),
    }


def _poner_el_aviso_en_el_indice(sitio):
    """El índice del panel recibe el aviso de calidad sin cambiar nada más de Django."""
    indice_de_django = sitio.index

    def indice_con_calidad(request, extra_context=None):
        return indice_de_django(request, {**contexto_del_indice(), **(extra_context or {})})

    sitio.index = indice_con_calidad
    sitio.index_template = PLANTILLA_INDICE_ADMIN


_poner_el_aviso_en_el_indice(admin.site)
