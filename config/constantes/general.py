"""Constantes generales: API, coordenadas, unidades, formato del código y topes comunes."""

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

PATRON_CODIGO_ARBOL = r"^S\d{2}-[A-Z]\d{3}$"
"""Forma del código de un árbol, por ejemplo S01-A001. Es el mismo patrón del contrato."""

TOPE_DESTACADOS_POR_SECTOR = 5
"""Árboles destacados por sector que la administración del censo puede marcar."""

SEPARADOR_DE_LINEAS = "\n"
"""Los alias y los beneficios de una ficha se guardan uno por línea."""

BYTES_POR_MB = 1024 * 1024
"""Para mostrar el tope de tamaño de la planilla en megabytes."""

LARGO_TEXTO = 255
"""Largo máximo de los textos cortos de los modelos (nombres, catálogos, archivos)."""
