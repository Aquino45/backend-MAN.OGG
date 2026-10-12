"""La ingesta de la planilla resuelve el texto a especie, catálogo y grupo; lo demás va a revisión.

Cubre la consola (`importar_planilla`) y la carga del panel (`aplicar_decisiones` con
`conservar_existentes`). La ingesta nunca crea una especie.
"""

import pytest

from apps.censo.models import Arbol, Especie, GrupoBrigada, ValorCatalogo
from apps.censo.servicios.carga_planilla import aplicar_decisiones, evaluar
from apps.censo.servicios.importar_planilla import importar_planilla
from apps.censo.servicios.lectura_planilla import leer
from apps.censo.servicios.resolver_campos import texto_de
from config.constantes import (
    DECISION_CONSERVAR,
    ESTADO_REGISTRO_EN_REVISION,
    ESTADO_REGISTRO_PUBLICADO,
    MOTIVO_ESPECIE_NO_REGISTRADA,
)
from tests.censo.conftest import (
    MEDIDAS_FILA_COMPLETA,
    TEXTOS_FILA_COMPLETA,
    crear_planilla,
    fila,
)

CODIGO = "S01-A001"


@pytest.fixture
def molle(db):
    return Especie.objects.create(
        nombre_cientifico="Schinus molle", nombre_comun="Molle", alias="Schinus\nSchinus Molle"
    )


def fila_completa(punto, **extra):
    este, norte = punto
    datos = {**TEXTOS_FILA_COMPLETA, **MEDIDAS_FILA_COMPLETA, "utm_este_m": este}
    return fila(**{**datos, "utm_norte_m": norte, **extra})


def importar(ruta_planilla, filas):
    crear_planilla(ruta_planilla, filas)
    return importar_planilla(ruta_planilla)


def test_el_nombre_por_alias_deja_al_arbol_con_la_especie_y_anota_el_original(
    ruta_planilla, punto_dentro, molle
):
    importar(ruta_planilla, [fila_completa(punto_dentro, nombre_cientifico="schinus")])

    arbol = Arbol.objects.get(codigo=CODIGO)
    assert arbol.especie == molle
    assert texto_de(arbol, "nombre_cientifico") == "Schinus molle"
    assert arbol.valores_originales["nombre_cientifico"] == "schinus"
    assert arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO


def test_un_nombre_sin_especie_registrada_va_a_revision_y_no_crea_la_especie(
    ruta_planilla, punto_dentro, molle
):
    reporte = importar(
        ruta_planilla, [fila_completa(punto_dentro, nombre_cientifico="Quercus robur")]
    )

    arbol = Arbol.objects.get(codigo=CODIGO)
    assert arbol.especie is None
    assert arbol.estado_registro == ESTADO_REGISTRO_EN_REVISION
    assert MOTIVO_ESPECIE_NO_REGISTRADA.format(texto="Quercus robur") in arbol.motivos_revision
    assert Especie.objects.count() == 1
    assert [r.codigo for r in reporte.en_revision] == [CODIGO]


def test_un_nombre_que_coincide_con_dos_especies_va_a_revision(ruta_planilla, punto_dentro, molle):
    Especie.objects.create(nombre_cientifico="Schinus areira", alias="Schinus")

    importar(ruta_planilla, [fila_completa(punto_dentro, nombre_cientifico="Schinus")])

    arbol = Arbol.objects.get(codigo=CODIGO)
    assert arbol.especie is None
    assert "Especie no registrada" in arbol.motivos_revision


def test_un_estado_fuera_del_catalogo_queda_en_los_originales_y_va_a_revision(
    ruta_planilla, punto_dentro, molle
):
    ValorCatalogo.objects.create(campo="estado_general", valor="Bueno", explicacion="x")

    importar(ruta_planilla, [fila_completa(punto_dentro, estado_general="Excelente")])

    arbol = Arbol.objects.get(codigo=CODIGO)
    assert arbol.estado_general is None
    assert arbol.valores_originales["estado_general"] == "Excelente"
    assert arbol.estado_registro == ESTADO_REGISTRO_EN_REVISION
    assert "Valor fuera del catálogo en Estado general: «Excelente»" in arbol.motivos_revision


