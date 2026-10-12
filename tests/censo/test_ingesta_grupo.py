"""La columna «Grupo» (opcional), «Brigada» y «Grupo» resueltos juntos, y la revisión de la especie.

Un grupo o una brigada que no se reconocen nunca mandan el árbol a revisión: el grupo es opcional.
Solo se informan y su texto queda en `valores_originales`.
"""

import pytest

from apps.censo.management.commands.importar_planilla import lineas_del_reporte
from apps.censo.models import Arbol, Brigada, Especie, GrupoBrigada, ValorCatalogo
from apps.censo.servicios.carga_planilla import aplicar_decisiones, evaluar
from apps.censo.servicios.importar_planilla import importar_planilla
from apps.censo.servicios.lectura_planilla import leer
from apps.censo.servicios.lote_carga import valores_activos_del_catalogo
from apps.censo.servicios.resolver_campos import resolver_valores, texto_de
from config.constantes import (
    CAMPOS_ESTADO_ARBOL,
    COLUMNAS_OPCIONALES_PLANILLA,
    DECISION_CONSERVAR,
    ESTADO_REGISTRO_EN_REVISION,
    ESTADO_REGISTRO_PUBLICADO,
    PREFIJO_CAMPO_CARGA,
    PREFIJO_CONSERVAR_CARGA,
)
from tests.censo.conftest import (
    MEDIDAS_FILA_COMPLETA,
    TEXTOS_FILA_COMPLETA,
    crear_planilla,
    fila,
)
from tests.censo.test_carga_planilla import cargar, fila_buena, fila_del_lote, texto, url

CODIGO = "S01-A001"
ENCABEZADO_GRUPO = "Grupo"
ENCABEZADO_AJENO = "Nombre científico original"


@pytest.fixture(autouse=True)
def molle(especie_molle):
    return especie_molle


@pytest.fixture(autouse=True)
def catalogo_de_la_fila_completa(db):
    """Los estados de la fila completa están en el catálogo: lo que falle será por otra cosa."""
    for campo in CAMPOS_ESTADO_ARBOL:
        ValorCatalogo.objects.create(
            campo=campo, valor=TEXTOS_FILA_COMPLETA[campo], explicacion="x"
        )


def fila_completa(punto, **extra):
    este, norte = punto
    datos = {**TEXTOS_FILA_COMPLETA, **MEDIDAS_FILA_COMPLETA, "utm_este_m": este}
    return fila(**{**datos, "utm_norte_m": norte, **extra})


def importar(ruta_planilla, filas, **opciones):
    crear_planilla(ruta_planilla, filas, **opciones)
    return importar_planilla(ruta_planilla)


def grupo_de(nombre, brigada="Brigada A"):
    return GrupoBrigada.objects.get(brigada__nombre=brigada, nombre=nombre)


# --- la columna es opcional --------------------------------------------------------------------


def test_grupo_es_una_columna_opcional_de_la_planilla():
    assert COLUMNAS_OPCIONALES_PLANILLA == {ENCABEZADO_GRUPO: "grupo"}


def test_una_planilla_sin_la_columna_grupo_se_lee_y_se_importa(ruta_planilla, punto_dentro):
    crear_planilla(ruta_planilla, [fila_completa(punto_dentro)], sin_columnas=(ENCABEZADO_GRUPO,))

    ((_, datos),) = leer(ruta_planilla).filas
    reporte = importar_planilla(ruta_planilla)

    assert "grupo" not in datos
    assert reporte.creados == 1
    assert Arbol.objects.get(codigo=CODIGO).grupo is None


def test_la_columna_grupo_se_lee_y_las_columnas_ajenas_se_ignoran(ruta_planilla, punto_dentro):
    crear_planilla(
        ruta_planilla,
        [fila_completa(punto_dentro, grupo="zapato")],
        columnas_ajenas=(ENCABEZADO_AJENO,),
    )

    ((_, datos),) = leer(ruta_planilla).filas

    assert datos["grupo"] == "zapato"
    assert ENCABEZADO_AJENO not in datos
    assert all(valor != ENCABEZADO_AJENO for valor in datos)


# --- «Grupo» resuelto --------------------------------------------------------------------------


