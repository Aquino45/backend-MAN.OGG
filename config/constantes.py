"""Constantes de negocio del back. Lo que no es secreto ni del entorno vive aquí."""

PREFIJO_API = "api/v1/"
"""Prefijo de todas las rutas de la API; termina en barra."""

SRID_UTM_CENSO = 32718
"""SRID de los datos de la brigada: UTM zona 18 Sur (WGS 84)."""

SRID_MAPA = 4326
"""SRID de salida para el mapa: WGS 84 en longitud y latitud."""

DECIMALES_COORDENADAS = 6
"""Decimales de las coordenadas WGS 84 que entrega la API (unos 0,1 m en el terreno)."""

DECIMALES_UTM = 2
"""Decimales de las coordenadas UTM que entrega la cartilla, en metros (1 cm)."""

M2_POR_HECTAREA = 10_000
"""Metros cuadrados en una hectárea."""

PROPIEDADES_OBLIGATORIAS_SECTOR = ("id", "nombre", "provisional", "fuente")
"""Propiedades que cada feature del GeoJSON de sectores debe traer."""

PATRON_CODIGO_ARBOL = r"^S\d{2}-[A-Z]\d{3}$"
"""Forma del código de un árbol, por ejemplo S01-A001. Es el mismo patrón del contrato."""

HOJA_PLANILLA = "Registro_Campo"
"""Nombre de la hoja de la planilla de la brigada donde viven los registros."""

COLUMNAS_PLANILLA = {
    "Código árbol": "codigo",
    "Sector": "sector",
    "Fecha": "fecha_registro",
    "Brigada": "brigada",
    "Tipo de individuo": "tipo_individuo",
    "Nombre común": "nombre_comun",
    "Nombre científico": "nombre_cientifico",
    "Identificación": "identificacion",
    "Origen": "origen",
    "Condición de conservación": "condicion_conservacion",
    "UTM Este (m)": "utm_este_m",
    "UTM Norte (m)": "utm_norte_m",
    "Altura total (m)": "altura_total_m",
    "DAP (cm)": "dap_cm",
    "Diámetro copa N-S (m)": "copa_ns_m",
    "Diámetro copa E-O (m)": "copa_eo_m",
    "Estado general": "estado_general",
    "Estado de copa": "estado_copa",
    "Tronco / daños": "tronco_danos",
    "Raíces / base": "raices_base",
    "Interferencia / entorno": "interferencia_entorno",
    "Foto árbol": "foto_archivo",
    "Foto detalle": "foto_detalle_archivo",
    "Observaciones": "observaciones",
    "Control de registro": "control_registro",
    "CO₂ almacenado (kg CO₂e)": "co2_almacenado_kg",
    "CO₂ capturado anual (kg CO₂/año)": "co2_captura_anual_kg",
}
"""Encabezado exacto de la hoja -> campo del modelo. Es el único lugar con nombres de columna.

`control_registro` se lee pero no se guarda: es una fórmula de control, no un dato del árbol.
"""

COLUMNAS_OPCIONALES_PLANILLA = {
    "Grupo": "grupo",
}
"""Columnas que la planilla puede traer o no: sin ellas se lee igual. Las demás columnas que no
están aquí ni en `COLUMNAS_PLANILLA` se ignoran."""

CAMPOS_NUMERICOS_PLANILLA = frozenset(
    {"altura_total_m", "dap_cm", "copa_ns_m", "copa_eo_m", "co2_almacenado_kg"}
    | {"co2_captura_anual_kg", "utm_este_m", "utm_norte_m"}
)
"""Campos de la planilla que deben ser números."""

CAMPOS_CON_NOTA_PLANILLA = frozenset({"dap_cm", "copa_ns_m", "copa_eo_m"})
"""Campos cuyo texto no numérico (p. ej. «muerto») se conserva como nota en `observaciones`."""

FORMATO_CODIGO_CALCULADO = "S{sector:02d}-A{orden:03d}"
"""Misma regla de la fórmula de la planilla: sector con 2 dígitos y orden en el sector con 3."""

FORMATO_NOTA_PLANILLA = "{encabezado} en planilla: {texto}"
"""Texto que se agrega a `observaciones` cuando DAP o copa no son números."""

SEPARADOR_NOTAS = "; "
"""Une las observaciones de la fila con las notas de la importación."""

FORMATOS_FECHA_PLANILLA = ("%d/%m/%Y", "%Y-%m-%d")
"""Formatos aceptados cuando la fecha viene como texto."""

FILA_ENCABEZADOS_PLANILLA = 1
"""Fila de la hoja donde están los encabezados."""

TOPE_DESTACADOS_POR_SECTOR = 5
"""Árboles destacados por sector que la administración del censo puede marcar."""

LETRA_CODIGO_DEMO = "D"
"""Letra del código de los árboles simulados (S02-D001); los reales usan otra letra, p. ej. A."""

PATRON_CODIGO_DEMO = rf"^S\d{{2}}-{LETRA_CODIGO_DEMO}\d{{3}}$"
"""Forma del código de un árbol simulado. Es un caso del PATRON_CODIGO_ARBOL."""

CLAVES_EXTRA_DEMO = frozenset({"lat", "lon", "foto_url", "foto_miniatura_url"})
"""Claves del archivo de árboles simulados que no son campos del modelo (nombres del contrato)."""

NOMBRE_ROL_ADMINISTRADOR = "Administrador"
"""Grupo del panel con todo sobre árboles y sectores, la papelera completa y la marca demo."""

NOMBRE_ROL_EDITOR = "Editor"
"""Grupo del panel que crea y edita árboles, los manda a la papelera y los restaura."""

PERMISO_CAMBIAR_DEMO = "cambiar_demo"
"""Permiso propio de Arbol: solo quien lo tiene cambia la marca `demo`."""

PERMISOS_POR_ROL = {
    NOMBRE_ROL_ADMINISTRADOR: (
        "add_arbol",
        "change_arbol",
        "delete_arbol",
        "view_arbol",
        PERMISO_CAMBIAR_DEMO,
        "add_sector",
        "change_sector",
        "view_sector",
        "view_arbolenpapelera",
        "change_arbolenpapelera",
        "delete_arbolenpapelera",
    ),
    NOMBRE_ROL_EDITOR: (
        "add_arbol",
        "change_arbol",
        "delete_arbol",
        "view_arbol",
        "view_sector",
        "view_arbolenpapelera",
        "change_arbolenpapelera",
    ),
}
"""Permisos de cada rol. `delete_arbol` solo manda a la papelera; borrar en definitiva es
`delete_arbolenpapelera`. Los sectores nunca se borran desde el panel."""

TITULO_ADMIN = "Censo arbóreo UPeU Lima — administración"
"""Encabezado, título del sitio y título del índice del panel de administración."""

MAPA_ADMIN_LON = -76.8399
"""Longitud (grados WGS 84) del centro del campus: centro de la caja de los 5 sectores."""

MAPA_ADMIN_LAT = -11.9902
"""Latitud (grados WGS 84) del centro del campus."""

MAPA_ADMIN_ZOOM = 16
"""Zoom inicial del mapa del panel: se ve el campus entero."""

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

_PERMISOS_DE_CAPSULAS = ("ayudacampo", "valorcatalogo")

PERMISOS_CAPSULAS_POR_ROL = {
    NOMBRE_ROL_ADMINISTRADOR: tuple(
        f"{accion}_{modelo}"
        for modelo in _PERMISOS_DE_CAPSULAS
        for accion in ("add", "change", "delete", "view")
    ),
    NOMBRE_ROL_EDITOR: tuple(
        f"{accion}_{modelo}"
        for modelo in _PERMISOS_DE_CAPSULAS
        for accion in ("add", "change", "view")
    ),
}
"""Permisos de las ayudas y el catálogo. Ambos roles agregan, editan y ven; solo el Administrador
borra. La ficha de una especie se edita con la especie (`PERMISOS_CATALOGOS_POR_ROL`)."""

SEPARADOR_DE_LINEAS = "\n"
"""Los alias y los beneficios de una ficha se guardan uno por línea."""

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
    "Valores que usan los árboles vigentes y todavía no están en el catálogo. La comparación es "
    "exacta: «bueno» y «Bueno» aparecen por separado. Esta vista solo avisa; no cambia árboles."
)
"""Texto de apoyo de la vista de valores fuera del catálogo."""

# --- Calidad del registro (BE-012) ------------------------------------------------------------

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

TOLERANCIA_FUERA_DE_SECTOR_M = 15
"""Metros que un árbol puede quedar fuera del polígono de su sector: el croquis tiene un error de
5 a 11 m."""

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

DESCRIPCION_DESTACADO_ADMIN = "Cada sector admite hasta {tope} destacados. El motivo es opcional."
"""Texto del panel sobre el tope de destacados por sector y el motivo opcional."""

CO2_PLANILLA_ES_SIMULADO = True
"""Decisión del stakeholder (11/10/2026): el CO₂ que trae la planilla se muestra como simulado
hasta que llegue el dato real. Ese día se cambia a `False` aquí, o se desmarca en el panel."""

ETIQUETA_CO2_SIMULADO = "CO₂ simulado"
"""Nombre de la casilla de CO₂ simulado en el panel."""

# --- Cargar planilla desde el panel ----------------------------------------------------------

PERMISO_CARGAR_PLANILLA = "cargar_planilla"
"""Permiso propio de LoteCarga: quien lo tiene ve «Cargar planilla» en el panel."""

PERMISOS_CARGA_POR_ROL = {
    NOMBRE_ROL_ADMINISTRADOR: (PERMISO_CARGAR_PLANILLA,),
    NOMBRE_ROL_EDITOR: (PERMISO_CARGAR_PLANILLA,),
}
"""Ambos roles cargan la planilla."""

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

CAMPOS_DE_UBICACION_PLANILLA = ("utm_este_m", "utm_norte_m")
"""Campos de la planilla que forman la ubicación de un árbol."""

PREFIJO_CONSERVAR_CARGA = "conservar-"
PREFIJO_CAMPO_CARGA = "campo-"
CAMPO_ARCHIVO_CARGA = "planilla"
"""Nombres de los controles del formulario de carga (el id de la fila va después del prefijo)."""

LOTES_RECIENTES_EN_CARGA = 10
"""Cuántas cargas anteriores se listan en la pantalla de carga."""

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

BYTES_POR_MB = 1024 * 1024
"""Para mostrar el tope de tamaño de la planilla en megabytes."""

FORMATO_FECHA_LOTE_CARGA = "d/m/Y H:i"
"""Cómo se muestra la fecha de una carga en la lista de cargas anteriores."""

# --- Especies, estados del catálogo y brigadas -------------------------------------------------

LARGO_TEXTO = 255
"""Largo máximo de los textos cortos de los modelos (nombres, catálogos, archivos)."""

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

_PERMISOS_DE_CATALOGOS = ("especie", "brigada", "grupobrigada")

PERMISOS_CATALOGOS_POR_ROL = {
    NOMBRE_ROL_ADMINISTRADOR: tuple(
        f"{accion}_{modelo}"
        for modelo in _PERMISOS_DE_CATALOGOS
        for accion in ("add", "change", "delete", "view")
    ),
    NOMBRE_ROL_EDITOR: tuple(
        f"{accion}_{modelo}"
        for modelo in _PERMISOS_DE_CATALOGOS
        for accion in ("add", "change", "view")
    ),
}
"""Permisos de especies, brigadas y grupos: el Administrador hace todo; el Editor agrega, edita y
ve."""

MENSAJE_ALIAS_REPETIDO = "El alias «{alias}» ya lo tiene la especie {especie}."
MENSAJE_FICHA_PUBLICADA_INCOMPLETA = (
    "Una ficha publicada necesita el nombre común, los beneficios y la fuente de la ficha."
)
"""Errores de validación de una especie."""
