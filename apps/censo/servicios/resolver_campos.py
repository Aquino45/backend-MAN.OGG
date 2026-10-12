"""Del texto de la planilla a las tablas del censo, y de las tablas otra vez al texto.

La planilla trae nombres, estados y brigada como texto. Aquí cada texto se busca, normalizado (sin
mayúsculas, tildes ni espacios de más), en la especie, el catálogo o el grupo que corresponde.
Lo que no coincide con una sola fila no se inventa: queda en `valores_originales` del árbol.

`texto_de` hace el camino contrario: el texto de un dato del árbol, que es el que usan la regla de
calidad, las cápsulas y la API. Una sola implementación para todos.
"""

from apps.censo.models import Brigada, Especie, GrupoBrigada, ValorCatalogo
from apps.censo.servicios.normalizacion import lineas_de, normalizar
from config.constantes import (
    CAMPO_BRIGADA,
    CAMPO_ORIGEN,
    CAMPOS_DE_ESPECIE,
    CAMPOS_ESTADO_ARBOL,
    CAMPOS_TEXTO_RESUELTOS,
)

RELACIONES_DEL_ARBOL = ("especie__origen", "grupo__brigada", *CAMPOS_ESTADO_ARBOL)
"""Lo que se trae junto con el árbol (`select_related`) para leer sus textos sin más consultas."""

CAMPOS_DE_NOMBRE = ("nombre_cientifico", "nombre_comun")
"""Nombres con los que se busca la especie, en orden: primero el científico."""


def _vacio(valor):
    return valor is None or (isinstance(valor, str) and not valor.strip())


class Resolutor:
    """Las especies, los valores del catálogo y los grupos ya leídos, para resolver muchas filas.

    Se arma una vez por carga (`desde_bd`) y no vuelve a consultar la BD.
    """

    def __init__(self, especies=(), valores=(), grupos=(), brigadas=()):
        self.especies_por_nombre = {}
        for especie in especies:
            nombres = [
                especie.nombre_cientifico,
                especie.nombre_comun,
                *lineas_de(especie.alias),
            ]
            for nombre in nombres:
                if not _vacio(nombre):
                    self.especies_por_nombre.setdefault(normalizar(nombre), {})[especie.pk] = (
                        especie
                    )
        self.valores = {}
        for valor in valores:
            self.valores.setdefault((valor.campo, normalizar(valor.valor)), valor)
        self.grupos_por_nombre = {}
        for grupo in grupos:
            for nombre in [grupo.nombre, *lineas_de(grupo.alias)]:
                self.grupos_por_nombre.setdefault(normalizar(nombre), {})[grupo.pk] = grupo
        self.brigadas = {normalizar(brigada.nombre): brigada for brigada in brigadas}

    @classmethod
    def desde_bd(cls):
        """Lee de la BD todo lo que hace falta para resolver."""
        return cls(
            Especie.objects.select_related("origen"),
            ValorCatalogo.objects.order_by("campo", "orden", "valor"),
            GrupoBrigada.objects.select_related("brigada"),
            Brigada.objects.all(),
        )

    def especie(self, texto):
        """La única especie que coincide con `texto`, o None (sin coincidencia o ambigua)."""
        encontradas = self.especies_por_nombre.get(normalizar(texto), {}) if texto else {}
        return next(iter(encontradas.values())) if len(encontradas) == 1 else None

    def valor(self, campo, texto):
        """El valor del catálogo de `campo` que coincide con `texto`, o None."""
        return self.valores.get((campo, normalizar(texto))) if texto else None

    def grupo(self, texto):
        """El único grupo, por nombre o alias, que coincide con `texto`, o None."""
        encontrados = self.grupos_por_nombre.get(normalizar(texto), {}) if texto else {}
        return next(iter(encontrados.values())) if len(encontrados) == 1 else None

    def resolver(self, valores):
        """Cambia los textos de `valores` por sus referencias y anota lo que no se resolvió.

        Recibe `{campo: texto}` con los campos de `CAMPOS_TEXTO_RESUELTOS` y devuelve un diccionario
        nuevo: los demás campos igual, `especie`, `grupo` y los estados como referencias (None si no
        se resolvió) y `valores_originales` con el texto de lo que no coincide con lo resuelto.
        """
        resultado = {c: v for c, v in valores.items() if c not in CAMPOS_TEXTO_RESUELTOS}
        originales = {}
        especie = self._especie_de(valores)
        resultado["especie"] = especie
        self._anotar_especie(valores, especie, originales)
        for campo in CAMPOS_ESTADO_ARBOL:
            texto = valores.get(campo)
            catalogado = self.valor(campo, texto)
            resultado[campo] = catalogado
            if texto is not None and (catalogado is None or catalogado.valor != texto):
                originales[campo] = texto
        texto_brigada = valores.get(CAMPO_BRIGADA)
        grupo = self.grupo(texto_brigada)
        resultado["grupo"] = grupo
        if texto_brigada is not None and (grupo is None or grupo.brigada.nombre != texto_brigada):
            originales[CAMPO_BRIGADA] = texto_brigada
        resultado["valores_originales"] = originales
        return resultado

    def _especie_de(self, valores):
        """La especie del nombre científico; sin nombre científico, la del nombre común."""
        for campo in CAMPOS_DE_NOMBRE:
            if not _vacio(valores.get(campo)):
                return self.especie(valores[campo])
        return None

    @staticmethod
    def _anotar_especie(valores, especie, originales):
        """Anota los nombres y el origen que traía la planilla y no son los de la especie."""
        for campo in CAMPOS_DE_ESPECIE:
            texto = valores.get(campo)
            if texto is None:
                continue
            canonico = texto_de_especie(especie, campo)
            if especie is None or normalizar(texto) != normalizar(canonico):
                originales[campo] = texto


