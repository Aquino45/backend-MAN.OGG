"""Pasa los textos del árbol a las tablas nuevas: especies, brigada con grupos y catálogo.

Hacia adelante:
1. Cada ficha de especie pasa a una `Especie` (con su historial). Se siembran los alias.
2. Cada árbol toma su especie por nombre normalizado o por alias. Un nombre científico sin especie
   crea la especie con ese nombre tal cual y `revisada=False` (nunca se inventa otro dato).
3. El origen pasa a la especie. Si una especie trae orígenes distintos, la migración se detiene y
   lista los árboles: se resuelve a mano.
4. Los 8 estados pasan a su valor del catálogo. Si el valor no está en el catálogo, la referencia
   queda vacía y el texto, en `valores_originales`.
5. Se crea la brigada con sus grupos. Los árboles no tienen grupo hasta que la planilla lo trae.

Cada texto que no coincide con lo que quedó en las tablas se guarda en `valores_originales`, así
la reversa reescribe los textos tal como estaban.
"""

from collections import defaultdict

from django.db import migrations

from apps.censo.servicios.normalizacion import lineas_de, normalizar
from config.constantes import (
    ALIAS_INICIALES_DE_ESPECIES,
    CAMPO_ORIGEN,
    CAMPOS_ESTADO_ARBOL,
    GRUPOS_INICIALES_DE_BRIGADA,
    NOMBRE_BRIGADA_INICIAL,
    SEPARADOR_DE_LINEAS,
)

CAMPOS_FICHA = ("nombre_cientifico", "nombre_comun", "alias", "beneficios", "dato_curioso", "cuidados")
CAMPOS_HISTORIAL = ("history_date", "history_change_reason", "history_type", "history_user_id")


def _texto_de_estado(campo):
    return f"{campo}_texto"


# --- hacia adelante ---------------------------------------------------------------------------


def pasar_a_tablas(apps, schema_editor):
    Arbol = apps.get_model("censo", "Arbol")
    Especie = apps.get_model("censo", "Especie")
    ValorCatalogo = apps.get_model("censo", "ValorCatalogo")
    _fichas_a_especies(apps)
    _sembrar_alias(Especie)
    arboles = list(Arbol.objects.order_by("pk"))
    por_especie = _asignar_especies(Especie, arboles)
    _origen_a_la_especie(Especie, ValorCatalogo, arboles, por_especie)
    grupos = _crear_brigada(apps)
    catalogo = {(v.campo, normalizar(v.valor)): v for v in ValorCatalogo.objects.order_by("pk")}
    especies = Especie.objects.select_related("origen").in_bulk()
    for arbol in arboles:
        especie = especies.get(por_especie.get(arbol.pk))
        cambios = _cambios_del_arbol(arbol, especie, catalogo, grupos)
        Arbol.objects.filter(pk=arbol.pk).update(**cambios)


def _fichas_a_especies(apps):
    """Cada ficha es una especie (con su historial); la ficha conserva su estado de publicación."""
    FichaEspecie = apps.get_model("censo", "FichaEspecie")
    HistoricalFichaEspecie = apps.get_model("censo", "HistoricalFichaEspecie")
    Especie = apps.get_model("censo", "Especie")
    HistoricalEspecie = apps.get_model("censo", "HistoricalEspecie")
    especie_de_ficha = {}
    for ficha in FichaEspecie.objects.order_by("pk"):
        completa = bool(ficha.beneficios.strip() and ficha.fuente.strip())
        especie_de_ficha[ficha.pk] = Especie.objects.create(
            **{campo: getattr(ficha, campo) for campo in CAMPOS_FICHA},
            fuente_ficha=ficha.fuente,
            ficha_publicada=ficha.publicada and completa,
        )
    for registro in HistoricalFichaEspecie.objects.order_by("history_id"):
        especie = especie_de_ficha.get(registro.id)
        if especie is None:
            continue  # la ficha ya no existe: su historial no tiene especie a la que ir
        HistoricalEspecie.objects.create(
            id=especie.pk,
            **{campo: getattr(registro, campo) for campo in CAMPOS_FICHA},
            fuente_ficha=registro.fuente,
            ficha_publicada=registro.publicada,
            **{campo: getattr(registro, campo) for campo in CAMPOS_HISTORIAL},
        )


