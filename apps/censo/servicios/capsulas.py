"""Cápsulas de ayuda de la cartilla: armado por árbol y carga inicial del contenido.

Armar es puro: recibe el árbol y el contenido ya leído, y no consulta la BD. Cargar valida el
archivo entero antes de escribir nada, crea lo que falta y se puede repetir sin duplicar.
"""

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction

from apps.censo.models import AyudaCampo, FichaEspecie, ValorCatalogo
from config.constantes import (
    CAMPOS_CATALOGADOS,
    CAMPOS_CON_AYUDA,
    CLAVES_AYUDA_CAMPO,
    CLAVES_FICHA_ESPECIE,
    CLAVES_VALOR_CATALOGO,
    SEPARADOR_DE_LINEAS,
)

SECCIONES = ("ayuda_campos", "valores", "fichas_especie")
"""Listas que debe traer el archivo de cápsulas."""


def normalizar(texto):
    """Minúsculas, sin acentos de más y con los espacios colapsados: así se comparan los valores.

    «Bueno», «bueno» y « bueno  » son lo mismo; `None` queda como texto vacío.
    """
    if texto is None:
        return ""
    sin_marcas = "".join(
        letra
        for letra in unicodedata.normalize("NFKD", str(texto))
        if not unicodedata.combining(letra)
    )
    return " ".join(sin_marcas.casefold().split())


def lineas_de(texto):
    """Las líneas con contenido de un texto «uno por línea», sin espacios de más."""
    return [linea.strip() for linea in (texto or "").split(SEPARADOR_DE_LINEAS) if linea.strip()]


def armar_capsulas(arbol, ayudas, valores):
    """Una cápsula por cada ayuda activa, en su orden (y después por campo).

    `en_este_arbol` es la explicación del valor activo del catálogo que coincide, normalizado,
    con el valor que tiene el árbol en ese campo; `None` si el campo no es del árbol, está
    vacío o su valor no está en el catálogo.
    """
    explicaciones = {
        (valor.campo, normalizar(valor.valor)): valor.explicacion
        for valor in valores
        if valor.activo
    }
    activas = sorted((a for a in ayudas if a.activo), key=lambda a: (a.orden, a.campo))
    return [
        {
            "campo": ayuda.campo,
            "titulo": ayuda.titulo,
            "que_es": ayuda.que_es,
            "en_este_arbol": _explicacion_del_valor(arbol, ayuda.campo, explicaciones),
        }
        for ayuda in activas
    ]


def _explicacion_del_valor(arbol, campo, explicaciones):
    valor = getattr(arbol, campo, None)
    if campo not in CAMPOS_CATALOGADOS or not isinstance(valor, str):
        return None
    return explicaciones.get((campo, normalizar(valor)))


def buscar_ficha(arbol, fichas):
    """La ficha de la especie del árbol, con la forma del contrato, o `None`.

    Se busca por `nombre_cientifico` (que gana) o por alias, normalizados, y solo entre las
    fichas publicadas.
    """
    buscado = normalizar(arbol.nombre_cientifico)
    if not buscado:
        return None
    fichas = [ficha for ficha in fichas if ficha.publicada]
    por_nombre = {normalizar(ficha.nombre_cientifico): ficha for ficha in fichas}
    por_alias = {normalizar(a): ficha for ficha in fichas for a in lineas_de(ficha.alias)}
    ficha = por_nombre.get(buscado) or por_alias.get(buscado)
    return None if ficha is None else _formato_de_ficha(ficha)


def _formato_de_ficha(ficha):
    return {
        "nombre_cientifico": ficha.nombre_cientifico,
        "nombre_comun": ficha.nombre_comun,
        "beneficios": lineas_de(ficha.beneficios),
        "dato_curioso": ficha.dato_curioso,
        "cuidados": ficha.cuidados,
        "fuente": ficha.fuente,
    }


# --- carga inicial ----------------------------------------------------------------------------


