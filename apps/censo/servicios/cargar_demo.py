"""Carga y borra los árboles simulados de los sectores 2 a 5 del Censo arbóreo UPeU Lima.

El archivo se valida entero antes de escribir nada; la carga se puede repetir sin duplicar.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db import models, transaction

from apps.censo.models import Arbol, Sector
from apps.censo.servicios.calidad_registro import CAMPOS_DEL_ESTADO, aplicar, cargar_catalogo
from apps.censo.servicios.importar_planilla import ArbolFueraDeSector
from config.constantes import (
    CLAVES_EXTRA_DEMO,
    LETRA_CODIGO_DEMO,
    MENSAJE_CODIGO_EN_PAPELERA,
    PATRON_CODIGO_ARBOL,
    PATRON_CODIGO_DEMO,
    SRID_MAPA,
    TOPE_DESTACADOS_POR_SECTOR,
)

CAMPOS_PROPIOS = frozenset({"codigo", "sector", "ubicacion"})
"""Campos del modelo que se arman aparte (la ubicación sale de `lat` y `lon`)."""

CLAVES_CONOCIDAS = (
    frozenset(
        campo.name
        for campo in Arbol._meta.concrete_fields
        if campo.editable and not campo.auto_created and not isinstance(campo, GeometryField)
    )
    | CLAVES_EXTRA_DEMO
)
"""Claves que puede traer un árbol del archivo: campos editables del modelo y las del contrato."""

CAMPOS_DECIMALES = frozenset(
    campo.name for campo in Arbol._meta.concrete_fields if isinstance(campo, models.DecimalField)
)
"""Campos numéricos del modelo: llegan como número JSON y se guardan como Decimal."""


@dataclass
class ReporteDemo:
    """Resultado de cargar los árboles simulados."""

    archivo: str = ""
    creados: int = 0
    actualizados: int = 0
    fuera_de_sector: list[ArbolFueraDeSector] = field(default_factory=list)
    destacados_por_sector: dict[int, int] = field(default_factory=dict)


@dataclass
class _Registro:
    """Un árbol del archivo ya validado, con los valores listos para el modelo."""

    codigo: str
    id_sector: int
    destacado: bool
    valores: dict
    ubicacion: Point | None


def cargar_demo(ruta):
    """Valida el archivo entero y, si todo está bien, hace upsert por `codigo`.

    Lanza ValueError (con todos los problemas juntos) y no guarda nada si algo no sirve.
    """
    ruta = Path(ruta)
    crudos = _leer_archivo(ruta)
    sectores = Sector.objects.in_bulk()
    registros = _validar(crudos, set(sectores))
    existentes = Arbol.todos.filter(codigo__in=[r.codigo for r in registros]).in_bulk(
        field_name="codigo"
    )
    catalogo = cargar_catalogo()
    guardados = {}
    reporte = ReporteDemo(archivo=ruta.name)
    with transaction.atomic():
        # Primero los no destacados: así el tope de Arbol.clean() no salta a mitad de una recarga.
        for registro in sorted(registros, key=lambda r: r.destacado):
            arbol = existentes.get(registro.codigo) or Arbol(codigo=registro.codigo)
            if arbol.pk is None:
                reporte.creados += 1
            else:
                reporte.actualizados += 1
            guardados[registro.codigo] = _guardar(arbol, registro, catalogo)
        for registro in registros:
            aviso = _aviso_fuera_de_sector(guardados[registro.codigo], sectores[registro.id_sector])
            if aviso is not None:
                reporte.fuera_de_sector.append(aviso)
        reporte.destacados_por_sector = _contar_destacados({r.id_sector for r in registros})
    return reporte


def borrar_demo():
    """Borra en definitivo los árboles simulados (demo y con la letra demo) y cuenta los borrados.

    Incluye los que están en la papelera. Un árbol real nunca se toca: los simulados no son
    registros del censo.
    """
    _, borrados_por_modelo = Arbol.todos.filter(
        demo=True, codigo__regex=PATRON_CODIGO_DEMO
    ).delete()
    return borrados_por_modelo.get(Arbol._meta.label, 0)


def _leer_archivo(ruta):
    """Lee el archivo y devuelve la lista de registros crudos."""
    if not ruta.is_file():
        raise ValueError(f"No existe el archivo: {ruta}")
    try:
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{ruta.name} no es un JSON válido: {error}") from error
    if not isinstance(contenido, list):
        raise ValueError(f"{ruta.name} debe ser una lista JSON de árboles.")
    if not contenido:
        raise ValueError(f"{ruta.name} está vacío: no trae ningún árbol.")
    return contenido


def _validar(crudos, ids_sectores):
    """Revisa todo el archivo y devuelve los registros; si hay problemas lanza un ValueError."""
    errores = []
    registros = []
    codigos_vistos = set()
    for indice, crudo in enumerate(crudos, start=1):
        if not isinstance(crudo, dict):
            errores.append(f"registro {indice}: no es un objeto JSON.")
            continue
        codigo = crudo.get("codigo")
        etiqueta = f"registro {indice}" + (f" ({codigo})" if isinstance(codigo, str) else "")
        problemas = _problemas_del_registro(crudo, ids_sectores)
        if isinstance(codigo, str) and codigo in codigos_vistos:
            problemas.append(f"el código {codigo} está repetido en el archivo")
        if isinstance(codigo, str):
            codigos_vistos.add(codigo)
        valores = _valores_del_modelo(crudo, problemas)
        errores += [f"{etiqueta}: {problema}." for problema in problemas]
        if not problemas:
            registros.append(_armar_registro(crudo, valores))
    if not errores:
        errores = _problemas_con_la_bd(registros)
    if errores:
        raise ValueError("El archivo se rechazó y no se guardó nada:\n- " + "\n- ".join(errores))
    return registros


def _problemas_del_registro(crudo, ids_sectores):
    """Problemas de un registro que se ven sin consultar la BD (salvo los sectores)."""
    problemas = []
    codigo = crudo.get("codigo")
    if crudo.get("demo") is not True:
        problemas.append("«demo» debe ser exactamente true")
    if not isinstance(codigo, str) or not re.fullmatch(PATRON_CODIGO_ARBOL, codigo):
        problemas.append(f"el código «{codigo}» no cumple el patrón {PATRON_CODIGO_ARBOL}")
    elif not re.fullmatch(PATRON_CODIGO_DEMO, codigo):
        problemas.append(f"el código «{codigo}» no lleva la letra demo «{LETRA_CODIGO_DEMO}»")
    fuente = crudo.get("fuente")
    if not isinstance(fuente, str) or not fuente.strip():
        problemas.append("la fuente está vacía o falta")
    for clave in ("foto_url", "foto_miniatura_url"):
        if crudo.get(clave) is not None:
            problemas.append(f"un árbol simulado no lleva foto ({clave} debe ser null)")
    sector = crudo.get("sector")
    if type(sector) is not int or sector not in ids_sectores:
        problemas.append(f"el sector «{sector}» no existe en la BD")
    desconocidas = sorted(set(crudo) - CLAVES_CONOCIDAS)
    if desconocidas:
        problemas.append("claves desconocidas: " + ", ".join(desconocidas))
    problemas += _problemas_de_coordenadas(crudo)
    return problemas


def _problemas_de_coordenadas(crudo):
    """`lat` y `lon` vienen juntas, como números dentro del rango de WGS84, o ninguna."""
    lat, lon = crudo.get("lat"), crudo.get("lon")
    if lat is None and lon is None:
        return []
    if not (_es_numero(lat) and _es_numero(lon) and abs(lat) <= 90 and abs(lon) <= 180):
        return [f"lat/lon no válidas (lat={lat!r}, lon={lon!r})"]
    return []


def _es_numero(valor):
    return isinstance(valor, int | float) and not isinstance(valor, bool)


def _valores_del_modelo(crudo, problemas):
    """Convierte lo que viene del JSON en valores del modelo; lo que no sirve va a `problemas`."""
    valores = {}
    for nombre in (CLAVES_CONOCIDAS & crudo.keys()) - CAMPOS_PROPIOS - CLAVES_EXTRA_DEMO:
        valor = crudo[nombre]
        try:
            if valor is not None and nombre in CAMPOS_DECIMALES:
                valor = _decimal(valor)
            elif valor is not None and nombre == "fecha_registro":
                valor = date.fromisoformat(valor)
        except (InvalidOperation, ValueError, TypeError):
            problemas.append(f"el valor de «{nombre}» no es válido: {valor!r}")
            continue
        valores[nombre] = valor
    return valores


def _decimal(valor):
    if isinstance(valor, bool) or not (decimal := Decimal(str(valor))).is_finite():
        raise ValueError(valor)
    return decimal


def _armar_registro(crudo, valores):
    lat, lon = crudo.get("lat"), crudo.get("lon")
    ubicacion = None if lat is None else Point(lon, lat, srid=SRID_MAPA)
    return _Registro(
        codigo=crudo["codigo"],
        id_sector=crudo["sector"],
        destacado=bool(valores.get("destacado")),
        valores=valores,
        ubicacion=ubicacion,
    )


def _problemas_con_la_bd(registros):
    """Códigos de árboles reales o de la papelera y sectores que pasarían el tope de destacados."""
    problemas = []
    codigos = [registro.codigo for registro in registros]
    reales = Arbol.todos.filter(codigo__in=codigos, demo=False).values_list("codigo", flat=True)
    problemas += [f"{codigo}: ya pertenece a un árbol real; no se pisa" for codigo in reales]
    en_papelera = Arbol.todos.filter(codigo__in=codigos, demo=True, eliminado_en__isnull=False)
    problemas += [
        f"{codigo}: " + MENSAJE_CODIGO_EN_PAPELERA.format(codigo=codigo)
        for codigo in en_papelera.values_list("codigo", flat=True)
    ]
    nuevos_por_sector = {}
    for registro in registros:
        if registro.destacado:
            nuevos_por_sector[registro.id_sector] = nuevos_por_sector.get(registro.id_sector, 0) + 1
    previos = list(
        Arbol.objects.filter(destacado=True, sector_id__in=nuevos_por_sector)
        .exclude(codigo__in=codigos)
        .values_list("sector_id", flat=True)
    )
    for id_sector in sorted(nuevos_por_sector):
        quedarian = nuevos_por_sector[id_sector] + previos.count(id_sector)
        if quedarian > TOPE_DESTACADOS_POR_SECTOR:
            problemas.append(
                f"sector {id_sector}: quedarían {quedarian} destacados y el tope es "
                f"{TOPE_DESTACADOS_POR_SECTOR}"
            )
    return problemas


def _guardar(arbol, registro, catalogo):
    """Copia los valores, valida con el modelo, guarda y aplica la regla de calidad."""
    for nombre, valor in registro.valores.items():
        setattr(arbol, nombre, valor)
    arbol.sector_id = registro.id_sector
    arbol.co2_simulado = True  # el CO₂ de un ejemplo siempre es simulado; sin CO₂ la regla lo quita
    # PostGIS transforma el punto de WGS84 al SRID del campo al guardar; Python no lo toca.
    arbol.ubicacion = registro.ubicacion
    try:
        arbol.full_clean()
    except ValidationError as error:
        raise ValueError(f"{registro.codigo}: {'; '.join(error.messages)}") from error
    arbol.save()
    arbol.refresh_from_db(fields=["ubicacion"])  # ya en UTM: la regla mide contra el sector
    aplicar(arbol, catalogo)
    arbol.save(update_fields=CAMPOS_DEL_ESTADO)
    return arbol


def _aviso_fuera_de_sector(arbol, sector):
    """Aviso si el punto ya transformado cae fuera del polígono de su sector."""
    if arbol.ubicacion is None or sector.geom.covers(arbol.ubicacion):
        return None
    return ArbolFueraDeSector(arbol.codigo, sector.id, sector.geom.distance(arbol.ubicacion))


def _contar_destacados(ids_sectores):
    """Destacados que quedaron en la BD en cada sector tocado por la carga."""
    cuenta = dict.fromkeys(sorted(ids_sectores), 0)
    for id_sector in Arbol.objects.filter(destacado=True, sector_id__in=ids_sectores).values_list(
        "sector_id", flat=True
    ):
        cuenta[id_sector] += 1
    return cuenta
