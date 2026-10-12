"""Piezas compartidas de las listas del panel: chips, miniatura y filtros.

Los chips son `<span class="chip chip--variante">`; su variante sale de las constantes.
"""

from django.contrib import admin
from django.template.loader import render_to_string
from django.utils.html import format_html

from config.constantes.calidad import ESTADOS_REGISTRO
from config.constantes.panel import (
    ETIQUETAS_COLUMNAS_ADMIN,
    ETIQUETAS_FILTROS_ADMIN,
    TEXTOS_CHIPS_ADMIN,
    VARIANTE_CHIP_ACTIVO,
    VARIANTE_CHIP_CENSO,
    VARIANTE_CHIP_DESTACADO,
    VARIANTE_CHIP_EJEMPLO,
    VARIANTE_CHIP_INACTIVO,
    VARIANTE_CHIP_POR_ESTADO_LOTE,
    VARIANTE_CHIP_POR_ESTADO_REGISTRO,
    VARIANTE_CHIP_PUBLICADO,
    VARIANTE_CHIP_REVISION,
)

PLANTILLA_GLIFO_PIXEL = "admin/censo/glifo_pixel.html"


def chip(texto, variante):
    """Un chip de color para una celda de la lista."""
    return format_html('<span class="chip chip--{}">{}</span>', variante, texto)


def chip_si_no(valor, texto_si, texto_no, variante_si, variante_no):
    return chip(texto_si, variante_si) if valor else chip(texto_no, variante_no)


def filtro_relacionado(campo, clave_de_titulo):
    """Par (campo, filtro) con el título del filtro tomado de las constantes."""

    class Filtro(admin.RelatedOnlyFieldListFilter):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.title = ETIQUETAS_FILTROS_ADMIN[clave_de_titulo]

    return (campo, Filtro)


class ChipsDeEstado:
    """Columnas con chips para el árbol: estado del registro, de ejemplo, destacado y miniatura."""

    @admin.display(description="Estado del registro", ordering="estado_registro")
    def chip_estado_registro(self, arbol):
        nombres = dict(ESTADOS_REGISTRO)
        variante = VARIANTE_CHIP_POR_ESTADO_REGISTRO.get(arbol.estado_registro)
        return chip(nombres.get(arbol.estado_registro, arbol.estado_registro), variante)

    @admin.display(description=ETIQUETAS_COLUMNAS_ADMIN["ejemplo"], ordering="demo")
    def chip_ejemplo(self, arbol):
        return chip_si_no(
            arbol.demo,
            TEXTOS_CHIPS_ADMIN["ejemplo"],
            TEXTOS_CHIPS_ADMIN["censo"],
            VARIANTE_CHIP_EJEMPLO,
            VARIANTE_CHIP_CENSO,
        )

    @admin.display(description=ETIQUETAS_COLUMNAS_ADMIN["destacado"], ordering="destacado")
    def chip_destacado(self, arbol):
        if not arbol.destacado:
            return ""
        return chip(TEXTOS_CHIPS_ADMIN["destacado"], VARIANTE_CHIP_DESTACADO)

    @admin.display(description=ETIQUETAS_COLUMNAS_ADMIN["miniatura"], ordering="foto_archivo")
    def miniatura(self, arbol):
        """El árbol pixel y, si el árbol tiene foto, la etiqueta «con foto»."""
        tiene_foto = bool(arbol.foto_archivo or arbol.foto_detalle_archivo)
        texto = TEXTOS_CHIPS_ADMIN["con_foto" if tiene_foto else "sin_foto"]
        return format_html(
            '<span class="miniatura">{} <small>{}</small></span>',
            render_to_string(PLANTILLA_GLIFO_PIXEL),
            texto,
        )


def chip_activo(activo):
    return chip_si_no(
        activo,
        TEXTOS_CHIPS_ADMIN["activo"],
        TEXTOS_CHIPS_ADMIN["inactivo"],
        VARIANTE_CHIP_ACTIVO,
        VARIANTE_CHIP_INACTIVO,
    )


def chip_de_lote(lote):
    return chip(lote.get_estado_display(), VARIANTE_CHIP_POR_ESTADO_LOTE[lote.estado])


def chip_de_revision(revisada):
    return chip_si_no(
        revisada,
        TEXTOS_CHIPS_ADMIN["revisada"],
        TEXTOS_CHIPS_ADMIN["por_revisar"],
        VARIANTE_CHIP_PUBLICADO,
        VARIANTE_CHIP_REVISION,
    )


def chip_de_ficha(publicada):
    return chip_si_no(
        publicada,
        TEXTOS_CHIPS_ADMIN["ficha_publicada"],
        TEXTOS_CHIPS_ADMIN["ficha_sin_publicar"],
        VARIANTE_CHIP_PUBLICADO,
        VARIANTE_CHIP_INACTIVO,
    )