def test_el_grupo_se_resuelve_por_nombre_sin_importar_mayusculas_ni_espacios(
    ruta_planilla, punto_dentro
):
    importar(ruta_planilla, [fila_completa(punto_dentro, grupo="  ZAPATO ")])

    arbol = Arbol.objects.get(codigo=CODIGO)
    assert arbol.grupo == grupo_de("zapato")
    assert texto_de(arbol, "brigada") == "Brigada A"
    assert "grupo" not in arbol.valores_originales
    assert arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO


def test_el_grupo_se_resuelve_por_alias(ruta_planilla, punto_dentro):
    GrupoBrigada.objects.filter(nombre="Sopita").update(alias="la sopa")

    importar(ruta_planilla, [fila_completa(punto_dentro, grupo=" LA   Sopa ")])

    assert Arbol.objects.get(codigo=CODIGO).grupo == grupo_de("Sopita")


def test_si_brigada_trae_el_nombre_de_una_brigada_y_grupo_el_de_su_grupo_quedan_los_dos(
    ruta_planilla, punto_dentro
):
    importar(ruta_planilla, [fila_completa(punto_dentro, brigada="brigada a", grupo="Sopita")])

    arbol = Arbol.objects.get(codigo=CODIGO)
    assert arbol.grupo == grupo_de("Sopita")
    assert not {"brigada", "grupo"} & arbol.valores_originales.keys()


def test_la_columna_grupo_manda_sobre_una_brigada_que_trae_el_nombre_de_otro_grupo(
    ruta_planilla, punto_dentro
):
    importar(ruta_planilla, [fila_completa(punto_dentro, brigada="Sopita", grupo="zapato")])

    arbol = Arbol.objects.get(codigo=CODIGO)
    assert arbol.grupo == grupo_de("zapato")
    assert arbol.valores_originales["brigada"] == "Sopita"


def test_con_el_mismo_nombre_de_grupo_en_dos_brigadas_decide_la_brigada():
    otra = Brigada.objects.create(nombre="Brigada B")
    zapato_b = GrupoBrigada.objects.create(brigada=otra, nombre="zapato")

    de_b = resolver_valores({"brigada": "Brigada B", "grupo": "zapato"})
    de_a = resolver_valores({"brigada": "Brigada A", "grupo": "zapato"})
    ambiguo = resolver_valores({"brigada": "Brigada C", "grupo": "zapato"})

    assert de_b["grupo"] == zapato_b
    assert de_a["grupo"] == grupo_de("zapato")
    assert ambiguo["grupo"] is None
    assert ambiguo["valores_originales"] == {"brigada": "Brigada C", "grupo": "zapato"}


# --- lo que no se resuelve se informa y no manda a revisión ------------------------------------


def test_un_grupo_desconocido_queda_en_los_originales_y_el_arbol_se_publica(
    ruta_planilla, punto_dentro
):
    reporte = importar(ruta_planilla, [fila_completa(punto_dentro, grupo="Cóndores")])

    arbol = Arbol.objects.get(codigo=CODIGO)
    assert arbol.grupo is None
    assert arbol.valores_originales["grupo"] == "Cóndores"
    assert arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO
    assert [(v.codigo, v.columna, v.texto) for v in reporte.sin_resolver] == [
        (CODIGO, ENCABEZADO_GRUPO, "Cóndores")
    ]
    assert reporte.en_revision == []


def test_una_brigada_desconocida_se_informa_y_una_brigada_conocida_sin_grupo_no(
    ruta_planilla, punto_dentro
):
    reporte = importar(
        ruta_planilla,
        [
            fila_completa(punto_dentro, codigo="S01-A001", brigada="Brigada Z"),
            fila_completa(
                punto_dentro,
                codigo="S01-A002",
                brigada="Brigada A",
                utm_este_m=punto_dentro[0] + 1,
            ),
        ],
    )

    assert [(v.codigo, v.columna, v.texto) for v in reporte.sin_resolver] == [
        ("S01-A001", "Brigada", "Brigada Z")
    ]
    sin_grupo = Arbol.objects.get(codigo="S01-A002")
    assert sin_grupo.grupo is None
    assert texto_de(sin_grupo, "brigada") == "Brigada A"
    assert sin_grupo.estado_registro == ESTADO_REGISTRO_PUBLICADO


def test_los_textos_sin_resolver_de_especie_y_estado_tambien_se_informan(
    ruta_planilla, punto_dentro
):
    reporte = importar(
        ruta_planilla,
        [fila_completa(punto_dentro, nombre_cientifico="Quercus robur", estado_general="Raro")],
    )

    informados = {(v.columna, v.texto) for v in reporte.sin_resolver}
    assert ("Nombre científico", "Quercus robur") in informados
    assert ("Estado general", "Raro") in informados


