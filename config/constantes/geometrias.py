"""Geometría del campus: rangos y márgenes de coordenadas, ubicación de árboles y sectores."""

PROPIEDADES_OBLIGATORIAS_SECTOR = ("id", "nombre", "provisional", "fuente")
"""Propiedades que cada feature del GeoJSON de sectores debe traer."""

TOLERANCIA_FUERA_DE_SECTOR_M = 15
"""Metros que un árbol puede quedar fuera del polígono de su sector: el croquis tiene un error de
5 a 11 m."""

RANGO_LATITUD_CAMPUS_GRADOS = (-12.09, -11.89)
RANGO_LONGITUD_CAMPUS_GRADOS = (-76.94, -76.74)
"""Rango (mínimo, máximo) de grados WGS 84 que se reconoce como el campus: el centro de
`MAPA_ADMIN_LAT` y `MAPA_ADMIN_LON` con 0,1 grados (unos 11 km) a cada lado."""

RANGO_UTM_ESTE_M = (100_000, 1_000_000)
RANGO_UTM_NORTE_M = (1_000_000, 10_000_000)
"""Rango (mínimo incluido, máximo excluido) de un valor UTM: el este tiene 6 cifras y el norte 7."""

TOLERANCIA_MISMA_UBICACION_M = 0.01
"""Metros bajo los cuales dos ubicaciones UTM son la misma (1 cm, como `DECIMALES_UTM`)."""

MARGEN_CAMPUS_M = 200
"""Metros que se admiten alrededor de la caja de los 5 sectores para ubicar un árbol."""

MENSAJE_FUERA_DEL_CAMPUS = (
    "La ubicación está fuera del campus (se admiten hasta {margen_m} m alrededor de los sectores)."
)
MENSAJE_PIDE_ESTE_Y_NORTE = "Escribe el UTM Este y el UTM Norte, o ninguno de los dos."
MENSAJE_COORDENADAS_ILEGIBLES = "Las coordenadas no son números válidos."
"""Errores al ubicar un árbol."""

MENSAJE_PUNTO_EN_SECTOR = "La ubicación de {codigo} cae en el sector {sector_id} ({nombre})."
MENSAJE_PUNTO_EN_OTRO_SECTOR = (
    "La ubicación de {codigo} cae en el sector {cae_en}, pero el árbol sigue registrado en el "
    "sector {sector_id}."
)
MENSAJE_PUNTO_SIN_SECTOR = "La ubicación de {codigo} no cae dentro de ningún sector."
"""Avisos al guardar una ubicación nueva."""

RANGO_LATITUD_VALIDA_GRADOS = (-80, 84)
RANGO_LONGITUD_VALIDA_GRADOS = (-180, 180)
"""Grados que el panel acepta convertir a UTM (los de la proyección UTM)."""

CAMPO_GUARDAR_IGUAL = "guardar_igual"
ETIQUETA_GUARDAR_IGUAL = "Guardar igual"
"""Botón que confirma guardar un sector cuyos árboles quedarían fuera."""

MENSAJE_VISTA_PREVIA_SECTOR_UNO = (
    "{cuantos} árbol quedaría a más de {tolerancia_m} m del sector. "
    "Corrige el polígono o pulsa «Guardar igual»."
)
MENSAJE_VISTA_PREVIA_SECTOR_VARIOS = (
    "{cuantos} árboles quedarían a más de {tolerancia_m} m del sector. "
    "Corrige el polígono o pulsa «Guardar igual»."
)
MENSAJE_SECTOR_A_REVISION_UNO = "{cuantos} árbol quedó fuera del sector y pasó a revisión."
MENSAJE_SECTOR_A_REVISION_VARIOS = (
    "{cuantos} árboles quedaron fuera del sector y pasaron a revisión."
)
"""Vista previa antes de guardar la frontera de un sector y aviso después de guardarla."""

MENSAJE_IDENTIFICADOR_ILEGIBLE = "El identificador del registro no es un número válido."
"""Respuesta del contexto del mapa ante un identificador que no es un entero positivo."""

MOTIVO_HISTORIAL_FRONTERA_SECTOR = "Recálculo por el cambio de las fronteras del sector {sector_id}"
"""Razón con que el historial de un árbol anota su cambio de estado por la frontera del sector."""