@dataclass
class ConteoDeCarga:
    """Cuántos registros de una tabla se crearon, se actualizaron o se dejaron como estaban."""

    creados: int = 0
    actualizados: int = 0
    omitidos: int = 0


@dataclass
class ReporteCapsulas:
    """Resultado de cargar el archivo de cápsulas."""

    archivo: str = ""
    ayudas: ConteoDeCarga = field(default_factory=ConteoDeCarga)
    valores: ConteoDeCarga = field(default_factory=ConteoDeCarga)
    fichas: ConteoDeCarga = field(default_factory=ConteoDeCarga)


def cargar_capsulas(ruta, actualizar=False):
    """Valida el archivo entero y, si todo está bien, crea lo que falta.

    Sin `actualizar` nunca pisa lo que ya existe (lo editado en el panel se respeta). Con
    `actualizar` sobrescribe los textos y el orden, pero conserva `publicada` y `activo` tal
    como están en la BD. Lanza ValueError, con todos los problemas juntos, y no guarda nada si
    algo no sirve.
    """
    ruta = Path(ruta)
    contenido = _leer(ruta)
    errores = []
    ayudas = _validar_ayudas(contenido["ayuda_campos"], errores)
    valores = _validar_valores(contenido["valores"], errores)
    fichas = _validar_fichas(contenido["fichas_especie"], errores)
    if errores:
        raise ValueError("El archivo de cápsulas no sirve:\n" + "\n".join(errores))
    reporte = ReporteCapsulas(archivo=str(ruta))
    with transaction.atomic():
        _guardar(reporte.ayudas, AyudaCampo, ["campo"], ayudas, actualizar)
        _guardar(reporte.valores, ValorCatalogo, ["campo", "valor"], valores, actualizar)
        _guardar(reporte.fichas, FichaEspecie, ["nombre_cientifico"], fichas, actualizar)
    return reporte


def _leer(ruta):
    try:
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"No se pudo leer {ruta}: {error}") from error
    if not isinstance(contenido, dict):
        raise ValueError(f"No se pudo leer {ruta}: se esperaba un objeto JSON.")
    faltan = [s for s in SECCIONES if not isinstance(contenido.get(s), list)]
    if faltan:
        raise ValueError(f"No se pudo leer {ruta}: faltan las listas {', '.join(faltan)}.")
    return contenido


def _guardar(conteo, modelo, claves, registros, actualizar):
    """Crea los registros que faltan; con `actualizar`, sobrescribe solo lo que cambió."""
    for datos in registros:
        busqueda = {clave: datos[clave] for clave in claves}
        existente = modelo.objects.filter(**busqueda).first()
        if existente is None:
            modelo.objects.create(**datos)
            conteo.creados += 1
            continue
        cambios = {k: v for k, v in datos.items() if k not in claves and k != "publicada"}
        if actualizar and any(getattr(existente, k) != v for k, v in cambios.items()):
            for atributo, valor in cambios.items():
                setattr(existente, atributo, valor)
            existente.save()
            conteo.actualizados += 1
        else:
            conteo.omitidos += 1


def _validar_ayudas(crudos, errores):
    registros, vistos = [], set()
    for posicion, crudo in enumerate(crudos, start=1):
        nombre = f"ayuda_campos[{posicion}]"
        antes = len(errores)
        if _revisar_claves(crudo, CLAVES_AYUDA_CAMPO, CLAVES_AYUDA_CAMPO, nombre, errores):
            _exigir_textos(crudo, ("campo", "titulo", "que_es"), nombre, errores)
            _exigir_en(crudo.get("campo"), CAMPOS_CON_AYUDA, "campo", nombre, errores)
            _exigir_unico(crudo.get("campo"), vistos, nombre, errores)
        if len(errores) == antes:
            registros.append({**crudo, "orden": posicion})
    return registros