def _indice_de_especies(Especie):
    """`{nombre normalizado: {pk: especie}}` con nombre científico, alias y nombre común."""
    indice = defaultdict(dict)
    for especie in Especie.objects.all():
        for nombre in (especie.nombre_cientifico, especie.nombre_comun, *lineas_de(especie.alias)):
            if nombre:
                indice[normalizar(nombre)][especie.pk] = especie
    return indice


def _sembrar_alias(Especie):
    """Agrega los alias iniciales a su especie, salvo los que ya usa otra."""
    indice = _indice_de_especies(Especie)
    for nombre_cientifico, alias_nuevos in ALIAS_INICIALES_DE_ESPECIES.items():
        especie = Especie.objects.filter(nombre_cientifico=nombre_cientifico).first()
        if especie is None:
            continue
        alias = lineas_de(especie.alias)
        for nuevo in alias_nuevos:
            ocupado_por = set(indice.get(normalizar(nuevo), {})) - {especie.pk}
            if normalizar(nuevo) not in map(normalizar, alias) and not ocupado_por:
                alias.append(nuevo)
        Especie.objects.filter(pk=especie.pk).update(alias=SEPARADOR_DE_LINEAS.join(alias))


def _asignar_especies(Especie, arboles):
    """`{pk del árbol: pk de su especie}`; crea las especies de los nombres sin coincidencia."""
    indice = _indice_de_especies(Especie)
    asignadas, faltantes = {}, {}
    for arbol in arboles:
        encontradas = _coincidencias(indice, arbol)
        if len(encontradas) == 1:
            asignadas[arbol.pk] = next(iter(encontradas))
        elif not encontradas and (arbol.nombre_cientifico or "").strip():
            faltantes.setdefault(normalizar(arbol.nombre_cientifico), []).append(arbol)
    for arboles_del_nombre in faltantes.values():
        primero = arboles_del_nombre[0]
        comun = next((a.nombre_comun for a in arboles_del_nombre if a.nombre_comun), None)
        nueva = Especie.objects.create(
            nombre_cientifico=primero.nombre_cientifico.strip(), nombre_comun=comun, revisada=False
        )
        for arbol in arboles_del_nombre:
            asignadas[arbol.pk] = nueva.pk
    return asignadas


def _coincidencias(indice, arbol):
    """Las especies que coinciden con el nombre científico del árbol o, sin él, con el común."""
    for texto in (arbol.nombre_cientifico, arbol.nombre_comun):
        if texto and texto.strip():
            return indice.get(normalizar(texto), {})
    return {}


def _origen_a_la_especie(Especie, ValorCatalogo, arboles, por_especie):
    """Pone el origen de cada especie; si sus árboles traen orígenes distintos, se detiene."""
    origenes = defaultdict(lambda: defaultdict(list))
    for arbol in arboles:
        if arbol.pk in por_especie and (arbol.origen or "").strip():
            origenes[por_especie[arbol.pk]][normalizar(arbol.origen)].append(arbol)
    conflictos = []
    for pk_especie, por_origen in origenes.items():
        if len(por_origen) > 1:
            nombre = Especie.objects.get(pk=pk_especie).nombre_cientifico
            detalle = ", ".join(
                f"{a.codigo} ({a.origen})" for lista in por_origen.values() for a in lista
            )
            conflictos.append(f"{nombre}: {detalle}")
    if conflictos:
        raise RuntimeError(
            "Una misma especie trae orígenes distintos; resuélvelo a mano y vuelve a migrar:\n"
            + "\n".join(conflictos)
        )
    valores = {normalizar(v.valor): v for v in ValorCatalogo.objects.filter(campo=CAMPO_ORIGEN)}
    for pk_especie, por_origen in origenes.items():
        catalogado = valores.get(next(iter(por_origen)))
        if catalogado is not None:
            Especie.objects.filter(pk=pk_especie).update(origen=catalogado)


def _crear_brigada(apps):
    """La brigada inicial con sus grupos; devuelve `{nombre normalizado: grupo}`."""
    Brigada = apps.get_model("censo", "Brigada")
    GrupoBrigada = apps.get_model("censo", "GrupoBrigada")
    brigada, _ = Brigada.objects.get_or_create(nombre=NOMBRE_BRIGADA_INICIAL)
    for nombre in GRUPOS_INICIALES_DE_BRIGADA:
        GrupoBrigada.objects.get_or_create(brigada=brigada, nombre=nombre)
    grupos = GrupoBrigada.objects.select_related("brigada")
    return {normalizar(grupo.nombre): grupo for grupo in grupos}


