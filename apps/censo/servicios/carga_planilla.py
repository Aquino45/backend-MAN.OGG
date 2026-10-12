"""Carga de la planilla de la brigada en tres pasos que comparten la consola y el panel.

`lectura_planilla.leer` abre el .xlsx en memoria. `evaluar` les aplica la regla
de calidad (`calidad_registro`) y busca duplicados, sin escribir nada. `aplicar_decisiones` guarda
las filas que entran. El panel guarda el lote entre un paso y otro (`lote_carga`).
"""

import re
from dataclasses import dataclass, field

from django.contrib.gis.geos import Point
from django.db import transaction

from apps.censo.models import Arbol, Sector, ValorCatalogo
from apps.censo.servicios.calidad_registro import (
    Motivo,
    aplicar,
    aviso_catalogo_sin_cargar,
    buscar_duplicado_por_ubicacion,
    cargar_catalogo,
)
from apps.censo.servicios.lectura_planilla import (
    ENCABEZADO_POR_CAMPO,
    entero_sector,
    fecha_de,
    numero_de,
    texto_de,
)
from config.constantes import (
    CAMPOS_CATALOGADOS,
    CAMPOS_CON_NOTA_PLANILLA,
    CAMPOS_NUMERICOS_PLANILLA,
    CLASIFICACION_CAMPOS_VACIOS,
    CLASIFICACION_DUPLICADO,
    CLASIFICACION_INCONSISTENTE,
    CLASIFICACION_LISTO,
    CLASIFICACIONES_CON_PROBLEMA,
    CO2_PLANILLA_ES_SIMULADO,
    COLUMNAS_PLANILLA,
    DECISION_CONSERVAR,
    ESTADO_REGISTRO_EN_REVISION,
    ETIQUETAS_CAMPOS_CALIDAD,
    FORMATO_CODIGO_CALCULADO,
    FORMATO_NOTA_PLANILLA,
    HOJA_PLANILLA,
    MENSAJE_CODIGO_EN_PAPELERA,
    MOTIVO_DUPLICADO_CODIGO,
    MOTIVO_DUPLICADO_UBICACION,
    MOTIVO_FALTA_DATO,
    PATRON_CODIGO_ARBOL,
    SEPARADOR_DE_LINEAS,
    SEPARADOR_NOTAS,
    SRID_UTM_CENSO,
)

CAMPOS_SIN_COPIA_DIRECTA = frozenset(
    {"codigo", "sector", "fecha_registro", "observaciones", "control_registro"}
)
"""Campos con tratamiento propio; `control_registro` se lee pero no se guarda."""

CAMPOS_TEXTO = (
    frozenset(COLUMNAS_PLANILLA.values()) - CAMPOS_NUMERICOS_PLANILLA - CAMPOS_SIN_COPIA_DIRECTA
)
"""Campos de texto que se copian tal cual (sin espacios en los bordes) al modelo."""


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

    def como_dict(self):
        """Los códigos de cada grupo, para guardarlos en la bitácora del lote."""
        return {
            "publicados": self.publicados,
            "en_revision": [registro.codigo for registro in self.en_revision],
            "no_incorporados": self.no_incorporados,
            "ejemplo_sin_cambios": self.ejemplo_sin_cambios,
        }


# --- paso 2: evaluar ------------------------------------------------------------


def evaluar(planilla):
    """Evalúa todas las filas con la regla de calidad y la búsqueda de duplicados; no escribe.

    Una fila es «listo», «con campos vacíos» (solo le faltan datos), «inconsistente» (algún dato
    no sirve) o «duplicado» (su código se repite en el archivo, o comparte ubicación y especie con
    otro árbol). Lanza ValueError si falta un sector, un código no cumple el patrón o está en la
    papelera.
    """
    catalogo = cargar_catalogo()
    evaluacion = Evaluacion(
        nombre_archivo=planilla.nombre_archivo,
        catalogo_calidad=catalogo,
        catalogo_sin_cargar=aviso_catalogo_sin_cargar(catalogo),
    )
    sectores = _cargar_sectores(planilla.filas)
    orden_en_sector, por_codigo, por_ubicacion = {}, {}, {}
    for numero_fila, datos in planilla.filas:
        id_sector = entero_sector(datos["sector"])
        orden_en_sector[id_sector] = orden_en_sector.get(id_sector, 0) + 1
        fila = _evaluar_fila(
            numero_fila, datos, planilla, sectores[id_sector], orden_en_sector, catalogo
        )
        _marcar_duplicados(fila, por_codigo, por_ubicacion)
        evaluacion.filas.append(fila)
    return evaluacion


def _cargar_sectores(filas):
    """Trae de la BD los sectores que usa la planilla; falla si falta alguno."""
    ids = {entero_sector(fila["sector"]) for _, fila in filas}
    sectores = Sector.objects.in_bulk(ids)
    faltan = sorted(ids - set(sectores))
    if faltan:
        raise ValueError(
            "La planilla usa sectores que no están en la BD: "
            + ", ".join(str(id_sector) for id_sector in faltan)
            + ". Importa antes los sectores (importar_sectores)."
        )
    return sectores