def test_una_celda_vacia_de_grupo_no_borra_el_grupo_de_un_arbol_que_ya_existe(
    ruta_planilla, punto_dentro
):
    importar(ruta_planilla, [fila_completa(punto_dentro, grupo="zapato")])
    crear_planilla(ruta_planilla, [fila_completa(punto_dentro, grupo=None)])
    evaluacion = evaluar(leer(ruta_planilla))
    decisiones = {f.numero_fila: DECISION_CONSERVAR for f in evaluacion.filas}

    aplicar_decisiones(evaluacion, decisiones, conservar_existentes=True)

    assert Arbol.objects.get(codigo=CODIGO).grupo == grupo_de("zapato")


def test_la_consola_separa_lo_que_no_se_resolvio_de_la_brigada_y_el_grupo(
    ruta_planilla, punto_dentro
):
    reporte = importar(
        ruta_planilla,
        [fila_completa(punto_dentro, grupo="Cóndores", estado_general="Raro")],
    )

    lineas = lineas_del_reporte(reporte)

    assert "Textos sin resolver (quedan en valores_originales): 1" in lineas
    assert f"  {CODIGO} · Estado general: «Raro»" in lineas
    assert "Brigada o grupo sin resolver (solo informativo, no manda a revisión): 1" in lineas
    assert f"  {CODIGO} · Grupo: «Cóndores»" in lineas


# --- la revisión ofrece las especies existentes ------------------------------------------------


def test_el_selector_de_la_revision_ofrece_las_especies_por_nombre_cientifico(db):
    Especie.objects.create(nombre_cientifico="Roystonea regia")

    activos = valores_activos_del_catalogo()

    assert activos["nombre_cientifico"] == ["Roystonea regia", "Schinus molle"]


def test_la_revision_de_una_especie_no_registrada_es_una_lista_de_las_existentes(
    cliente_administrador, tmp_path, punto_dentro
):
    Especie.objects.create(nombre_cientifico="Roystonea regia")
    lote = cargar(
        cliente_administrador,
        tmp_path,
        [fila_buena(punto_dentro, CODIGO, nombre_cientifico="Quercus robur")],
    )

    cuerpo = texto(cliente_administrador.get(url("revisar", lote)))

    pk = fila_del_lote(lote, CODIGO).pk
    assert f'<select name="{PREFIJO_CAMPO_CARGA}{pk}-nombre_cientifico"' in cuerpo
    assert ">Schinus molle<" in cuerpo and ">Roystonea regia<" in cuerpo
    assert "Quercus robur" in cuerpo  # lo que llegó se ve, para saber qué se cambia


def test_elegir_una_especie_de_la_lista_re_evalua_el_registro_y_lo_publica(
    cliente_administrador, tmp_path, punto_dentro
):
    lote = cargar(
        cliente_administrador,
        tmp_path,
        [fila_buena(punto_dentro, CODIGO, nombre_cientifico="Quercus robur")],
    )
    pk = fila_del_lote(lote, CODIGO).pk
    datos = {
        f"{PREFIJO_CAMPO_CARGA}{pk}-nombre_cientifico": "Schinus molle",
        f"{PREFIJO_CONSERVAR_CARGA}{pk}": "on",
    }

    cliente_administrador.post(url("revisar", lote), datos)

    arbol = Arbol.objects.get(codigo=CODIGO)
    assert arbol.especie == Especie.objects.get(nombre_cientifico="Schinus molle")
    assert arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO
    assert Especie.objects.count() == 1


def test_sin_elegir_especie_el_registro_conservado_queda_en_revision(
    cliente_administrador, tmp_path, punto_dentro
):
    lote = cargar(
        cliente_administrador,
        tmp_path,
        [fila_buena(punto_dentro, CODIGO, nombre_cientifico="Quercus robur")],
    )
    pk = fila_del_lote(lote, CODIGO).pk

    cliente_administrador.post(url("revisar", lote), {f"{PREFIJO_CONSERVAR_CARGA}{pk}": "on"})

    arbol = Arbol.objects.get(codigo=CODIGO)
    assert arbol.especie is None
    assert arbol.estado_registro == ESTADO_REGISTRO_EN_REVISION
