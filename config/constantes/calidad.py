"""Calidad del registro: estados, obligatorios, rangos, motivos, ejemplos y CO₂ simulado."""

LETRA_CODIGO_DEMO = "D"
"""Letra del código de los árboles simulados (S02-D001); los reales usan otra letra, p. ej. A."""

PATRON_CODIGO_DEMO = rf"^S\d{{2}}-{LETRA_CODIGO_DEMO}\d{{3}}$"
"""Forma del código de un árbol simulado. Es un caso del PATRON_CODIGO_ARBOL."""

CLAVES_EXTRA_DEMO = frozenset({"lat", "lon", "foto_url", "foto_miniatura_url"})
"""Claves del archivo de árboles simulados que no son campos del modelo (nombres del contrato)."""

ESTADO_REGISTRO_PUBLICADO = "publicado"
"""El registro está completo y consistente: sale en la web."""

ESTADO_REGISTRO_EN_REVISION = "en_revision"
"""El registro está vacío o inconsistente: no sale en la web y se ve en el panel con sus motivos."""

ESTADOS_REGISTRO = (
    (ESTADO_REGISTRO_PUBLICADO, "Publicado"),
    (ESTADO_REGISTRO_EN_REVISION, "En revisión"),
)
"""Opciones del estado del registro, con su nombre para el panel."""

CAMPOS_OBLIGATORIOS_CALIDAD = (
    "tipo_individuo",
    "nombre_comun",
    "nombre_cientifico",
    "identificacion",
    "origen",
    "ubicacion",
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
)
"""Datos de la cartilla que no pueden ir vacíos. Si falta uno, el registro queda en revisión."""

CAMPOS_OPCIONALES_CALIDAD = (
    "foto_archivo",
    "foto_detalle_archivo",
    "observaciones",
    "condicion_conservacion",
    "fecha_registro",
    "motivo_destacado",
)
"""Datos que pueden ir vacíos sin mandar el registro a revisión (también el motivo destacado)."""

CAMPOS_OBLIGATORIOS_SI_NO_ES_EJEMPLO = ()
"""Datos que exige solo un árbol real y no uno de ejemplo (`demo`). Hoy ninguno: el grupo de la
brigada es opcional y nunca manda un árbol a revisión."""

CAMPO_DAP_EXENTO_EN_JUVENIL = "dap_cm"
"""Dato que un juvenil (menos de 1.30 m) no necesita: todavía no se mide el DAP."""

VALOR_TIPO_JUVENIL = "Juvenil <1.30 m (sin DAP)"
"""Valor de `tipo_individuo` del catálogo que corresponde a un juvenil (se compara normalizado)."""

RANGOS_MEDIDAS = {
    "dap_cm": (0, False, 1000),
    "altura_total_m": (0, False, 60),
    "copa_ns_m": (0, True, 50),
    "copa_eo_m": (0, True, 50),
    "co2_almacenado_kg": (0, True, None),
    "co2_captura_anual_kg": (0, True, None),
}
"""Rango válido de cada medida: (mínimo, si el mínimo está incluido, máximo incluido o None)."""

ETIQUETAS_CAMPOS_CALIDAD = {
    "tipo_individuo": "Tipo de individuo",
    "nombre_comun": "Nombre común",
    "nombre_cientifico": "Nombre científico",
    "identificacion": "Identificación",
    "origen": "Origen",
    "condicion_conservacion": "Condición de conservación",
    "ubicacion": "Ubicación",
    "altura_total_m": "Altura total",
    "dap_cm": "DAP",
    "copa_ns_m": "Copa N-S",
    "copa_eo_m": "Copa E-O",
    "estado_general": "Estado general",
    "estado_copa": "Estado de copa",
    "tronco_danos": "Tronco / daños",
    "raices_base": "Raíces / base",
    "interferencia_entorno": "Interferencia / entorno",
    "co2_almacenado_kg": "CO₂ almacenado",
    "co2_captura_anual_kg": "CO₂ capturado anual",
    "brigada": "Brigada",
}
"""Cómo se llama cada dato en los motivos de revisión (lenguaje simple)."""

