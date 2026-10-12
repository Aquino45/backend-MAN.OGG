"""El lote del panel: guardar lo validado, corregir fila por fila y confirmar.

Las filas del lote (`FilaCarga`) llevan los valores tal como se leyeron; al confirmar se evalúa
todo otra vez con lo corregido y se guarda con `aplicar_decisiones`. El archivo nunca se guarda.
"""

import hashlib

from django.db import transaction

from apps.censo.models import Arbol, Especie, FilaCarga, LoteCarga, ValorCatalogo
from apps.censo.servicios.carga_planilla import aplicar_decisiones, evaluar
from apps.censo.servicios.lectura_planilla import (
    ENCABEZADO_POR_CAMPO,
    PlanillaLeida,
    a_json,
    numero_de,
    texto_de,
)
from config.constantes import (
    CAMPO_MOTIVO_ESPECIE,
    CAMPOS_CATALOGADOS,
    CAMPOS_DE_UBICACION_PLANILLA,
    CAMPOS_NUMERICOS_PLANILLA,
    CLASIFICACION_CAMPOS_VACIOS,
    CLASIFICACION_DUPLICADO,
    CLASIFICACION_INCONSISTENTE,
    CLASIFICACION_LISTO,
    CLASIFICACIONES_CON_PROBLEMA,
    COLUMNAS_PLANILLA,
    DECISION_CONSERVAR,
    DECISION_DESCARTAR,
    ESTADO_LOTE_CANCELADO,
    ESTADO_LOTE_CONFIRMADO,
    ESTADO_LOTE_VALIDADO,
    FORMATO_CODIGO_EXISTENTE_NO_ACTUALIZADO,
    FORMATO_CODIGO_NUEVO_NO_INCORPORADO,
    MENSAJE_CARGA_LOTE_CERRADO,
    TIPO_CAMPO_LISTA,
    TIPO_CAMPO_NUMERO,
    TIPO_CAMPO_TEXTO,
)

CAMPOS_CORREGIBLES = frozenset(COLUMNAS_PLANILLA.values()) - {
    "codigo",
    "sector",
    "control_registro",
}
"""Campos que la pantalla de revisión deja corregir."""

LARGO_NOMBRE_ARCHIVO = LoteCarga._meta.get_field("nombre_archivo").max_length
"""Cuántos caracteres del nombre del archivo caben en la bitácora."""


def registrar_lote(usuario, nombre_archivo, contenido, evaluacion):
    """Guarda el lote (con el hash del archivo, no el archivo) y una fila por registro leído."""
    cuentas = evaluacion.cuentas()
    with transaction.atomic():
        lote = LoteCarga.objects.create(
            usuario=usuario,
            nombre_archivo=nombre_archivo[:LARGO_NOMBRE_ARCHIVO],
            sha256=hashlib.sha256(contenido).hexdigest(),
            filas_leidas=len(evaluacion.filas),
            listos=cuentas[CLASIFICACION_LISTO],
            con_campos_vacios=cuentas[CLASIFICACION_CAMPOS_VACIOS],
            inconsistentes=cuentas[CLASIFICACION_INCONSISTENTE],
            duplicados=cuentas[CLASIFICACION_DUPLICADO],
            resultado={"avisos": evaluacion.avisos},
        )
        FilaCarga.objects.bulk_create(
            FilaCarga(
                lote=lote,
                numero_fila=fila.numero_fila,
                codigo=fila.codigo,
                clasificacion=fila.clasificacion,
                datos={campo: a_json(valor) for campo, valor in fila.datos.items()},
                motivos=[{"campo": m.campo, "porque": m.porque} for m in fila.motivos_a_mostrar],
            )
            for fila in evaluacion.filas
        )
    return lote


def filas_con_problema(lote):
    """Las filas del lote por las que hay que preguntar, en el orden de la planilla."""
    return lote.filas.filter(clasificacion__in=CLASIFICACIONES_CON_PROBLEMA)


def mensajes_de_no_incorporacion(lote):
    """Qué pasa, por código, si se confirma sin revisar: un mensaje distinto si ya existe."""
    codigos = list(dict.fromkeys(filas_con_problema(lote).values_list("codigo", flat=True)))
    existentes = set(Arbol.todos.filter(codigo__in=codigos).values_list("codigo", flat=True))
    return [
        (
            FORMATO_CODIGO_EXISTENTE_NO_ACTUALIZADO
            if codigo in existentes
            else FORMATO_CODIGO_NUEVO_NO_INCORPORADO
        ).format(codigo=codigo)
        for codigo in codigos
    ]


def valores_activos_del_catalogo():
    """`{campo: [valores activos]}` para las listas de la revisión.

    Los campos del catálogo van en su orden; el nombre científico ofrece las especies existentes.
    """
    activos = {campo: [] for campo in CAMPOS_CATALOGADOS}
    filas = ValorCatalogo.objects.filter(activo=True).order_by("campo", "orden", "valor")
    for campo, valor in filas.values_list("campo", "valor"):
        activos.setdefault(campo, []).append(valor)
    activos[CAMPO_MOTIVO_ESPECIE] = list(
        Especie.objects.order_by("nombre_cientifico").values_list("nombre_cientifico", flat=True)
    )
    return activos


