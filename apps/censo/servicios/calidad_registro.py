"""Regla de calidad del registro: un árbol sale en la web («publicado») o queda «en revisión».

`evaluar` es pura: recibe el árbol, el catálogo ya leído y el polígono de su sector, y devuelve
los motivos por los que no se puede publicar (vacía = publicable). `aplicar` pone el estado y los
motivos en el árbol; todo camino de escritura la llama antes de guardar. El estado nunca se edita a
mano.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.censo.models import Arbol, ValorCatalogo
from apps.censo.servicios.capsulas import normalizar
from config.constantes import (
    AVISO_CATALOGO_SIN_CARGAR,
    CAMPO_DAP_EXENTO_EN_JUVENIL,
    CAMPOS_CATALOGADOS,
    CAMPOS_OBLIGATORIOS_CALIDAD,
    CAMPOS_OBLIGATORIOS_SI_NO_ES_EJEMPLO,
    ESTADO_REGISTRO_EN_REVISION,
    ESTADO_REGISTRO_PUBLICADO,
    ETIQUETAS_CAMPOS_CALIDAD,
    MOTIVO_FALTA_DATO,
    MOTIVO_FUERA_DE_CATALOGO,
    MOTIVO_FUERA_DE_RANGO,
    MOTIVO_FUERA_DEL_SECTOR,
    MOTIVO_HISTORIAL_RECALCULO_CALIDAD,
    MOTIVO_NO_ES_NUMERO,
    RANGOS_MEDIDAS,
    SEPARADOR_DE_LINEAS,
    TEXTO_RANGO_DESDE,
    TEXTO_RANGO_HASTA,
    TEXTO_RANGO_MAS_DE,
    TOLERANCIA_FUERA_DE_SECTOR_M,
    VALOR_TIPO_JUVENIL,
)

CAMPOS_DEL_ESTADO = ["estado_registro", "motivos_revision"]
"""Lo único que cambia el recálculo cuando solo se actualiza el estado de un árbol guardado."""


@dataclass(frozen=True)
class Motivo:
    """Por qué un registro no se puede publicar: el campo y el porqué, en lenguaje simple."""

    campo: str
    porque: str

    def __str__(self):
        return self.porque


@dataclass
class ReporteRecalculo:
    """Resultado de recalcular el estado de todos los árboles."""

    revisados: int = 0
    publicados: int = 0
    en_revision: int = 0
    cambiaron: int = 0
    catalogos_sin_cargar: list[str] | None = None


def cargar_catalogo():
    """El catálogo como `{campo: {valores normalizados}}`. Un valor inactivo también cuenta."""
    catalogo = {}
    for campo, valor in ValorCatalogo.objects.values_list("campo", "valor"):
        catalogo.setdefault(campo, set()).add(normalizar(valor))
    return catalogo


def campos_sin_catalogo(catalogo):
    """Los campos con lista desplegable que no tienen ningún valor en el catálogo."""
    return [campo for campo in CAMPOS_CATALOGADOS if not catalogo.get(campo)]


def aviso_catalogo_sin_cargar(catalogo):
    """«Catálogo sin cargar en: …», o None si todos los campos tienen catálogo."""
    campos = campos_sin_catalogo(catalogo)
    return AVISO_CATALOGO_SIN_CARGAR.format(campos=", ".join(campos)) if campos else None


def evaluar(arbol, catalogo=None, geom_sector=None, textos_no_numericos=None):
    """Los motivos por los que `arbol` no se puede publicar (lista vacía = publicable).

    `catalogo` es `{campo: {valores normalizados}}`: un campo sin valores no se evalúa.
    `geom_sector` es el polígono del sector en UTM; sin él no se mira la ubicación contra el
    sector. `textos_no_numericos` es `{campo: texto}` de lo que llegó donde va un número.
    """
    catalogo = catalogo or {}
    textos = textos_no_numericos or {}
    motivos = []
    for campo in _campos_exigidos(arbol):
        if campo in textos:
            motivos.append(_motivo(campo, MOTIVO_NO_ES_NUMERO, texto=textos[campo]))
        elif _vacio(getattr(arbol, campo)):
            if not (campo == CAMPO_DAP_EXENTO_EN_JUVENIL and _es_juvenil(arbol)):
                motivos.append(_motivo(campo, MOTIVO_FALTA_DATO))
        elif campo in RANGOS_MEDIDAS:
            motivos += _motivos_de_medida(campo, getattr(arbol, campo))
    motivos += _motivos_de_catalogo(arbol, catalogo)
    motivos += _motivos_de_sector(arbol, geom_sector)
    return motivos


def aplicar(arbol, catalogo=None, geom_sector=None, textos_no_numericos=None):
    """Pone en el árbol su estado y sus motivos (uno por línea) y devuelve los motivos.

    Sin `catalogo` o sin `geom_sector` los lee de la BD. Es lo que se llama antes de guardar.
    """
    if catalogo is None:
        catalogo = cargar_catalogo()
    if geom_sector is None and arbol.sector_id is not None:
        geom_sector = arbol.sector.geom
    motivos = evaluar(arbol, catalogo, geom_sector, textos_no_numericos)
    arbol.estado_registro = ESTADO_REGISTRO_EN_REVISION if motivos else ESTADO_REGISTRO_PUBLICADO
    arbol.motivos_revision = SEPARADOR_DE_LINEAS.join(str(motivo) for motivo in motivos)
    return motivos


def buscar_duplicado_por_ubicacion(codigo, ubicacion, nombre_cientifico):
    """Código de otro árbol vigente con la misma ubicación exacta y la misma especie, o None."""
    if ubicacion is None or not (nombre_cientifico or "").strip():
        return None
    otros = Arbol.objects.filter(ubicacion=ubicacion, nombre_cientifico__iexact=nombre_cientifico)
    return otros.exclude(codigo=codigo).values_list("codigo", flat=True).first()


def recalcular_calidad():
    """Evalúa todos los árboles (también los de la papelera) y guarda solo los que cambian.

    Se puede repetir: la segunda vez no cambia nada. Es lo que se corre después de la migración
    y cuando cambia el catálogo.
    """
    catalogo = cargar_catalogo()
    reporte = ReporteRecalculo(catalogos_sin_cargar=campos_sin_catalogo(catalogo))
    with transaction.atomic():
        for arbol in Arbol.todos.select_related("sector").order_by("codigo"):
            antes = (arbol.estado_registro, arbol.motivos_revision)
            aplicar(arbol, catalogo)
            reporte.revisados += 1
            if arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO:
                reporte.publicados += 1
            else:
                reporte.en_revision += 1
            if (arbol.estado_registro, arbol.motivos_revision) != antes:
                arbol._change_reason = MOTIVO_HISTORIAL_RECALCULO_CALIDAD
                arbol.save(update_fields=CAMPOS_DEL_ESTADO)
                reporte.cambiaron += 1
    return reporte


def _campos_exigidos(arbol):
    """Los campos que no pueden ir vacíos; la brigada solo se exige a un árbol real."""
    if arbol.demo:
        return CAMPOS_OBLIGATORIOS_CALIDAD
    return (*CAMPOS_OBLIGATORIOS_CALIDAD, *CAMPOS_OBLIGATORIOS_SI_NO_ES_EJEMPLO)


def _vacio(valor):
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _es_juvenil(arbol):
    return normalizar(arbol.tipo_individuo) == normalizar(VALOR_TIPO_JUVENIL)


def _motivo(campo, plantilla, **datos):
    etiqueta = ETIQUETAS_CAMPOS_CALIDAD[campo]
    return Motivo(campo, plantilla.format(etiqueta=etiqueta, **datos))


def _motivos_de_medida(campo, valor):
    """Motivo si la medida no es un número o cae fuera de su rango."""
    numero = _a_numero(valor)
    if numero is None:
        return [_motivo(campo, MOTIVO_NO_ES_NUMERO, texto=valor)]
    minimo, minimo_incluido, maximo = RANGOS_MEDIDAS[campo]
    debajo = numero < minimo or (numero == minimo and not minimo_incluido)
    if debajo or (maximo is not None and numero > maximo):
        piezas = [
            (TEXTO_RANGO_DESDE if minimo_incluido else TEXTO_RANGO_MAS_DE).format(minimo=minimo)
        ]
        if maximo is not None:
            piezas.append(TEXTO_RANGO_HASTA.format(maximo=maximo))
        rango = " ".join(piezas)
        return [_motivo(campo, MOTIVO_FUERA_DE_RANGO, valor=format(numero, "f"), rango=rango)]
    return []


def _a_numero(valor):
    """El valor como Decimal, o None si no es un número finito."""
    if isinstance(valor, bool):
        return None
    try:
        numero = Decimal(str(valor).strip().replace(",", "."))
    except InvalidOperation:
        return None
    return numero if numero.is_finite() else None


def _motivos_de_catalogo(arbol, catalogo):
    """Un valor que no está en el catálogo (comparado normalizado) manda a revisión."""
    motivos = []
    for campo in CAMPOS_CATALOGADOS:
        valor = getattr(arbol, campo)
        permitidos = catalogo.get(campo)
        if permitidos and not _vacio(valor) and normalizar(valor) not in permitidos:
            motivos.append(_motivo(campo, MOTIVO_FUERA_DE_CATALOGO, valor=valor))
    return motivos


def _motivos_de_sector(arbol, geom_sector):
    """Una ubicación a más de la tolerancia del polígono de su sector manda a revisión."""
    if geom_sector is None or arbol.ubicacion is None:
        return []
    distancia_m = geom_sector.distance(arbol.ubicacion)
    if distancia_m <= TOLERANCIA_FUERA_DE_SECTOR_M:
        return []
    return [
        Motivo(
            "ubicacion",
            MOTIVO_FUERA_DEL_SECTOR.format(
                distancia_m=distancia_m,
                sector=arbol.sector_id,
                tolerancia_m=TOLERANCIA_FUERA_DE_SECTOR_M,
            ),
        )
    ]
