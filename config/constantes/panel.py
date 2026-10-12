"""Identidad y listas del panel: títulos, logo, chips, columnas, filtros y avisos."""

import config.constantes.calidad as calidad
import config.constantes.carga as carga

TITULO_ADMIN = "Censo arbóreo UPeU Lima — administración"
"""Encabezado, título del sitio y título del índice del panel de administración."""

CAMPOS_FUERA_DE_LA_REVERSION = (
    "demo",
    "eliminado_en",
    "eliminado_por",
    "motivo_eliminacion",
    "uid",
    "fila_origen",
    "estado_registro",
    "motivos_revision",
)
"""Campos que volver a una versión nunca cambia: se quedan como están hoy. La marca demo se cambia
solo en el formulario de edición, la papelera solo con sus acciones y el estado del registro, solo
con la regla de calidad."""

CAMPO_MOTIVO_ELIMINACION = "motivo_eliminacion"
"""Nombre del campo donde el panel recibe el motivo para mandar árboles a la papelera."""

MENSAJE_MOTIVO_OBLIGATORIO = "Indica el motivo para mandar el árbol a la papelera."
"""Aviso cuando falta el motivo al eliminar."""

MENSAJE_CODIGO_EN_PAPELERA = "El código {codigo} está en la papelera; puede restaurarse."
"""Error al repetir el código de un árbol que está en la papelera."""

MENSAJE_RESTAURADO_SIN_DESTACADO = (
    "El árbol {codigo} volvió sin la marca de destacado: su sector ya tiene {tope} destacados."
)
"""Aviso cuando se restaura un destacado en un sector que ya está lleno."""

AVISO_ARBOL_DE_EJEMPLO = "Dato de ejemplo: este árbol es simulado y no es del censo."
"""Aviso visible en el panel para los árboles con `demo`."""

AYUDA_CO2_ADMIN = (
    "Lo calcula el stakeholder; aquí solo se registra el resultado. Marca «CO₂ simulado» si los "
    "valores son una estimación que se va a reemplazar por el dato real: un árbol de ejemplo con "
    "CO₂ siempre queda marcado y, sin CO₂, la marca se quita sola."
)
"""Ayuda del bloque de CO₂ del formulario del árbol."""

DESCRIPCION_DESTACADO_ADMIN = "Cada sector admite hasta {tope} destacados. El motivo es opcional."
"""Texto del panel sobre el tope de destacados por sector y el motivo opcional."""

NOMBRE_PUBLICO_ADMIN = "Censo arbóreo UPeU Lima"
"""Nombre público completo: título de la pestaña y pantalla de acceso del panel."""

WORDMARK_BARRA_ADMIN = ("Censo", "Arbóreo", "Administración")
"""Nombre junto al símbolo en la barra lateral y en el acceso, como el wordmark del sitio público:
«CENSO» espaciado arriba, «Arbóreo» grande al medio y «ADMINISTRACIÓN» chico debajo."""

HOJA_IDENTIDAD_ADMIN = "admin/censo/identidad.css"
HOJA_COMPONENTES_ADMIN = "admin/censo/componentes.css"
LOGO_ADMIN = "admin/censo/marca/logo-vivero.svg"
FAVICON_ADMIN = "admin/censo/marca/favicon.svg"
"""Archivos estáticos de la identidad del panel (hojas de estilos, logo y favicon)."""

PESOS_ESCALA_COLOR_ADMIN = (50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950)
"""Los 11 tonos de cada escala de color que lee el panel."""

PAGINA_ADMIN = 50
"""Filas por página en las listas del panel."""

VARIANTE_CHIP_PUBLICADO = "publicado"
VARIANTE_CHIP_REVISION = "revision"
VARIANTE_CHIP_EJEMPLO = "ejemplo"
VARIANTE_CHIP_CENSO = "censo"
VARIANTE_CHIP_DESTACADO = "destacado"
VARIANTE_CHIP_ACTIVO = "activo"
VARIANTE_CHIP_INACTIVO = "inactivo"
VARIANTES_CHIP = (
    VARIANTE_CHIP_PUBLICADO,
    VARIANTE_CHIP_REVISION,
    VARIANTE_CHIP_EJEMPLO,
    VARIANTE_CHIP_CENSO,
    VARIANTE_CHIP_DESTACADO,
    VARIANTE_CHIP_ACTIVO,
    VARIANTE_CHIP_INACTIVO,
)
"""Variantes de color de los chips de las listas; cada una tiene su par de colores en la hoja
de identidad del panel."""

VARIANTE_CHIP_POR_ESTADO_REGISTRO = {
    calidad.ESTADO_REGISTRO_PUBLICADO: VARIANTE_CHIP_PUBLICADO,
    calidad.ESTADO_REGISTRO_EN_REVISION: VARIANTE_CHIP_REVISION,
}
"""Variante del chip según el estado del registro de un árbol."""

VARIANTE_CHIP_POR_ESTADO_LOTE = {
    carga.ESTADO_LOTE_VALIDADO: VARIANTE_CHIP_REVISION,
    carga.ESTADO_LOTE_CONFIRMADO: VARIANTE_CHIP_PUBLICADO,
    carga.ESTADO_LOTE_CANCELADO: VARIANTE_CHIP_INACTIVO,
}
"""Variante del chip según el estado de una carga de planilla."""

TEXTOS_CHIPS_ADMIN = {
    "ejemplo": "De ejemplo",
    "censo": "Del censo",
    "destacado": "Destacado",
    "activo": "Activo",
    "inactivo": "Inactivo",
    "ficha_publicada": "Publicada",
    "ficha_sin_publicar": "Sin publicar",
    "revisada": "Revisada",
    "por_revisar": "Por revisar",
    "con_foto": "con foto",
    "sin_foto": "sin foto",
}
"""Textos de los chips y de la miniatura en las listas del panel."""

ETIQUETAS_COLUMNAS_ADMIN = {
    "miniatura": "Foto",
    "ejemplo": "Origen del dato",
    "destacado": "Destacado",
    "ficha": "Ficha de especie",
    "revisada": "Revisión de la especie",
    "activo": "Estado",
    "estado_lote": "Estado de la carga",
    "grupos": "Grupos",
    "arboles": "Árboles",
}
"""Títulos de las columnas que el panel arma por su cuenta."""

ETIQUETAS_FILTROS_ADMIN = {
    "ejemplo": "De ejemplo",
    "destacado": "Destacado",
    "especie": "Especie",
    "grupo": "Grupo de la brigada",
    "sector": "Sector",
}
"""Títulos de los filtros de las listas del panel."""