MOTIVO_FALTA_DATO = "Falta el dato «{etiqueta}»"
MOTIVO_NO_ES_NUMERO = "{etiqueta} no es un número: «{texto}»"
MOTIVO_FUERA_DE_RANGO = "{etiqueta} fuera de rango: {valor} (permitido: {rango})"
MOTIVO_FUERA_DE_CATALOGO = "Valor fuera del catálogo en {etiqueta}: «{valor}»"
MOTIVO_FUERA_DEL_SECTOR = (
    "La ubicación cae a {distancia_m:.1f} m del sector {sector} (se admiten {tolerancia_m} m)"
)
"""Textos de los motivos por los que un registro queda en revisión."""

TEXTO_RANGO_DESDE = "desde {minimo}"
TEXTO_RANGO_MAS_DE = "más de {minimo}"
TEXTO_RANGO_HASTA = "hasta {maximo}"
"""Piezas con que se escribe un rango en un motivo."""

AVISO_CATALOGO_SIN_CARGAR = "Catálogo sin cargar en: {campos}"
"""Aviso cuando un campo con lista desplegable no tiene valores en el catálogo: no se evalúa."""

MOTIVO_DUPLICADO_CODIGO = "el código {codigo} está repetido en la planilla; no se incorporó"
MOTIVO_DUPLICADO_UBICACION = "misma ubicación y misma especie que {otro}; no se incorporó"
"""Por qué el importador no incorpora una fila."""

CLAVES_COMPLETAR_EJEMPLO = frozenset(
    {"codigo", "marcar_ejemplo", "campos", "campos_simulados", "nota_fuente"}
)
"""Claves de un registro del archivo que completa los árboles de ejemplo."""

FORMATO_FUENTE_EJEMPLO = "{nota} (campos simulados: {campos})"
"""Lo que `completar_ejemplo` agrega a la `fuente` de un árbol de ejemplo."""

SEPARADOR_FUENTE = " | "
"""Une las partes de la `fuente` cuando se le agrega una nota."""

ETIQUETA_FILTRO_ESTADO_REGISTRO = "Estado del registro"
ETIQUETA_COLUMNA_ESTADO_REGISTRO = "Estado del registro"
ETIQUETA_BLOQUE_ESTADO_REGISTRO = "Estado del registro"
AYUDA_BLOQUE_ESTADO_REGISTRO = (
    "Lo calcula la regla de calidad al guardar; no se edita. Un registro en revisión no sale en la "
    "web."
)
TEXTO_SIN_MOTIVOS = "Sin motivos: el registro está completo y consistente."
"""Textos del panel sobre el estado del registro."""

MENSAJE_REGISTRO_PUBLICADO = "El árbol {codigo} quedó publicado."
MENSAJE_REGISTRO_EN_REVISION = (
    "El árbol {codigo} quedó en revisión y no sale en la web. Motivos: {motivos}"
)
"""Aviso del panel al guardar un árbol."""

AVISO_INDICE_UN_REGISTRO_EN_REVISION = "1 registro en revisión"
AVISO_INDICE_REGISTROS_EN_REVISION = "{total} registros en revisión"
"""Aviso del índice del panel con el número de registros en revisión."""

ETIQUETA_COLUMNA_MOTIVOS_REVISION = "Motivos de revisión"
LARGO_MOTIVOS_EN_LISTA = 90
TEXTO_ESTADO_SE_CALCULA_AL_GUARDAR = "Se calcula al guardar el árbol."
PLANTILLA_INDICE_ADMIN = "admin/censo/index.html"
"""Textos y plantilla del panel para los motivos de revisión (largo máximo en la lista)."""

MOTIVO_HISTORIAL_RECALCULO_CALIDAD = "Recálculo de la calidad del registro"
"""Motivo que queda en el historial cuando `recalcular_calidad` cambia el estado de un árbol."""

MOTIVO_HISTORIAL_COMPLETAR_EJEMPLO = "Completar datos de ejemplo"
"""Motivo que queda en el historial de cada árbol completado por `completar_ejemplo`."""

PARAMETRO_FILTRO_ESTADO_REGISTRO = "estado_registro"
"""Parámetro de la URL del filtro «Estado del registro» del panel (el índice enlaza a él)."""

CO2_PLANILLA_ES_SIMULADO = True
"""Decisión del stakeholder (11/10/2026): el CO₂ que trae la planilla se muestra como simulado
hasta que llegue el dato real. Ese día se cambia a `False` aquí, o se desmarca en el panel."""

ETIQUETA_CO2_SIMULADO = "CO₂ simulado"
"""Nombre de la casilla de CO₂ simulado en el panel."""