def test_un_estado_del_catalogo_se_guarda_como_referencia(ruta_planilla, punto_dentro, molle):
    bueno = ValorCatalogo.objects.create(campo="estado_general", valor="Bueno", explicacion="x")

    importar(ruta_planilla, [fila_completa(punto_dentro, estado_general=" bueno ")])

    arbol = Arbol.objects.get(codigo=CODIGO)
    assert arbol.estado_general == bueno
    assert texto_de(arbol, "estado_general") == "Bueno"


def test_la_brigada_que_trae_el_nombre_de_un_grupo_se_guarda_en_ese_grupo(
    ruta_planilla, punto_dentro, molle
):
    importar(ruta_planilla, [fila_completa(punto_dentro, brigada="sopita")])

    arbol = Arbol.objects.get(codigo=CODIGO)
    assert arbol.grupo == GrupoBrigada.objects.get(nombre="Sopita")
    assert texto_de(arbol, "brigada") == "Brigada A"
    assert arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO


def test_una_brigada_sin_grupo_no_manda_el_arbol_a_revision(ruta_planilla, punto_dentro, molle):
    importar(ruta_planilla, [fila_completa(punto_dentro, brigada="Brigada A")])

    arbol = Arbol.objects.get(codigo=CODIGO)
    assert arbol.grupo is None
    assert arbol.valores_originales["brigada"] == "Brigada A"
    assert arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO


def test_la_misma_especie_con_la_misma_ubicacion_es_duplicado_aunque_llegue_por_alias(
    ruta_planilla, punto_dentro, molle
):
    reporte = importar(
        ruta_planilla,
        [
            fila_completa(punto_dentro, codigo="S01-A001"),
            fila_completa(punto_dentro, codigo="S01-A002", nombre_cientifico="Schinus"),
        ],
    )

    assert [d.codigo for d in reporte.duplicados] == ["S01-A002"]
    assert Arbol.objects.count() == 1


# --- la carga del panel: un dato que ya existe no se pierde ------------------------------------


def aplicar_en_el_panel(ruta_planilla, filas):
    crear_planilla(ruta_planilla, filas)
    evaluacion = evaluar(leer(ruta_planilla))
    decisiones = {f.numero_fila: DECISION_CONSERVAR for f in evaluacion.filas}
    return aplicar_decisiones(evaluacion, decisiones, conservar_existentes=True)


def test_una_celda_vacia_no_borra_la_especie_ni_los_originales_del_arbol_que_ya_existe(
    ruta_planilla, punto_dentro, molle
):
    importar(ruta_planilla, [fila_completa(punto_dentro, estado_general="Excelente")])
    antes = Arbol.objects.get(codigo=CODIGO)

    aplicar_en_el_panel(
        ruta_planilla,
        [
            fila_completa(
                punto_dentro,
                nombre_cientifico=None,
                nombre_comun=None,
                estado_general=None,
                estado_copa=None,
            )
        ],
    )

    despues = Arbol.objects.get(codigo=CODIGO)
    assert despues.especie == antes.especie == molle
    assert despues.valores_originales["estado_general"] == "Excelente"


def test_lo_que_ahora_se_resuelve_deja_de_estar_en_los_originales(
    ruta_planilla, punto_dentro, molle
):
    importar(ruta_planilla, [fila_completa(punto_dentro, estado_general="Excelente")])
    excelente = ValorCatalogo.objects.create(
        campo="estado_general", valor="Excelente", explicacion="x"
    )

    aplicar_en_el_panel(ruta_planilla, [fila_completa(punto_dentro, estado_general="Excelente")])

    arbol = Arbol.objects.get(codigo=CODIGO)
    assert arbol.estado_general == excelente
    assert "estado_general" not in arbol.valores_originales
    assert arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO
