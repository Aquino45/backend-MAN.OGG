"""Planilla de la brigada: hoja, columnas, formatos de lectura y coordenadas que trae."""

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

CAMPOS_DE_UBICACION_PLANILLA = ("utm_este_m", "utm_norte_m")
"""Campos de la planilla que forman la ubicación de un árbol."""

ENCABEZADOS_LATITUD_PLANILLA = ("Latitud", "Lat")
ENCABEZADOS_LONGITUD_PLANILLA = ("Longitud", "Long", "Lon")
"""Encabezados que la planilla puede traer en lugar de «UTM Este (m)» y «UTM Norte (m)». La
primera columna del par ocupa el lugar del este y la segunda el del norte."""

CAMPO_COORDENADAS_NO_RECONOCIDAS = "coordenadas_no_reconocidas"
"""Clave con que la lectura anota en la fila el texto de unas coordenadas no reconocidas."""

FORMATO_COORDENADAS_NO_RECONOCIDAS = "Latitud {primera}; Longitud {segunda}"
"""Cómo se muestra, en el motivo de la fila, lo que traían las columnas de coordenadas."""

TEXTO_CELDA_VACIA_COORDENADAS = "(vacío)"
"""Lo que se muestra de una celda de coordenadas sin valor."""

ENCABEZADO_COORDENADAS_NO_RECONOCIDAS = "Latitud / Longitud"
"""Columna que los reportes nombran cuando las coordenadas no se pudieron leer."""

AVISO_COLUMNAS_COORDENADAS_CON_UTM = (
    "Columnas Latitud/Longitud con valores UTM: se tomaron como UTM"
)
"""Aviso del lote cuando las columnas Latitud/Longitud traen valores de 6 y 7 cifras."""

PATRON_ROTULO_SECTOR_PLANILLA = r"S\s*(\d+)"
"""Rótulo con que la planilla puede nombrar un sector en lugar del número («S01»); sin distinguir
mayúsculas."""