def texto_de_especie(especie, campo):
    """El texto de un dato que viene de la especie (nombre o origen), o None."""
    if especie is None:
        return None
    if campo == CAMPO_ORIGEN:
        return None if especie.origen is None else especie.origen.valor
    return getattr(especie, campo)


def resolver_especie(texto, resolutor=None):
    """La especie que coincide con el texto (nombre científico, alias o nombre común), o None."""
    return (resolutor or Resolutor.desde_bd()).especie(texto)


def resolver_valor(campo, texto, resolutor=None):
    """El valor del catálogo de `campo` que coincide con el texto, o None."""
    return (resolutor or Resolutor.desde_bd()).valor(campo, texto)


def resolver_grupo(texto, resolutor=None):
    """El grupo (por nombre o alias) que coincide con el texto, o None."""
    return (resolutor or Resolutor.desde_bd()).grupo(texto)


def resolver_valores(valores, resolutor=None):
    """Resuelve los textos de `valores` (ver `Resolutor.resolver`)."""
    return (resolutor or Resolutor.desde_bd()).resolver(valores)


def texto_de(arbol, campo):
    """El texto de un dato del árbol: lo que dicen sus tablas y, si falta, lo que trajo la planilla.

    Nombres y origen salen de la especie; los estados, de su valor del catálogo; la brigada y el
    grupo, del grupo. Para cualquier otro campo devuelve el atributo del árbol.
    """
    if campo not in (*CAMPOS_TEXTO_RESUELTOS, "grupo"):
        return getattr(arbol, campo)
    valor = _de_las_tablas(arbol, campo)
    if _vacio(valor):
        return (arbol.valores_originales or {}).get(campo)
    return valor


def _de_las_tablas(arbol, campo):
    if campo in CAMPOS_DE_ESPECIE:
        return texto_de_especie(arbol.especie, campo)
    if campo == CAMPO_BRIGADA:
        return None if arbol.grupo is None else arbol.grupo.brigada.nombre
    if campo == "grupo":
        return None if arbol.grupo is None else arbol.grupo.nombre
    catalogado = getattr(arbol, campo)
    return None if catalogado is None else catalogado.valor


def nombre_cientifico_de(valores):
    """El nombre científico de unos `valores` ya resueltos: el de la especie o el de la fila."""
    especie = valores.get("especie")
    if especie is not None:
        return especie.nombre_cientifico
    return (valores.get("valores_originales") or {}).get("nombre_cientifico")


CAMPOS_QUE_RESUELVE = {
    "especie": CAMPOS_DE_ESPECIE,
    "grupo": (CAMPO_BRIGADA,),
    **{campo: (campo,) for campo in CAMPOS_ESTADO_ARBOL},
}
"""Qué textos de la planilla quedan resueltos cuando una referencia tiene valor."""


def fusionar_originales(existentes, valores):
    """Los textos sin resolver de un árbol que ya existe, puestos al día con los de una fila nueva.

    Un texto que la fila ahora sí resuelve (su referencia trae valor) deja de estar anotado; los
    que la fila no pudo resolver se suman o reemplazan a los anotados.
    """
    resueltos = {
        campo
        for referencia, campos in CAMPOS_QUE_RESUELVE.items()
        if valores.get(referencia) is not None
        for campo in campos
    }
    conservados = {c: t for c, t in (existentes or {}).items() if c not in resueltos}
    return {**conservados, **(valores.get("valores_originales") or {})}


def aplicar_textos(arbol, textos, resolutor=None):
    """Pone en el árbol los datos de texto dados (`{campo: texto}`) ya resueltos.

    Solo toca lo que `textos` menciona: la especie si trae algún nombre, el grupo si trae la
    brigada y cada estado que trae. Lo que no se resuelve queda en `valores_originales`.
    """
    resueltos = resolver_valores(textos, resolutor)
    for referencia, campos in CAMPOS_QUE_RESUELVE.items():
        pedidos = [c for c in campos if c in textos]
        if referencia == "especie":
            pedidos = [c for c in pedidos if c in CAMPOS_DE_NOMBRE]
        if pedidos:
            setattr(arbol, referencia, resueltos[referencia])
    arbol.valores_originales = fusionar_originales(arbol.valores_originales, resueltos)
