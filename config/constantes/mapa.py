"""Mapa editable del panel: mosaicos, capas, atribuciones, estilos, textos y campos de ubicación."""

MAPA_ADMIN_LON = -76.8399
"""Longitud (grados WGS 84) del centro del campus: centro de la caja de los 5 sectores."""

MAPA_ADMIN_LAT = -11.9902
"""Latitud (grados WGS 84) del centro del campus."""

MAPA_ADMIN_ZOOM = 16
"""Zoom inicial del mapa del panel: se ve el campus entero."""

ETIQUETA_UBICACION_EDITADA_EN_PANEL = "Ubicación corregida en el panel"
ETIQUETA_FECHA_UBICACION_EDITADA = "Fecha de la corrección de la ubicación"
"""Cómo se llaman en el panel las marcas de una ubicación editada a mano."""

ESRI_URL_MOSAICOS = (
    "https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/"
    "{z}/{y}/{x}?token={clave}"
)
"""Mosaicos de Esri World Imagery (ArcGIS Location Platform); `{clave}` se reemplaza por la clave
del entorno y `{z}/{y}/{x}` los llena el mapa."""

OSM_URL_MOSAICOS = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
"""Mosaicos de OpenStreetMap, la capa de calles y la de respaldo sin clave de Esri."""

ATRIBUCION_ESRI = "Powered by Esri · Esri, Maxar, Earthstar Geographics, and the GIS User Community"
ATRIBUCION_ESRI_URL = "https://www.esri.com"
ATRIBUCION_OSM = "© OpenStreetMap contributors"
ATRIBUCION_OSM_URL = "https://www.openstreetmap.org/copyright"
"""Atribución que se muestra sobre el mapa con cada capa de fondo."""

ID_CAPA_SATELITE = "satelite"
ID_CAPA_CALLES = "calles"
NOMBRE_CAPA_SATELITE = "Satélite"
NOMBRE_CAPA_CALLES = "Calles"
"""Identificador y nombre en el selector de cada capa de fondo."""

ZOOM_MAXIMO_MAPA_ADMIN = 19
"""Zoom máximo de los mosaicos del mapa del panel."""

SRID_MAPA_ADMIN = 3857
"""SRID en que trabaja el mapa del panel (Web Mercator); GeoDjango transforma al guardar."""

CAMPO_UTM_ESTE_ADMIN = "utm_este_m"
CAMPO_UTM_NORTE_ADMIN = "utm_norte_m"
CAMPO_LATITUD_ADMIN = "latitud"
CAMPO_LONGITUD_ADMIN = "longitud"
"""Campos del formulario del árbol que acompañan al pin (no son campos del modelo)."""

ETIQUETA_UTM_ESTE_ADMIN = "UTM Este (m)"
ETIQUETA_UTM_NORTE_ADMIN = "UTM Norte (m)"
ETIQUETA_LATITUD_ADMIN = "Latitud (grados)"
ETIQUETA_LONGITUD_ADMIN = "Longitud (grados)"
AYUDA_UBICACION_ADMIN = (
    "UTM zona 18 Sur. Escribir las coordenadas mueve el pin y mover el pin las llena; la latitud "
    "y la longitud son solo de lectura. Un clic en el mapa coloca el pin."
)
"""Etiquetas y ayuda de la sección «Ubicación» del árbol."""

DECIMALES_FORMULARIO_UTM = 2
DIGITOS_FORMULARIO_UTM = 12
"""Decimales y dígitos de las coordenadas UTM del formulario (centímetros)."""

ESTILOS_MAPA_ADMIN = {
    "sector_contorno": "#ffd54f",
    "sector_grosor_px": 2,
    "sector_texto": "#ffffff",
    "sector_texto_borde": "#212121",
    "arbol_contexto_relleno": "rgba(255, 255, 255, 0.55)",
    "arbol_contexto_borde": "rgba(33, 33, 33, 0.55)",
    "arbol_contexto_radio_px": 3,
    "editable_relleno": "rgba(255, 87, 34, 0.15)",
    "editable_borde": "#ff5722",
    "editable_grosor_px": 3,
    "pin_relleno": "#ff5722",
    "pin_borde": "#ffffff",
    "pin_radio_px": 8,
    "texto_tamano_px": 12,
}
"""Colores y tamaños con que el mapa del panel dibuja el contexto y la geometría que se edita."""

TEXTOS_MAPA_ADMIN = {
    "selector": "Mapa de fondo",
    "convirtiendo": "Convirtiendo coordenadas…",
    "error_conversion": "No se pudo convertir la coordenada.",
    "error_contexto": "No se pudo cargar el contexto del mapa.",
    "contexto": "Los sectores y los demás árboles se ven solo como referencia.",
}
"""Textos que el JavaScript del mapa muestra."""

TIPO_CONTEXTO_SECTOR = "sector"
TIPO_CONTEXTO_ARBOL = "arbol"
"""Valor de `properties.tipo` de cada elemento del contexto GeoJSON del mapa."""

MAPA_ADMIN_ANCHO_PX = 720
MAPA_ADMIN_ALTO_PX = 480
"""Tamaño del mapa en los formularios del panel."""
