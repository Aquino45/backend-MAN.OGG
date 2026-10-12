"""Carga de la planilla desde el panel: límites, estados del lote, decisiones, textos y mensajes."""

EXTENSION_PLANILLA = ".xlsx"
"""Única extensión que se acepta al subir la planilla."""

TAMANO_MAXIMO_PLANILLA_BYTES = 5 * 1024 * 1024
"""Tope de tamaño del archivo que se sube desde el panel."""

FILAS_MAXIMAS_PLANILLA = 5000
"""Tope de filas que declara la hoja de la planilla subida desde el panel."""

HORAS_VIDA_LOTE_CARGA = 24
"""Horas que un lote validado espera una decisión; después sus filas se descartan."""

ESTADO_LOTE_VALIDADO = "validado"
ESTADO_LOTE_CONFIRMADO = "confirmado"
ESTADO_LOTE_CANCELADO = "cancelado"
ESTADOS_LOTE_CARGA = (
    (ESTADO_LOTE_VALIDADO, "Validado"),
    (ESTADO_LOTE_CONFIRMADO, "Confirmado"),
    (ESTADO_LOTE_CANCELADO, "Cancelado"),
)
"""En qué punto está una carga: validada (esperando decisión), confirmada o cancelada."""

DECISION_CONSERVAR = "conservar"
DECISION_DESCARTAR = "descartar"
DECISION_SIN_DECIDIR = "sin_decidir"
DECISIONES_FILA_CARGA = (
    (DECISION_CONSERVAR, "Conservar"),
    (DECISION_DESCARTAR, "Descartar"),
    (DECISION_SIN_DECIDIR, "Sin decidir"),
)
"""Qué se hace con una fila con problemas."""

CLASIFICACION_LISTO = "listo"
CLASIFICACION_CAMPOS_VACIOS = "campos_vacios"
CLASIFICACION_INCONSISTENTE = "inconsistente"
CLASIFICACION_DUPLICADO = "duplicado"
CLASIFICACIONES_CARGA = (
    (CLASIFICACION_LISTO, "Listo"),
    (CLASIFICACION_CAMPOS_VACIOS, "Con campos vacíos"),
    (CLASIFICACION_INCONSISTENTE, "Inconsistente"),
    (CLASIFICACION_DUPLICADO, "Duplicado"),
)
"""Cómo queda cada fila al validar la planilla. Todas menos «listo» piden una decisión."""

CLASIFICACIONES_CON_PROBLEMA = (
    CLASIFICACION_CAMPOS_VACIOS,
    CLASIFICACION_INCONSISTENTE,
    CLASIFICACION_DUPLICADO,
)
"""Las filas por las que el panel pregunta (alerta, revisión y rama «No»); las listas no."""

TIPO_CAMPO_LISTA = "lista"
TIPO_CAMPO_NUMERO = "numero"
TIPO_CAMPO_TEXTO = "texto"
"""Cómo se edita un campo con problema en la pantalla de revisión."""

PREFIJO_CONSERVAR_CARGA = "conservar-"
PREFIJO_CAMPO_CARGA = "campo-"
CAMPO_ARCHIVO_CARGA = "planilla"
"""Nombres de los controles del formulario de carga (el id de la fila va después del prefijo)."""

LOTES_RECIENTES_EN_CARGA = 10
"""Cuántas cargas anteriores se listan en la pantalla de carga."""

AVISO_UBICACION_DEL_PANEL = "Ubicación corregida en el panel; se mantiene"
"""Aviso cuando la planilla trae otra ubicación para un árbol corregido en el panel."""