def _evaluar_fila(numero_fila, datos, planilla, sector, orden_en_sector, catalogo):
    """Convierte una fila en lo que se guardaría y le aplica la regla de calidad."""
    codigo = texto_de(datos["codigo"])
    calculado = codigo is None
    if calculado:
        codigo = FORMATO_CODIGO_CALCULADO.format(sector=sector.id, orden=orden_en_sector[sector.id])
    if not re.fullmatch(PATRON_CODIGO_ARBOL, codigo):
        raise ValueError(f"Fila {numero_fila}: el código «{codigo}» no cumple el patrón.")
    if Arbol.todos.filter(codigo=codigo, eliminado_en__isnull=False).exists():
        raise ValueError(f"Fila {numero_fila}: " + MENSAJE_CODIGO_EN_PAPELERA.format(codigo=codigo))
    fila = FilaEvaluada(
        numero_fila, codigo, datos, {}, {}, [], CLASIFICACION_LISTO, codigo_calculado=calculado
    )
    valores = fila.valores
    valores.update({campo: texto_de(datos[campo]) for campo in CAMPOS_TEXTO})
    for campo in valores.keys() & planilla.catalogos.keys():
        if valores[campo] is not None and valores[campo] not in planilla.catalogos[campo]:
            fila.fuera_de_catalogo.append(
                ValorNoValido(codigo, ENCABEZADO_POR_CAMPO[campo], valores[campo])
            )
    notas = _leer_numeros(fila)
    valores["fecha_registro"], texto_fecha = fecha_de(datos["fecha_registro"])
    if texto_fecha is not None:
        encabezado = ENCABEZADO_POR_CAMPO["fecha_registro"]
        fila.fechas_no_validas.append(ValorNoValido(codigo, encabezado, texto_fecha))
    partes_observaciones = [texto_de(datos["observaciones"]), *notas]
    valores["observaciones"] = SEPARADOR_NOTAS.join(p for p in partes_observaciones if p) or None
    _poner_ubicacion(fila, sector)
    valores["sector"] = sector
    partes_fuente = [
        valores["brigada"],
        f"hoja {HOJA_PLANILLA} de {planilla.nombre_archivo}",
        f"fila {numero_fila}",
    ]
    valores["fuente"] = ", ".join(parte for parte in partes_fuente if parte)
    valores["fila_origen"] = numero_fila
    valores["demo"] = False
    valores["co2_simulado"] = CO2_PLANILLA_ES_SIMULADO
    candidato = Arbol(codigo=codigo, **valores)
    motivos = aplicar(candidato, catalogo, sector.geom, fila.textos_no_numericos)
    fila.motivos, fila.clasificacion = motivos, _clasificar(motivos)
    return fila


def _leer_numeros(fila):
    """Pone en `fila.valores` los números; devuelve las notas para `observaciones`."""
    notas = []
    for campo in (c for c in COLUMNAS_PLANILLA.values() if c in CAMPOS_NUMERICOS_PLANILLA):
        fila.valores[campo], texto = numero_de(fila.datos[campo], campo)
        if texto is not None:
            encabezado = ENCABEZADO_POR_CAMPO[campo]
            fila.numeros_no_validos.append(ValorNoValido(fila.codigo, encabezado, texto))
            fila.textos_no_numericos[campo] = texto
            if campo in CAMPOS_CON_NOTA_PLANILLA:
                notas.append(FORMATO_NOTA_PLANILLA.format(encabezado=encabezado, texto=texto))
    return notas


def _poner_ubicacion(fila, sector):
    valores = fila.valores
    este, norte = valores.pop("utm_este_m"), valores.pop("utm_norte_m")
    valores["ubicacion"] = None
    if este is not None and norte is not None:
        valores["ubicacion"] = Point(float(este), float(norte), srid=SRID_UTM_CENSO)
    else:
        fila.sin_coordenadas = True
    if valores["ubicacion"] is not None and not sector.geom.covers(valores["ubicacion"]):
        distancia_m = sector.geom.distance(valores["ubicacion"])
        fila.fuera_de_sector.append(ArbolFueraDeSector(fila.codigo, sector.id, distancia_m))


def _clasificar(motivos):
    """Sin motivos es listo; si solo faltan datos, campos vacíos; si no, inconsistente."""
    if not motivos:
        return CLASIFICACION_LISTO
    if all(_es_falta_de_dato(motivo) for motivo in motivos):
        return CLASIFICACION_CAMPOS_VACIOS
    return CLASIFICACION_INCONSISTENTE


def _es_falta_de_dato(motivo):
    etiqueta = ETIQUETAS_CAMPOS_CALIDAD.get(motivo.campo)
    return etiqueta is not None and motivo.porque == MOTIVO_FALTA_DATO.format(etiqueta=etiqueta)


