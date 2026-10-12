"""Catálogos: especies, brigadas, formas de vida y las ayudas y cápsulas del panel."""

CAMPOS_CON_AYUDA = (
    "codigo",
    "tipo_individuo",
    "identificacion",
    "origen",
    "condicion_conservacion",
    "altura_total_m",
    "dap_cm",
    "copa_ns_m",
    "copa_eo_m",
    "estado_general",
    "estado_copa",
    "tronco_danos",
    "raices_base",
    "interferencia_entorno",
    "co2_almacenado_kg",
    "co2_captura_anual_kg",
    "ubicacion",
    "demo",
)
"""Datos de la cartilla que pueden llevar una ayuda «?». No todos son campos de `Arbol` tal cual
(`ubicacion` agrupa las coordenadas)."""

CAMPOS_CATALOGADOS = (
    "tipo_individuo",
    "identificacion",
    "origen",
    "condicion_conservacion",
    "estado_general",
    "estado_copa",
    "tronco_danos",
    "raices_base",
    "interferencia_entorno",
)
"""Campos de `Arbol` con listas desplegables en la planilla: sus valores tienen catálogo."""

ETIQUETAS_DE_CAMPOS_CON_AYUDA = {
    "codigo": "Código",
    "tipo_individuo": "Tipo de individuo",
    "identificacion": "Identificación",
    "origen": "Origen",
    "condicion_conservacion": "Condición de conservación",
    "altura_total_m": "Altura total (m)",
    "dap_cm": "DAP (cm)",
    "copa_ns_m": "Copa norte-sur (m)",
    "copa_eo_m": "Copa este-oeste (m)",
    "estado_general": "Estado general",
    "estado_copa": "Estado de la copa",
    "tronco_danos": "Daños del tronco",
    "raices_base": "Raíces y base",
    "interferencia_entorno": "Interferencia del entorno",
    "co2_almacenado_kg": "CO₂ almacenado (kg)",
    "co2_captura_anual_kg": "CO₂ capturado por año (kg)",
    "ubicacion": "Ubicación",
    "demo": "De ejemplo",
}
"""Nombre legible de cada dato con ayuda o catálogo, para las listas desplegables del panel."""

CLAVES_AYUDA_CAMPO = frozenset({"campo", "titulo", "que_es"})
"""Claves de una ayuda en el archivo de cápsulas."""

CLAVES_VALOR_CATALOGO = frozenset({"campo", "valor", "orden", "explicacion"})
"""Claves de un valor del catálogo en el archivo de cápsulas."""

CLAVES_FICHA_ESPECIE = frozenset(
    {
        "nombre_cientifico",
        "nombre_comun",
        "alias",
        "beneficios",
        "dato_curioso",
        "cuidados",
        "fuente",
        "publicada",
    }
)
"""Claves de una ficha de especie en el archivo de cápsulas."""

TITULO_VALORES_FUERA_DEL_CATALOGO = "Valores fuera del catálogo"
"""Título de la vista del panel con los valores de los árboles que no están en el catálogo."""

AYUDA_VALORES_FUERA_DEL_CATALOGO = (
    "Valores que traen los árboles vigentes y no se pudieron resolver al catálogo: se cuentan tal "
    "cual vinieron en la planilla. Esta vista solo avisa; no cambia árboles."
)
"""Texto de apoyo de la vista de valores fuera del catálogo."""

CAMPO_ORIGEN = "origen"
"""Campo del catálogo con el origen de la especie (nativa, introducida…)."""

CAMPOS_ESTADO_ARBOL = tuple(campo for campo in CAMPOS_CATALOGADOS if campo != CAMPO_ORIGEN)
"""Campos de `Arbol` que son una referencia al catálogo; el origen va por la especie."""

CAMPOS_DE_ESPECIE = ("nombre_comun", "nombre_cientifico", CAMPO_ORIGEN)
"""Datos que el árbol toma de su especie (la planilla los trae como texto)."""

CAMPO_BRIGADA = "brigada"
"""Columna de la planilla con la brigada (o con el nombre de un grupo)."""

CAMPO_GRUPO = "grupo"
"""Columna opcional de la planilla con el grupo de la brigada; el árbol guarda una referencia."""

TITULO_SIN_RESOLVER_CATALOGO = "Textos sin resolver (quedan en valores_originales)"
TITULO_SIN_RESOLVER_BRIGADA = "Brigada o grupo sin resolver (solo informativo, no manda a revisión)"
"""Títulos del reporte de la consola para lo que la planilla trae y no coincide con una tabla."""

CAMPOS_TEXTO_RESUELTOS = (*CAMPOS_DE_ESPECIE, *CAMPOS_ESTADO_ARBOL, CAMPO_BRIGADA)
"""Datos que la planilla trae como texto y el árbol guarda como referencia a otra tabla."""

FORMA_ARBOL = "arbol"
FORMA_PALMA = "palma"
FORMA_ARBUSTO = "arbusto"
FORMAS_ESPECIE = (
    (FORMA_ARBOL, "Árbol"),
    (FORMA_PALMA, "Palma"),
    (FORMA_ARBUSTO, "Arbusto"),
)
"""Formas de vida de una especie, con su nombre para el panel."""

DIGITOS_DENSIDAD_MADERA = 6
DECIMALES_DENSIDAD_MADERA = 3
"""Tamaño del campo `densidad_madera_g_cm3` (g/cm³)."""

MOTIVO_ESPECIE_NO_REGISTRADA = "Especie no registrada: «{texto}»"
"""Motivo cuando el nombre de la especie no coincide con una sola especie registrada."""

CAMPO_MOTIVO_ESPECIE = "nombre_cientifico"
"""Campo al que apunta el motivo de especie no registrada."""

ALIAS_INICIALES_DE_ESPECIES = {
    "Schinus molle": ("Schinus", "Schinus Molle"),
    "Roystonea regia": ("Roystonea",),
    "Prosopis pallida": ("Prosopis Pallida",),
}
"""Otros nombres con que llegan estas especies en la planilla (los siembra la migración)."""

NOMBRE_BRIGADA_INICIAL = "Brigada A"
"""Única brigada del censo hoy: todos los grupos son de ella."""

GRUPOS_INICIALES_DE_BRIGADA = ("Sopita", "zapatito", "zapato")
"""Grupos de la brigada tal como vienen en la planilla del stakeholder."""

TEXTO_ORIGEN_SIN_DATO = "Sin dato"
"""Lo que el panel del árbol muestra de origen si su especie no tiene origen (o no hay especie)."""

MENSAJE_ALIAS_REPETIDO = "El alias «{alias}» ya es un nombre o un alias de la especie {especie}."
MENSAJE_NOMBRE_CIENTIFICO_REPETIDO = (
    "El nombre científico «{nombre}» ya es un nombre o un alias de la especie {especie}."
)
MENSAJE_FICHA_PUBLICADA_INCOMPLETA = (
    "Una ficha publicada necesita el nombre común, los beneficios y la fuente de la ficha."
)
"""Errores de validación de una especie."""