def _cambios_del_arbol(arbol, especie, catalogo, grupos):
    """Las referencias nuevas del árbol y el texto original de lo que no coincide con ellas."""
    originales = {}
    for campo in ("nombre_cientifico", "nombre_comun"):
        canonico = getattr(especie, campo) if especie else None
        if getattr(arbol, campo) != canonico:
            originales[campo] = getattr(arbol, campo)
    canonico = especie.origen.valor if especie and especie.origen else None
    if arbol.origen != canonico:
        originales[CAMPO_ORIGEN] = arbol.origen
    cambios = {"especie": especie}
    for campo in CAMPOS_ESTADO_ARBOL:
        texto = getattr(arbol, _texto_de_estado(campo))
        valor = catalogo.get((campo, normalizar(texto))) if texto else None
        cambios[campo] = valor
        if texto != (valor.valor if valor else None):
            originales[campo] = texto
    grupo = grupos.get(normalizar(arbol.brigada)) if arbol.brigada else None
    cambios["grupo"] = grupo
    if arbol.brigada != (grupo.brigada.nombre if grupo else None):
        originales["brigada"] = arbol.brigada
    cambios["valores_originales"] = originales
    return cambios


# --- hacia atrás ------------------------------------------------------------------------------


def volver_a_textos(apps, schema_editor):
    """Reescribe los textos del árbol desde sus referencias y las especies vuelven a ser fichas."""
    Arbol = apps.get_model("censo", "Arbol")
    relaciones = ("especie__origen", "grupo__brigada", *CAMPOS_ESTADO_ARBOL)
    for arbol in Arbol.objects.select_related(*relaciones).order_by("pk"):
        originales = arbol.valores_originales or {}
        especie, grupo = arbol.especie, arbol.grupo
        canonicos = {
            "nombre_cientifico": especie.nombre_cientifico if especie else None,
            "nombre_comun": especie.nombre_comun if especie else None,
            CAMPO_ORIGEN: especie.origen.valor if especie and especie.origen else None,
            "brigada": grupo.brigada.nombre if grupo else None,
        }
        for campo in CAMPOS_ESTADO_ARBOL:
            valor = getattr(arbol, campo)
            canonicos[_texto_de_estado(campo)] = valor.valor if valor else None
        textos = {}
        for columna, canonico in canonicos.items():
            campo = columna.removesuffix("_texto")
            textos[columna] = originales[campo] if campo in originales else canonico
        Arbol.objects.filter(pk=arbol.pk).update(**textos)
    _especies_a_fichas(apps)


def _especies_a_fichas(apps):
    FichaEspecie = apps.get_model("censo", "FichaEspecie")
    HistoricalFichaEspecie = apps.get_model("censo", "HistoricalFichaEspecie")
    Especie = apps.get_model("censo", "Especie")
    HistoricalEspecie = apps.get_model("censo", "HistoricalEspecie")
    ficha_de_especie = {}
    for especie in Especie.objects.exclude(fuente_ficha="").order_by("pk"):
        ficha_de_especie[especie.pk] = FichaEspecie.objects.create(
            **{**{campo: getattr(especie, campo) for campo in CAMPOS_FICHA}, "nombre_comun": especie.nombre_comun or ""},
            fuente=especie.fuente_ficha,
            publicada=especie.ficha_publicada,
        )
    for registro in HistoricalEspecie.objects.order_by("history_id"):
        ficha = ficha_de_especie.get(registro.id)
        if ficha is None:
            continue
        HistoricalFichaEspecie.objects.create(
            id=ficha.pk,
            **{campo: getattr(registro, campo) for campo in CAMPOS_FICHA},
            fuente=registro.fuente_ficha,
            publicada=registro.ficha_publicada,
            **{campo: getattr(registro, campo) for campo in CAMPOS_HISTORIAL},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("censo", "0010_especies_brigadas_y_catalogo"),
    ]

    operations = [
        migrations.RunPython(pasar_a_tablas, volver_a_textos),
    ]
