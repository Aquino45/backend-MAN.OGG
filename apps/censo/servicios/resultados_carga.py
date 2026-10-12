"""Lo que devuelve la carga de la planilla: filas evaluadas, avisos y qué pasó al guardar.

Son solo contenedores de datos; `carga_planilla` los llena y la consola y el panel los leen.
"""

from dataclasses import dataclass, field

from apps.censo.servicios.calidad_registro import Motivo
from config.constantes import (
    CLASIFICACION_CAMPOS_VACIOS,
    CLASIFICACION_DUPLICADO,
    CLASIFICACION_INCONSISTENTE,
    CLASIFICACION_LISTO,
    CLASIFICACIONES_CON_PROBLEMA,
)


@dataclass
class ValorNoValido:
    """Un valor de la planilla que no se pudo leer como se esperaba."""

    codigo: str
    columna: str
    texto: str


@dataclass
class ArbolFueraDeSector:
    """Un árbol cuyo punto cae fuera del polígono de su sector."""

    codigo: str
    sector: int
    distancia_m: float


@dataclass
class RegistroEnRevision:
    """Un registro que entró a la BD pero no sale en la web, con sus motivos."""

    codigo: str
    motivos: list[str]


@dataclass
class FilaEvaluada:
    """Una fila ya evaluada: lo que se guardaría, sus motivos y en qué grupo cae."""

    numero_fila: int
    codigo: str
    datos: dict
    valores: dict
    textos_no_numericos: dict
    motivos: list
    clasificacion: str
    codigo_calculado: bool = False
    repetida: bool = False
    duplicado: Motivo | None = None
    duplicado_por_ubicacion: bool = False
    sin_coordenadas: bool = False
    numeros_no_validos: list = field(default_factory=list)
    fechas_no_validas: list = field(default_factory=list)
    fuera_de_catalogo: list = field(default_factory=list)
    fuera_de_sector: list = field(default_factory=list)
    sin_resolver: list = field(default_factory=list)

    @property
    def motivos_a_mostrar(self):
        return [*self.motivos, *([self.duplicado] if self.duplicado else [])]


@dataclass
class Evaluacion:
    """Todas las filas evaluadas; no se escribió nada."""

    nombre_archivo: str
    filas: list = field(default_factory=list)
    catalogo_calidad: dict = field(default_factory=dict)
    catalogo_sin_cargar: str | None = None
    avisos: list[str] = field(default_factory=list)
    """Avisos de toda la planilla (no de una fila), tal como los dejó la lectura."""

    def cuentas(self):
        """Cuántas filas hay de cada clasificación."""
        return {c: sum(f.clasificacion == c for f in self.filas) for c in CLASIFICACIONES_TODAS}

    def con_problema(self):
        return [f for f in self.filas if f.clasificacion in CLASIFICACIONES_CON_PROBLEMA]


CLASIFICACIONES_TODAS = (
    CLASIFICACION_LISTO,
    CLASIFICACION_CAMPOS_VACIOS,
    CLASIFICACION_INCONSISTENTE,
    CLASIFICACION_DUPLICADO,
)


@dataclass
class ResultadoCarga:
    """Qué pasó con cada fila al guardar."""

    creados: int = 0
    actualizados: int = 0
    publicados: list[str] = field(default_factory=list)
    en_revision: list[RegistroEnRevision] = field(default_factory=list)
    no_incorporados: list[str] = field(default_factory=list)
    ejemplo_sin_cambios: list[str] = field(default_factory=list)
    ejemplo_reemplazados: list[str] = field(default_factory=list)
    ubicaciones_del_panel: list[str] = field(default_factory=list)
    """Códigos cuya ubicación, corregida en el panel, se mantuvo frente a otra de la planilla."""

    def como_dict(self):
        """Los códigos de cada grupo, para guardarlos en la bitácora del lote."""
        return {
            "publicados": self.publicados,
            "en_revision": [registro.codigo for registro in self.en_revision],
            "no_incorporados": self.no_incorporados,
            "ejemplo_sin_cambios": self.ejemplo_sin_cambios,
            "ubicaciones_del_panel": self.ubicaciones_del_panel,
        }
