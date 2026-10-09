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