def _marcar_duplicados(fila, por_codigo, por_ubicacion):
    """Marca como duplicadas las filas con código repetido o con la ubicación y especie de otra."""
    if fila.codigo in por_codigo:
        primera = por_codigo[fila.codigo]
        fila.repetida = True
        for afectada in (primera, fila):
            afectada.clasificacion = CLASIFICACION_DUPLICADO
            afectada.duplicado = afectada.duplicado or Motivo(
                "codigo", MOTIVO_DUPLICADO_CODIGO.format(codigo=fila.codigo)
            )
        return
    por_codigo[fila.codigo] = fila
    ubicacion, especie = fila.valores["ubicacion"], fila.valores["nombre_cientifico"]
    clave = (ubicacion.x, ubicacion.y, especie.lower()) if ubicacion and especie else None
    otro = por_ubicacion.get(clave) or buscar_duplicado_por_ubicacion(
        fila.codigo, ubicacion, especie
    )
    if otro:
        fila.duplicado_por_ubicacion = True
        fila.clasificacion = CLASIFICACION_DUPLICADO
        fila.duplicado = Motivo("ubicacion", MOTIVO_DUPLICADO_UBICACION.format(otro=otro))
    elif clave:
        por_ubicacion[clave] = fila.codigo


# --- paso 3: aplicar las decisiones ------------------------------------------------------------


def aplicar_decisiones(evaluacion, decisiones, conservar_existentes=False):
    """Guarda las filas que entran y devuelve qué pasó con cada una.

    `decisiones` es `{número de fila: conservar | descartar}`. Una fila lista entra sin decisión;
    una con campos vacíos, inconsistente o duplicada solo si se conserva. Todo lo que se guarda
    pasa por la regla de calidad, así que entra publicado o en revisión. Con `conservar_existentes`
    (el panel), una celda vacía no borra el dato de un árbol que ya existe.
    """
    resultado = ResultadoCarga()
    with transaction.atomic():
        for fila in evaluacion.filas:
            decision = decisiones.get(fila.numero_fila)
            sin_problema = fila.clasificacion not in CLASIFICACIONES_CON_PROBLEMA
            if decision == DECISION_CONSERVAR or (decision is None and sin_problema):
                _guardar_fila(fila, evaluacion.catalogo_calidad, resultado, conservar_existentes)
            else:
                resultado.no_incorporados.append(fila.codigo)
    return resultado


def _guardar_fila(fila, catalogo, resultado, conservar_existentes=False):
    """Guarda la fila con su estado. Un árbol de ejemplo solo se reemplaza por una fila completa.

    Un duplicado de ubicación que se conserva entra siempre en revisión, con ese motivo.
    """
    codigo = fila.codigo
    existente = Arbol.todos.filter(codigo=codigo).first()
    valores = fila.valores
    if conservar_existentes and existente is not None and not existente.demo:
        valores = _valores_sobre_existente(existente, fila.valores)
    candidato = Arbol(codigo=codigo, **valores)
    motivos = aplicar(candidato, catalogo, fila.valores["sector"].geom, fila.textos_no_numericos)
    if fila.duplicado_por_ubicacion:
        motivos = [*motivos, fila.duplicado]
        candidato.estado_registro = ESTADO_REGISTRO_EN_REVISION
        candidato.motivos_revision = SEPARADOR_DE_LINEAS.join(str(m) for m in motivos)
    if existente is not None and existente.demo:
        if motivos:
            resultado.ejemplo_sin_cambios.append(codigo)
            return
        resultado.ejemplo_reemplazados.append(codigo)
    estado = {
        "estado_registro": candidato.estado_registro,
        "motivos_revision": candidato.motivos_revision,
        "co2_simulado": candidato.co2_simulado,
    }
    _, creado = Arbol.todos.update_or_create(codigo=codigo, defaults={**valores, **estado})
    if creado:
        resultado.creados += 1
    else:
        resultado.actualizados += 1
    if motivos:
        resultado.en_revision.append(RegistroEnRevision(codigo, [str(m) for m in motivos]))
    else:
        resultado.publicados.append(codigo)


def _valores_sobre_existente(existente, valores):
    """El árbol que ya existe más los campos que la fila trae con valor; los vacíos no pisan."""
    con_valor = {campo: v for campo, v in valores.items() if v is not None and v != ""}
    resultado = {
        campo.name: getattr(existente, campo.name)
        for campo in Arbol._meta.concrete_fields
        if campo.name in valores
    }
    return {**resultado, **con_valor}


def valores_activos_del_catalogo():
    """`{campo: [valores activos]}` en el orden del catálogo, para las listas de la revisión."""
    activos = {campo: [] for campo in CAMPOS_CATALOGADOS}
    filas = ValorCatalogo.objects.filter(activo=True).order_by("campo", "orden", "valor")
    for campo, valor in filas.values_list("campo", "valor"):
        activos.setdefault(campo, []).append(valor)
    return activos
