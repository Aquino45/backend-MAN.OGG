"""Configuración del panel con Unfold: nombre, logo, favicon, hoja de estilos y escalas de color.

Las escalas no llevan colores: apuntan a las variables que define la hoja de identidad, que es
el único lugar con la paleta.
"""

from django.templatetags.static import static

from config.constantes import (
    FAVICON_ADMIN,
    HOJA_COMPONENTES_ADMIN,
    HOJA_IDENTIDAD_ADMIN,
    LOGO_ADMIN,
    NOMBRE_PUBLICO_ADMIN,
    PESOS_ESCALA_COLOR_ADMIN,
    TITULO_ADMIN,
)


def _escala(nombre_en_la_hoja):
    return {
        str(peso): f"var(--marca-{nombre_en_la_hoja}-{peso})" for peso in PESOS_ESCALA_COLOR_ADMIN
    }


UNFOLD = {
    "SITE_TITLE": TITULO_ADMIN,
    "SITE_HEADER": NOMBRE_PUBLICO_ADMIN,
    "SITE_LOGO": lambda request: static(LOGO_ADMIN),
    "SITE_FAVICONS": [
        {"rel": "icon", "type": "image/svg+xml", "href": lambda request: static(FAVICON_ADMIN)}
    ],
    "STYLES": [
        lambda request: static(HOJA_IDENTIDAD_ADMIN),
        lambda request: static(HOJA_COMPONENTES_ADMIN),
    ],
    "COLORS": {"base": _escala("base"), "primary": _escala("primario")},
}