def campos_a_corregir(fila, activos):
    """Los campos de una fila con problema que se pueden editar: `[{campo, etiqueta, ...}]`."""
    campos = []
    for motivo in fila.motivos:
        pedidos = (
            CAMPOS_DE_UBICACION_PLANILLA if motivo["campo"] == "ubicacion" else (motivo["campo"],)
        )
        campos += [c for c in pedidos if c in CAMPOS_CORREGIBLES and c not in campos]
    return [_describir_campo(campo, fila.datos.get(campo), activos) for campo in campos]


def _describir_campo(campo, valor, activos):
    if campo in CAMPOS_NUMERICOS_PLANILLA:
        tipo = TIPO_CAMPO_NUMERO
    elif activos.get(campo):
        tipo = TIPO_CAMPO_LISTA
    else:
        tipo = TIPO_CAMPO_TEXTO
    return {
        "campo": campo,
        "etiqueta": ENCABEZADO_POR_CAMPO[campo],
        "tipo": tipo,
        "valor_en_planilla": texto_de(valor),
        "valor": _valor_mostrado(campo, valor, tipo),
        "opciones": activos.get(campo, []) if tipo == TIPO_CAMPO_LISTA else [],
    }


def _valor_mostrado(campo, valor, tipo):
    """Lo que trae el control de la pantalla; un texto donde va un número se muestra vacío."""
    if tipo == TIPO_CAMPO_NUMERO and numero_de(valor, campo)[0] is None:
        return ""
    return texto_de(valor) or ""


def ediciones_del_formulario(filas, activos, pedidos):
    """`{pk de la fila: {campo: valor}}` con lo que el usuario cambió; el resto se ignora.

    `pedidos` es una función `(pk, campo) -> texto o None` que lee el formulario. Solo cuentan los
    campos que la pantalla ofrece y que cambiaron frente a lo que se mostraba.
    """
    ediciones = {}
    for fila in filas:
        for descrito in campos_a_corregir(fila, activos):
            nuevo = pedidos(fila.pk, descrito["campo"])
            if nuevo is not None and nuevo.strip() != descrito["valor"]:
                ediciones.setdefault(fila.pk, {})[descrito["campo"]] = nuevo.strip()
    return ediciones


def codigo_con_varias_conservadas(filas, conservadas):
    """El primer código con más de una fila conservada, o None (se conserva como mucho una)."""
    vistos = set()
    for fila in filas:
        if fila.pk in conservadas:
            if fila.codigo in vistos:
                return fila.codigo
            vistos.add(fila.codigo)
    return None


def confirmar_lote(lote, conservadas=None, ediciones=None):
    """Evalúa otra vez el lote (con lo corregido), guarda lo que entra y lo cierra.

    Con `conservadas` (los pk de las filas elegidas) las demás filas con problema no entran;
    sin él, no entra ninguna. Las filas buenas entran siempre. Un dato que ya existe no se
    borra con una celda vacía de la planilla. Las filas del lote se borran.
    Lanza ValueError si el lote ya no está pendiente.
    """
    ediciones = ediciones or {}
    with transaction.atomic():
        lote = LoteCarga.objects.select_for_update().get(pk=lote.pk)
        if lote.estado != ESTADO_LOTE_VALIDADO:
            raise ValueError(MENSAJE_CARGA_LOTE_CERRADO)
        filas = list(lote.filas.all())
        planilla = PlanillaLeida(
            lote.nombre_archivo,
            [(f.numero_fila, {**f.datos, **ediciones.get(f.pk, {})}) for f in filas],
        )
        evaluacion = evaluar(planilla)
        if conservadas is None:
            decisiones = {f.numero_fila: DECISION_DESCARTAR for f in evaluacion.con_problema()}
        else:
            decisiones = {
                f.numero_fila: DECISION_CONSERVAR if f.pk in conservadas else DECISION_DESCARTAR
                for f in filas
                if f.clasificacion in CLASIFICACIONES_CON_PROBLEMA
            }
        for fila in filas:
            fila.decision = decisiones.get(fila.numero_fila, fila.decision)
        FilaCarga.objects.bulk_update(filas, ["decision"])
        resultado = aplicar_decisiones(evaluacion, decisiones, conservar_existentes=True)
        lote.cerrar(
            ESTADO_LOTE_CONFIRMADO,
            {**resultado.como_dict(), "avisos": lote.resultado.get("avisos", [])},
        )
    return resultado


def cancelar_lote(lote):
    """Descarta el lote sin guardar nada. Lanza ValueError si el lote ya no está pendiente."""
    with transaction.atomic():
        lote = LoteCarga.objects.select_for_update().get(pk=lote.pk)
        if lote.estado != ESTADO_LOTE_VALIDADO:
            raise ValueError(MENSAJE_CARGA_LOTE_CERRADO)
        lote.cerrar(ESTADO_LOTE_CANCELADO)