def _validar_valores(crudos, errores):
    registros, vistos = [], set()
    for posicion, crudo in enumerate(crudos, start=1):
        nombre = f"valores[{posicion}]"
        antes = len(errores)
        if _revisar_claves(crudo, CLAVES_VALOR_CATALOGO, CLAVES_VALOR_CATALOGO, nombre, errores):
            _exigir_textos(crudo, ("campo", "valor", "explicacion"), nombre, errores)
            _exigir_en(crudo.get("campo"), CAMPOS_CATALOGADOS, "campo", nombre, errores)
            if not isinstance(crudo.get("orden"), int) or crudo["orden"] < 0:
                errores.append(f"{nombre}: «orden» debe ser un entero desde 0.")
            _exigir_unico(
                (crudo.get("campo"), normalizar(crudo.get("valor"))), vistos, nombre, errores
            )
        if len(errores) == antes:
            registros.append(dict(crudo))
    return registros


def _validar_fichas(crudos, errores):
    registros, vistos = [], set()
    for posicion, crudo in enumerate(crudos, start=1):
        nombre = f"fichas_especie[{posicion}]"
        antes = len(errores)
        if _revisar_claves(crudo, CLAVES_FICHA_ESPECIE, CLAVES_FICHA_ESPECIE, nombre, errores):
            _exigir_textos(crudo, ("nombre_cientifico", "nombre_comun", "fuente"), nombre, errores)
            for clave in ("alias", "beneficios"):
                _exigir_lista(crudo.get(clave), clave, nombre, errores)
            if not crudo.get("beneficios"):
                errores.append(f"{nombre}: «beneficios» no puede ir vacío.")
            for clave in ("dato_curioso", "cuidados"):
                texto = crudo.get(clave)
                if texto is not None and not (isinstance(texto, str) and texto.strip()):
                    errores.append(f"{nombre}: «{clave}» es un texto o null, nunca vacío.")
            if not isinstance(crudo.get("publicada"), bool):
                errores.append(f"{nombre}: «publicada» debe ser true o false.")
            _exigir_unico(normalizar(crudo.get("nombre_cientifico")), vistos, nombre, errores)
        if len(errores) == antes:
            registros.append(_ficha_para_el_modelo(crudo))
    return registros


def _ficha_para_el_modelo(crudo):
    return {
        **crudo,
        "alias": SEPARADOR_DE_LINEAS.join(crudo["alias"]),
        "beneficios": SEPARADOR_DE_LINEAS.join(crudo["beneficios"]),
    }


def _revisar_claves(crudo, requeridas, permitidas, nombre, errores):
    """True si el registro es un objeto con exactamente las claves esperadas."""
    if not isinstance(crudo, dict):
        errores.append(f"{nombre}: se esperaba un objeto.")
        return False
    faltan, sobran = requeridas - crudo.keys(), crudo.keys() - permitidas
    if faltan:
        errores.append(f"{nombre}: faltan las claves {', '.join(sorted(faltan))}.")
    if sobran:
        errores.append(f"{nombre}: claves desconocidas {', '.join(sorted(sobran))}.")
    return not (faltan or sobran)


def _exigir_textos(crudo, claves, nombre, errores):
    for clave in claves:
        texto = crudo.get(clave)
        if not (isinstance(texto, str) and texto.strip()):
            errores.append(f"{nombre}: «{clave}» es obligatorio y no puede ir vacío.")


def _exigir_lista(valor, clave, nombre, errores):
    if not isinstance(valor, list) or not all(isinstance(t, str) and t.strip() for t in valor):
        errores.append(f"{nombre}: «{clave}» debe ser una lista de textos con contenido.")


def _exigir_en(valor, permitidos, clave, nombre, errores):
    if isinstance(valor, str) and valor.strip() and valor not in permitidos:
        errores.append(f"{nombre}: «{clave}» {valor!r} no es de las constantes del sistema.")


def _exigir_unico(identidad, vistos, nombre, errores):
    if not isinstance(identidad, str | tuple) or (
        isinstance(identidad, tuple) and not all(isinstance(parte, str) for parte in identidad)
    ):
        return  # un tipo que no es texto ya se reportó como error aparte
    if identidad in vistos:
        errores.append(f"{nombre}: registro repetido ({identidad}).")
    vistos.add(identidad)
