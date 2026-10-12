"""Completa los árboles de ejemplo (simulados) con datos que les faltan, sin pisar lo medido.

El archivo se valida entero antes de escribir nada. Solo se llenan los campos vacíos de la BD: un
valor distinto de lo que ya hay se informa como «no se pisa». Se puede repetir sin cambiar nada.
Un árbol real (`demo` falso) nunca se toca.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models, transaction

from apps.censo.models import Arbol
from apps.censo.servicios.calidad_registro import aplicar, cargar_catalogo
from apps.censo.servicios.resolver_campos import Resolutor, aplicar_textos, texto_de
from config.constantes.calidad import (
    CAMPOS_OBLIGATORIOS_CALIDAD,
    CAMPOS_OPCIONALES_CALIDAD,
    CLAVES_COMPLETAR_EJEMPLO,
    ESTADO_REGISTRO_PUBLICADO,
    FORMATO_FUENTE_EJEMPLO,
    MOTIVO_HISTORIAL_COMPLETAR_EJEMPLO,
    SEPARADOR_FUENTE,
)
from config.constantes.catalogos import CAMPOS_TEXTO_RESUELTOS
from config.constantes.general import PATRON_CODIGO_ARBOL

CAMPOS_COMPLETABLES = frozenset((*CAMPOS_OBLIGATORIOS_CALIDAD, *CAMPOS_OPCIONALES_CALIDAD)) - {
    "ubicacion",
    "motivo_destacado",
}
"""Datos que el archivo puede traer: los de la cartilla, sin la ubicación ni el motivo destacado."""

CAMPOS_DECIMALES = frozenset(
    campo.name for campo in Arbol._meta.concrete_fields if isinstance(campo, models.DecimalField)
)
"""Campos numéricos del modelo: llegan como número JSON y se guardan como Decimal."""


@dataclass
class ValorQueNoSePisa:
    """Un dato del archivo distinto del que ya tiene el árbol: se deja el del árbol."""

    codigo: str
    campo: str
    actual: str
    propuesto: str


@dataclass
class ReporteCompletarEjemplo:
    """Resultado de completar los árboles de ejemplo."""

    archivo: str = ""
    registros: int = 0
    completados: list[str] = field(default_factory=list)
    sin_cambios: int = 0
    no_se_pisa: list[ValorQueNoSePisa] = field(default_factory=list)
    reales_sin_tocar: list[str] = field(default_factory=list)
    publicados: int = 0
    en_revision: int = 0


def completar_ejemplo(ruta):
    """Valida el archivo entero y, si todo está bien, llena los campos vacíos de cada árbol.

    Lanza ValueError (con todos los problemas juntos) y no guarda nada si algo no sirve.
    """
    ruta = Path(ruta)
    registros = _validar(_leer_archivo(ruta))
    codigos = [registro["codigo"] for registro in registros]
    arboles = Arbol.todos.filter(codigo__in=codigos).in_bulk(field_name="codigo")
    faltan = [codigo for codigo in codigos if codigo not in arboles]
    if faltan:
        raise ValueError(_rechazo([f"{codigo}: no existe en la BD" for codigo in faltan]))
    catalogo = cargar_catalogo()
    resolutor = Resolutor.desde_bd()
    reporte = ReporteCompletarEjemplo(archivo=ruta.name, registros=len(registros))
    with transaction.atomic():
        for registro in registros:
            _completar(arboles[registro["codigo"]], registro, catalogo, reporte, resolutor)
    return reporte


def _leer_archivo(ruta):
    if not ruta.is_file():
        raise ValueError(f"No existe el archivo: {ruta}")
    try:
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{ruta.name} no es un JSON válido: {error}") from error
    if not isinstance(contenido, list) or not contenido:
        raise ValueError(f"{ruta.name} debe ser una lista JSON con al menos un registro.")
    return contenido


def _rechazo(errores):
    return "El archivo se rechazó y no se guardó nada:\n- " + "\n- ".join(errores)


def _validar(crudos):
    """Revisa todo el archivo y devuelve los registros con los valores ya convertidos."""
    errores, registros, vistos = [], [], set()
    for indice, crudo in enumerate(crudos, start=1):
        if not isinstance(crudo, dict):
            errores.append(f"registro {indice}: no es un objeto JSON.")
            continue
        codigo = crudo.get("codigo")
        etiqueta = f"registro {indice}" + (f" ({codigo})" if isinstance(codigo, str) else "")
        problemas = _problemas_del_registro(crudo)
        if isinstance(codigo, str) and codigo in vistos:
            problemas.append("el código está repetido en el archivo")
        if isinstance(codigo, str):
            vistos.add(codigo)
        campos = _convertir_campos(crudo, problemas)
        errores += [f"{etiqueta}: {problema}." for problema in problemas]
        if not problemas:
            registros.append({**crudo, "campos": campos})
    if errores:
        raise ValueError(_rechazo(errores))
    return registros


def _problemas_del_registro(crudo):
    claves = set(crudo)
    if claves != CLAVES_COMPLETAR_EJEMPLO:
        faltan = sorted(CLAVES_COMPLETAR_EJEMPLO - claves)
        sobran = sorted(claves - CLAVES_COMPLETAR_EJEMPLO)
        return [f"claves que faltan {faltan} o sobran {sobran}"]
    problemas = []
    codigo = crudo["codigo"]
    if not isinstance(codigo, str) or not re.fullmatch(PATRON_CODIGO_ARBOL, codigo):
        problemas.append(f"el código «{codigo}» no cumple el patrón {PATRON_CODIGO_ARBOL}")
    if not isinstance(crudo["marcar_ejemplo"], bool):
        problemas.append("«marcar_ejemplo» debe ser true o false")
    if not isinstance(crudo["nota_fuente"], str) or not crudo["nota_fuente"].strip():
        problemas.append("la nota de la fuente está vacía o falta")
    campos, simulados = crudo["campos"], crudo["campos_simulados"]
    if not isinstance(campos, dict) or not campos:
        return [*problemas, "«campos» debe ser un objeto con al menos un dato"]
    desconocidos = sorted(set(campos) - CAMPOS_COMPLETABLES)
    if desconocidos:
        problemas.append("campos que no se pueden completar: " + ", ".join(desconocidos))
    if not isinstance(simulados, list) or not set(simulados) <= set(campos):
        problemas.append("«campos_simulados» debe ser una lista de campos que están en «campos»")
    return problemas


def _convertir_campos(crudo, problemas):
    """Convierte los valores del archivo a tipos del modelo; lo que no sirve va a `problemas`."""
    campos = crudo.get("campos")
    if not isinstance(campos, dict):
        return {}
    convertidos = {}
    for nombre, valor in campos.items():
        if nombre not in CAMPOS_COMPLETABLES:
            continue
        try:
            convertidos[nombre] = _convertir(nombre, valor)
        except (InvalidOperation, ValueError, TypeError):
            problemas.append(f"el valor de «{nombre}» no es válido: {valor!r}")
    return convertidos


def _convertir(nombre, valor):
    if nombre in CAMPOS_DECIMALES:
        if isinstance(valor, bool) or not (numero := Decimal(str(valor))).is_finite():
            raise ValueError(valor)
        return numero
    if nombre == "fecha_registro":
        return date.fromisoformat(valor)
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(valor)
    return valor


def _vacio(valor):
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _completar(arbol, registro, catalogo, reporte, resolutor):
    """Llena los campos vacíos del árbol, marca el ejemplo, recalcula el estado y guarda."""
    codigo = arbol.codigo
    if not arbol.demo:
        reporte.reales_sin_tocar.append(codigo)
        return
    llenados, textos = [], {}
    for campo, propuesto in registro["campos"].items():
        actual = (
            texto_de(arbol, campo) if campo in CAMPOS_TEXTO_RESUELTOS else getattr(arbol, campo)
        )
        if _vacio(actual):
            llenados.append(campo)
            if campo in CAMPOS_TEXTO_RESUELTOS:
                textos[campo] = propuesto
            else:
                setattr(arbol, campo, propuesto)
        elif actual != propuesto:
            reporte.no_se_pisa.append(ValorQueNoSePisa(codigo, campo, str(actual), str(propuesto)))
    aplicar_textos(arbol, textos, resolutor)
    if llenados:
        arbol.fuente = _fuente_con_nota(arbol.fuente, registro, llenados)
    antes = (arbol.estado_registro, arbol.motivos_revision)
    aplicar(arbol, catalogo)
    if not llenados and (arbol.estado_registro, arbol.motivos_revision) == antes:
        reporte.sin_cambios += 1
    else:
        _guardar(arbol)
        if llenados:
            reporte.completados.append(codigo)
    if arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO:
        reporte.publicados += 1
    else:
        reporte.en_revision += 1


def _fuente_con_nota(fuente, registro, llenados):
    """Agrega a la fuente la nota y los campos simulados que de verdad se llenaron."""
    simulados = [campo for campo in registro["campos_simulados"] if campo in llenados]
    if not simulados:
        return fuente
    nota = FORMATO_FUENTE_EJEMPLO.format(
        nota=registro["nota_fuente"].strip(), campos=", ".join(simulados)
    )
    return fuente if nota in fuente else f"{fuente}{SEPARADOR_FUENTE}{nota}"


def _guardar(arbol):
    try:
        arbol.full_clean()
    except ValidationError as error:
        raise ValueError(f"{arbol.codigo}: " + "; ".join(error.messages)) from error
    arbol._change_reason = MOTIVO_HISTORIAL_COMPLETAR_EJEMPLO
    arbol.save()
