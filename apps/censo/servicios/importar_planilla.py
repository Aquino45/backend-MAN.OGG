"""Importa la planilla de la brigada (hoja Registro_Campo). Se puede repetir sin duplicar.

Es la carga de la consola: lee, evalúa y aplica todo (`carga_planilla`). No descarta nada por
calidad: cada registro pasa por la regla y entra publicado o en revisión, con sus motivos. Solo se
dejan fuera los duplicados, que se listan.
"""

from dataclasses import dataclass, field

from django.db import transaction

from apps.censo.servicios.carga_planilla import aplicar_decisiones, evaluar
from apps.censo.servicios.lectura_planilla import leer
from apps.censo.servicios.resultados_carga import (
    ArbolFueraDeSector,
    RegistroEnRevision,
    ValorNoValido,
)
from config.constantes import DECISION_CONSERVAR, DECISION_DESCARTAR


@dataclass
class FilaDuplicada:
    """Una fila que no se incorporó porque repite un código o una ubicación con su especie."""

    codigo: str
    motivo: str


@dataclass
class ReportePlanilla:
    """Resultado de importar la planilla (el mismo con y sin `--seco`)."""

    archivo: str = ""
    seco: bool = False
    filas_leidas: int = 0
    creados: int = 0
    actualizados: int = 0
    sin_coordenadas: int = 0
    codigos_calculados: int = 0
    numeros_no_validos: list[ValorNoValido] = field(default_factory=list)
    fechas_no_validas: list[ValorNoValido] = field(default_factory=list)
    fuera_de_catalogo: list[ValorNoValido] = field(default_factory=list)
    fuera_de_sector: list[ArbolFueraDeSector] = field(default_factory=list)
    sin_resolver: list[ValorNoValido] = field(default_factory=list)
    publicados: int = 0
    en_revision: list[RegistroEnRevision] = field(default_factory=list)
    duplicados: list[FilaDuplicada] = field(default_factory=list)
    ejemplo_sin_cambios: list[str] = field(default_factory=list)
    ejemplo_reemplazados: list[str] = field(default_factory=list)
    catalogo_sin_cargar: str | None = None


def importar_planilla(ruta, seco=False):
    """Lee la planilla y hace upsert por `codigo`. Con `seco` valida y revierte al final.

    De un código repetido entra la primera fila; una fila con la ubicación y la especie de otro
    árbol no entra. Lanza ValueError con un mensaje claro si el archivo no sirve.
    """
    planilla = leer(ruta)
    evaluacion = evaluar(planilla)
    decisiones = {
        fila.numero_fila: DECISION_DESCARTAR if _no_entra(fila) else DECISION_CONSERVAR
        for fila in evaluacion.filas
    }
    with transaction.atomic():
        resultado = aplicar_decisiones(evaluacion, decisiones)
        if seco:
            transaction.set_rollback(True)
    reporte = ReportePlanilla(
        archivo=planilla.nombre_archivo,
        seco=seco,
        filas_leidas=len(evaluacion.filas),
        creados=resultado.creados,
        actualizados=resultado.actualizados,
        publicados=len(resultado.publicados),
        en_revision=resultado.en_revision,
        ejemplo_sin_cambios=resultado.ejemplo_sin_cambios,
        ejemplo_reemplazados=resultado.ejemplo_reemplazados,
        catalogo_sin_cargar=evaluacion.catalogo_sin_cargar,
    )
    for fila in evaluacion.filas:
        reporte.codigos_calculados += fila.codigo_calculado
        if _no_entra(fila):
            reporte.duplicados.append(FilaDuplicada(fila.codigo, fila.duplicado.porque))
        if fila.repetida:
            continue  # una fila repetida no se lee más: solo se lista
        reporte.sin_coordenadas += fila.sin_coordenadas
        reporte.numeros_no_validos += fila.numeros_no_validos
        reporte.fechas_no_validas += fila.fechas_no_validas
        reporte.fuera_de_catalogo += fila.fuera_de_catalogo
        reporte.fuera_de_sector += fila.fuera_de_sector
        reporte.sin_resolver += fila.sin_resolver
    return reporte


def _no_entra(fila):
    """En la consola solo se dejan fuera los códigos repetidos y los duplicados de ubicación."""
    return fila.repetida or fila.duplicado_por_ubicacion
