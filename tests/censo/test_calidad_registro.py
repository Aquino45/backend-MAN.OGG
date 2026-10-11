"""Tests de la regla de calidad: qué manda un registro a revisión y qué lo deja publicado."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.contrib.gis.geos import Point, Polygon

from apps.censo.models import Arbol, ValorCatalogo
from apps.censo.servicios.calidad_registro import (
    aplicar,
    aviso_catalogo_sin_cargar,
    buscar_duplicado_por_ubicacion,
    cargar_catalogo,
    evaluar,
    recalcular_calidad,
)
from apps.censo.servicios.capsulas import normalizar
from config.constantes import (
    CAMPOS_CATALOGADOS,
    CAMPOS_OBLIGATORIOS_CALIDAD,
    CAMPOS_OPCIONALES_CALIDAD,
    ESTADO_REGISTRO_EN_REVISION,
    ESTADO_REGISTRO_PUBLICADO,
    SRID_UTM_CENSO,
    TOLERANCIA_FUERA_DE_SECTOR_M,
    VALOR_TIPO_JUVENIL,
)
from tests.censo.conftest import arbol_evaluado, valores_de_arbol_completo

LADO_SECTOR_M = 100
SECTOR_DE_PRUEBA = Polygon.from_bbox((0, 0, LADO_SECTOR_M, LADO_SECTOR_M))
SECTOR_DE_PRUEBA.srid = SRID_UTM_CENSO
CENTRO = (50, 50)


def arbol_en_memoria(**cambios):
    """Árbol completo sin guardar, con su punto en el centro del sector de prueba."""
    valores = valores_de_arbol_completo()
    valores["ubicacion"] = Point(*CENTRO, srid=SRID_UTM_CENSO)
    valores.update(cambios)
    return Arbol(codigo="S01-A001", sector_id=1, fuente="Prueba", **valores)


def campos_de(motivos):
    return [motivo.campo for motivo in motivos]


def evaluar_en_sector(arbol, catalogo=None, **extra):
    return evaluar(arbol, catalogo, SECTOR_DE_PRUEBA, **extra)


def test_un_arbol_completo_y_consistente_se_publica():
    assert evaluar_en_sector(arbol_en_memoria()) == []


@pytest.mark.parametrize("campo", CAMPOS_OBLIGATORIOS_CALIDAD)
def test_cada_campo_obligatorio_vacio_da_su_motivo(campo):
    motivos = evaluar_en_sector(arbol_en_memoria(**{campo: None}))

    assert campos_de(motivos) == [campo]
    assert "Falta" in motivos[0].porque


@pytest.mark.parametrize("vacio", ["", "   "])
def test_un_texto_en_blanco_cuenta_como_vacio(vacio):
    assert campos_de(evaluar_en_sector(arbol_en_memoria(nombre_comun=vacio))) == ["nombre_comun"]


@pytest.mark.parametrize("campo", CAMPOS_OPCIONALES_CALIDAD)
def test_los_campos_opcionales_vacios_no_mandan_a_revision(campo):
    assert evaluar_en_sector(arbol_en_memoria(**{campo: None})) == []


def test_el_motivo_dice_el_campo_y_el_porque_en_lenguaje_simple():
    motivo = evaluar_en_sector(arbol_en_memoria(nombre_cientifico=None))[0]

    assert motivo.campo == "nombre_cientifico"
    assert motivo.porque == "Falta el dato «Nombre científico»"


def test_un_juvenil_sin_dap_se_publica():
    arbol = arbol_en_memoria(tipo_individuo=VALOR_TIPO_JUVENIL, dap_cm=None)

    assert evaluar_en_sector(arbol) == []


def test_un_juvenil_se_reconoce_normalizado():
    arbol = arbol_en_memoria(tipo_individuo="  juvenil <1.30 M (sin dap) ", dap_cm=None)

    assert evaluar_en_sector(arbol) == []


def test_un_no_juvenil_sin_dap_va_a_revision():
    assert campos_de(evaluar_en_sector(arbol_en_memoria(dap_cm=None))) == ["dap_cm"]


def test_un_juvenil_sigue_sin_poder_traer_un_dap_fuera_de_rango():
    arbol = arbol_en_memoria(tipo_individuo=VALOR_TIPO_JUVENIL, dap_cm=Decimal("5000"))

    assert campos_de(evaluar_en_sector(arbol)) == ["dap_cm"]


def test_brigada_vacia_se_exige_solo_a_un_arbol_real():
    assert campos_de(evaluar_en_sector(arbol_en_memoria(demo=False, brigada=None))) == ["brigada"]
    assert evaluar_en_sector(arbol_en_memoria(demo=True, brigada=None)) == []


def test_un_destacado_sin_motivo_se_publica():
    arbol = arbol_en_memoria(destacado=True, motivo_destacado=None)

    assert evaluar_en_sector(arbol) == []


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("dap_cm", 0),
        ("dap_cm", -1),
        ("dap_cm", 1000.001),
        ("altura_total_m", 0),
        ("altura_total_m", 60.5),
        ("copa_ns_m", -0.1),
        ("copa_eo_m", 50.1),
        ("co2_almacenado_kg", -1),
        ("co2_captura_anual_kg", -0.5),
    ],
)
def test_una_medida_fuera_de_rango_va_a_revision(campo, valor):
    motivos = evaluar_en_sector(arbol_en_memoria(**{campo: Decimal(str(valor))}))

    assert campos_de(motivos) == [campo]
    assert "fuera de rango" in motivos[0].porque


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("dap_cm", 1000),
        ("altura_total_m", 60),
        ("copa_ns_m", 0),
        ("copa_eo_m", 50),
        ("co2_almacenado_kg", 0),
        ("co2_captura_anual_kg", 100000),
    ],
)
def test_una_medida_en_el_borde_del_rango_se_publica(campo, valor):
    assert evaluar_en_sector(arbol_en_memoria(**{campo: Decimal(valor)})) == []


def test_un_texto_donde_va_un_numero_va_a_revision_con_el_texto():
    arbol = arbol_en_memoria(dap_cm=None)

    motivos = evaluar_en_sector(arbol, textos_no_numericos={"dap_cm": "muerto"})

    assert [str(motivo) for motivo in motivos] == ["DAP no es un número: «muerto»"]


def test_un_texto_donde_va_un_numero_manda_aunque_sea_juvenil():
    arbol = arbol_en_memoria(tipo_individuo=VALOR_TIPO_JUVENIL, dap_cm=None)

    motivos = evaluar_en_sector(arbol, textos_no_numericos={"dap_cm": "muerto"})

    assert campos_de(motivos) == ["dap_cm"]


def catalogo_de_prueba():
    return {campo: {normalizar(getattr(arbol_en_memoria(), campo))} for campo in CAMPOS_CATALOGADOS}


def test_un_valor_del_catalogo_se_compara_normalizado():
    """«bueno » es lo mismo que «Bueno»: pasa."""
    catalogo = catalogo_de_prueba()
    catalogo["estado_general"] = {normalizar("Bueno")}

    assert evaluar_en_sector(arbol_en_memoria(estado_general="bueno  "), catalogo) == []


def test_un_valor_fuera_del_catalogo_va_a_revision():
    catalogo = catalogo_de_prueba()
    catalogo["estado_general"] = {normalizar("Bueno")}

    motivos = evaluar_en_sector(arbol_en_memoria(estado_general="Excelente"), catalogo)

    assert [str(motivo) for motivo in motivos] == [
        "Valor fuera del catálogo en Estado general: «Excelente»"
    ]


def test_una_condicion_de_conservacion_fuera_del_catalogo_tambien_manda_a_revision():
    catalogo = catalogo_de_prueba()

    motivos = evaluar_en_sector(arbol_en_memoria(condicion_conservacion="Rara"), catalogo)

    assert campos_de(motivos) == ["condicion_conservacion"]


def test_un_campo_con_catalogo_vacio_no_se_evalua():
    catalogo = catalogo_de_prueba()
    catalogo["estado_general"] = set()

    assert evaluar_en_sector(arbol_en_memoria(estado_general="Cualquiera"), catalogo) == []


@pytest.mark.parametrize(
    ("este_m", "publicado"),
    [
        (LADO_SECTOR_M, True),  # en el borde
        (LADO_SECTOR_M + 6, True),  # como S01-A018: a 6 m
        (LADO_SECTOR_M + TOLERANCIA_FUERA_DE_SECTOR_M, True),  # justo en la tolerancia
        (LADO_SECTOR_M + 20, False),
    ],
)
def test_la_ubicacion_se_tolera_hasta_la_distancia_de_la_constante(este_m, publicado):
    arbol = arbol_en_memoria(ubicacion=Point(este_m, 50, srid=SRID_UTM_CENSO))

    motivos = evaluar_en_sector(arbol)

    assert (motivos == []) is publicado
    if not publicado:
        assert campos_de(motivos) == ["ubicacion"]
        assert "20.0 m del sector" in motivos[0].porque


def test_sin_poligono_no_se_mira_la_ubicacion_contra_el_sector():
    arbol = arbol_en_memoria(ubicacion=Point(5000, 5000, srid=SRID_UTM_CENSO))

    assert evaluar(arbol, None, None) == []


def test_los_motivos_se_acumulan():
    arbol = arbol_en_memoria(nombre_comun=None, altura_total_m=Decimal("99"))

    assert campos_de(evaluar_en_sector(arbol)) == ["nombre_comun", "altura_total_m"]


def test_aplicar_pone_estado_y_motivos_uno_por_linea():
    arbol = arbol_en_memoria(nombre_comun=None, origen=None)

    motivos = aplicar(arbol, {}, SECTOR_DE_PRUEBA)

    assert arbol.estado_registro == ESTADO_REGISTRO_EN_REVISION
    assert arbol.motivos_revision == "\n".join(str(motivo) for motivo in motivos)
    assert arbol.motivos_revision.count("\n") == 1


def test_aplicar_publica_y_borra_los_motivos_de_un_registro_que_ya_esta_bien():
    arbol = arbol_en_memoria()
    arbol.estado_registro, arbol.motivos_revision = ESTADO_REGISTRO_EN_REVISION, "viejo"

    assert aplicar(arbol, {}, SECTOR_DE_PRUEBA) == []

    assert arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO
    assert arbol.motivos_revision == ""


def test_un_arbol_nuevo_nace_en_revision(sectores):
    arbol = Arbol.objects.create(codigo="S01-A001", sector_id=1, fuente="Prueba")

    assert arbol.estado_registro == ESTADO_REGISTRO_EN_REVISION
    assert arbol.motivos_revision == ""


# --- Con la BD ---------------------------------------------------------------------------------


def test_el_helper_de_tests_crea_un_arbol_real_publicado(sectores):
    arbol = arbol_evaluado()

    assert arbol.demo is False
    assert arbol.brigada
    assert arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO


def test_el_helper_de_tests_crea_un_arbol_de_ejemplo_publicado_sin_brigada(sectores):
    arbol = arbol_evaluado("S02-D001", sector_id=2, demo=True, brigada=None)

    assert arbol.demo is True
    assert arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO


def test_aplicar_lee_el_poligono_del_sector_de_la_bd(sectores):
    arbol = arbol_evaluado()
    arbol.ubicacion = Point(0, 0, srid=SRID_UTM_CENSO)

    motivos = aplicar(arbol)

    assert campos_de(motivos) == ["ubicacion"]


def test_el_catalogo_cuenta_tambien_los_valores_inactivos(db):
    ValorCatalogo.objects.create(campo="estado_general", valor="Bueno", explicacion="x")
    ValorCatalogo.objects.create(
        campo="estado_general", valor="Pésimo", explicacion="x", activo=False
    )

    assert cargar_catalogo() == {"estado_general": {"bueno", "pesimo"}}


def test_el_aviso_nombra_los_campos_sin_catalogo(db):
    ValorCatalogo.objects.create(campo="estado_general", valor="Bueno", explicacion="x")

    aviso = aviso_catalogo_sin_cargar(cargar_catalogo())

    assert aviso.startswith("Catálogo sin cargar en: ")
    assert "estado_general" not in aviso
    assert "origen" in aviso


def test_sin_campos_sin_catalogo_no_hay_aviso(db):
    for campo in CAMPOS_CATALOGADOS:
        ValorCatalogo.objects.create(campo=campo, valor="Algo", explicacion="x")

    assert aviso_catalogo_sin_cargar(cargar_catalogo()) is None


def test_recalcular_calidad_evalua_a_todos_y_es_idempotente(sectores):
    bueno = arbol_evaluado("S01-A001")
    malo = arbol_evaluado("S01-A002", nombre_comun=None)
    Arbol.todos.filter(pk__in=[bueno.pk, malo.pk]).update(
        estado_registro=ESTADO_REGISTRO_EN_REVISION, motivos_revision=""
    )

    primera = recalcular_calidad()
    segunda = recalcular_calidad()

    bueno.refresh_from_db()
    malo.refresh_from_db()
    assert bueno.estado_registro == ESTADO_REGISTRO_PUBLICADO
    assert malo.estado_registro == ESTADO_REGISTRO_EN_REVISION
    assert "Nombre común" in malo.motivos_revision
    assert (primera.revisados, primera.publicados, primera.en_revision) == (2, 1, 1)
    assert primera.cambiaron == 2
    assert segunda.cambiaron == 0


def test_recalcular_calidad_deja_rastro_en_el_historial(sectores):
    arbol = arbol_evaluado("S01-A001")
    Arbol.todos.filter(pk=arbol.pk).update(estado_registro=ESTADO_REGISTRO_EN_REVISION)

    recalcular_calidad()

    ultimo = arbol.history.first()
    assert ultimo.history_change_reason == "Recálculo de la calidad del registro"
    assert ultimo.estado_registro == ESTADO_REGISTRO_PUBLICADO


def test_recalcular_calidad_incluye_los_de_la_papelera(sectores):
    arbol = arbol_evaluado("S01-A001", eliminado_en=datetime.now(tz=UTC))
    Arbol.todos.filter(pk=arbol.pk).update(estado_registro=ESTADO_REGISTRO_EN_REVISION)

    assert recalcular_calidad().revisados == 1


def test_buscar_duplicado_misma_ubicacion_y_misma_especie(sectores):
    existente = arbol_evaluado("S01-A001")

    encontrado = buscar_duplicado_por_ubicacion(
        "S01-A002", existente.ubicacion, existente.nombre_cientifico.upper()
    )

    assert encontrado == "S01-A001"


def test_no_es_duplicado_con_otra_especie_ni_con_su_propio_codigo(sectores):
    existente = arbol_evaluado("S01-A001")

    assert buscar_duplicado_por_ubicacion("S01-A002", existente.ubicacion, "Otra especie") is None
    assert (
        buscar_duplicado_por_ubicacion("S01-A001", existente.ubicacion, existente.nombre_cientifico)
        is None
    )
    assert buscar_duplicado_por_ubicacion("S01-A002", None, existente.nombre_cientifico) is None
