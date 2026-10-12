"""Configuración del panel con Unfold: símbolo y nombre de la barra, favicon, estilos y escalas.

Las escalas no llevan colores: apuntan a las variables que define la hoja de identidad, que es
el único lugar con la paleta.
"""

from django.templatetags.static import static
from django.utils.html import format_html

from config.constantes.panel import (
    FAVICON_ADMIN,
    HOJA_COMPONENTES_ADMIN,
    HOJA_IDENTIDAD_ADMIN,
    LOGO_ADMIN,
    PESOS_ESCALA_COLOR_ADMIN,
    TITULO_ADMIN,
    WORDMARK_BARRA_ADMIN,
)


def _escala(nombre_en_la_hoja):
    return {
        str(peso): f"var(--marca-{nombre_en_la_hoja}-{peso})" for peso in PESOS_ESCALA_COLOR_ADMIN
    }


def _wordmark(request):
    """Nombre de la barra en dos líneas, con las clases que le dan el estilo del sitio."""
    censo, arboreo, admin = WORDMARK_BARRA_ADMIN
    return format_html(
        '<span class="wordmark-barra"><span class="wordmark-barra__censo">{}</span> '
        '<span class="wordmark-barra__arboreo">{}</span> '
        '<span class="wordmark-barra__admin">{}</span></span>',
        censo,
        arboreo,
        admin,
    )


UNFOLD = {
    "SITE_TITLE": TITULO_ADMIN,
    "SITE_HEADER": _wordmark,
    "SITE_ICON": lambda request: static(LOGO_ADMIN),
    "SITE_FAVICONS": [
        {"rel": "icon", "type": "image/svg+xml", "href": lambda request: static(FAVICON_ADMIN)}
    ],
    "STYLES": [
        lambda request: static(HOJA_IDENTIDAD_ADMIN),
        lambda request: static(HOJA_COMPONENTES_ADMIN),
    ],
    "COLORS": {"base": _escala("base"), "primary": _escala("primario")},
}