TEXTOS_CARGA_PLANILLA = {
    "titulo": "Cargar planilla",
    "ayuda_subir": (
        "Sube el archivo .xlsx de la brigada. Se revisa sin guardar nada: primero ves un resumen."
    ),
    "etiqueta_archivo": "Planilla de la brigada (.xlsx)",
    "boton_subir": "Validar planilla",
    "titulo_resumen": "Resumen de la planilla",
    "boton_si": "Sí",
    "boton_no": "No",
    "boton_confirmar": "Confirmar",
    "boton_incorporar": "Incorporar los registros",
    "boton_guardar": "Guardar e incorporar",
    "boton_cancelar": "Cancelar carga",
    "boton_volver": "Volver",
    "titulo_revision": "Revisar registros con problemas",
    "ayuda_revision": (
        "Corrige lo que quieras y marca «Conservar» en los registros que se incorporan. "
        "Lo conservado que quede completo se publica; lo que siga con problemas entra en revisión. "
        "Lo que no marques no se incorpora. En un código repetido, conserva solo uno."
    ),
    "etiqueta_conservar": "Conservar",
    "titulo_no_incorporar": "Confirmar sin los registros con problemas",
    "titulo_resultado": "Resultado de la carga",
    "columna_codigo": "Código",
    "columna_motivos": "Motivos",
    "columna_campos": "Campos a corregir",
    "texto_en_planilla": "En la planilla: «{valor}»",
    "texto_sin_dato": "(sin dato)",
    "titulo_cargas_anteriores": "Cargas anteriores",
    "texto_sin_cargas": "Todavía no se cargó ninguna planilla.",
    "etiqueta_codigos_publicados": "Publicados",
    "etiqueta_codigos_en_revision": "En revisión",
    "etiqueta_codigos_no_incorporados": "No incorporados",
    "etiqueta_codigos_ejemplo": "De ejemplo sin cambios",
    "etiqueta_codigos_ubicacion_del_panel": AVISO_UBICACION_DEL_PANEL,
    "titulo_avisos": "Avisos de la planilla",
    "texto_sin_registros": "Ninguno",
    "enlace_a_revision": "Ver los registros en revisión",
    "migas_inicio": "Inicio",
    "columna_fecha": "Fecha",
    "columna_archivo": "Archivo",
    "columna_estado": "Estado",
    "columna_filas": "Filas",
    "etiqueta_fila": "fila",
}
"""Textos de las pantallas de «Cargar planilla»."""

FORMATO_RESUMEN_CARGA = (
    "{listos} listos · {vacios} con campos vacíos · {inconsistentes} inconsistentes · "
    "{duplicados} duplicados"
)
FORMATO_ALERTA_PROBLEMAS = (
    "Se detectaron {total} registros inconsistentes o duplicados. ¿Quieres revisarlos?"
)
FORMATO_ALERTA_UN_PROBLEMA = "Se detectó 1 registro inconsistente o duplicado. ¿Quieres revisarlo?"
FORMATO_SIN_PROBLEMAS = "No se detectaron registros inconsistentes ni duplicados."
FORMATO_CODIGO_NUEVO_NO_INCORPORADO = "El árbol {codigo} no está en el registro y no se incorporará"
FORMATO_CODIGO_EXISTENTE_NO_ACTUALIZADO = "{codigo} no se actualiza; se mantiene lo que había"
FORMATO_RESULTADO_CARGA = (
    "{publicados} publicados · {en_revision} en revisión · {no_incorporados} no incorporados · "
    "{ejemplo_sin_cambios} de ejemplo sin cambios"
)
"""Frases de la carga con sus huecos."""

MENSAJE_CARGA_SIN_ARCHIVO = "Elige el archivo .xlsx de la brigada."
MENSAJE_CARGA_NO_ES_XLSX = "El archivo debe ser una planilla de Excel (.xlsx)."
MENSAJE_CARGA_MUY_GRANDE = "El archivo pesa más de {maximo_mb:g} MB; no se puede cargar."
MENSAJE_CARGA_MUCHAS_FILAS = "La hoja declara {filas} filas; el máximo es {maximo}."
MENSAJE_CARGA_LOTE_CERRADO = "Esa carga ya no está pendiente: sube la planilla otra vez."
MENSAJE_CARGA_UN_SOLO_CODIGO = "Conserva solo un registro del código {codigo}."
MENSAJE_CARGA_CANCELADA = "Carga cancelada: no se guardó nada."
"""Errores y avisos de la carga desde el panel."""

FORMATO_FECHA_LOTE_CARGA = "d/m/Y H:i"
"""Cómo se muestra la fecha de una carga en la lista de cargas anteriores."""
