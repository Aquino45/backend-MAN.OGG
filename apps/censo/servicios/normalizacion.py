"""Comparación de textos de la planilla: sin mayúsculas, tildes ni espacios de más.

No toca la BD ni los modelos, así que lo pueden usar los modelos y las migraciones.
"""

import unicodedata

from config.constantes import SEPARADOR_DE_LINEAS


def normalizar(texto):
    """Minúsculas, sin acentos de más y con los espacios colapsados: así se comparan los valores.

    «Bueno», «bueno» y « bueno  » son lo mismo; `None` queda como texto vacío.
    """
    if texto is None:
        return ""
    sin_marcas = "".join(
        letra
        for letra in unicodedata.normalize("NFKD", str(texto))
        if not unicodedata.combining(letra)
    )
    return " ".join(sin_marcas.casefold().split())


def lineas_de(texto):
    """Las líneas con contenido de un texto «uno por línea», sin espacios de más."""
    return [linea.strip() for linea in (texto or "").split(SEPARADOR_DE_LINEAS) if linea.strip()]
