"""Tests del resolver: del texto de la planilla a la especie, el catálogo y el grupo, y vuelta."""

import pytest

from apps.censo.models import Arbol, Brigada, Especie, GrupoBrigada, ValorCatalogo
from apps.censo.servicios.calidad_registro import aplicar
from apps.censo.servicios.resolver_campos import (
    Resolutor,
    aplicar_textos,
    fusionar_originales,
    nombre_cientifico_de,
    resolver_especie,
    resolver_grupo,
    resolver_valor,
    resolver_valores,
    texto_de,
    valores_sobre_existente,
)
from config.constantes.catalogos import MOTIVO_ESPECIE_NO_REGISTRADA
from tests.censo.conftest import arbol_evaluado

pytestmark = pytest.mark.django_db


@pytest.fixture
def molle():
    return Especie.objects.create(
        nombre_cientifico="Schinus molle", nombre_comun="Molle", alias="Schinus\nSchinus Molle"
    )


@pytest.fixture
def grupo():
    """El grupo «Sopita» que siembra la migración de datos, con un alias."""
    grupo = GrupoBrigada.objects.get(brigada__nombre="Brigada A", nombre="Sopita")
    grupo.alias = "la sopa"
    grupo.save()
    return grupo


def crear_valor(campo="estado_general", valor="Bueno", **extra):
    return ValorCatalogo.objects.create(campo=campo, valor=valor, explicacion="x", **extra)


# --- especie ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto", ["Schinus molle", "  schinus   MOLLE ", "SCHINUS", "schinus molle", "molle", "MOLLE"]
)
def test_la_especie_se_busca_normalizada_por_nombre_cientifico_alias_o_nombre_comun(molle, texto):
    assert resolver_especie(texto) == molle


def test_una_tilde_o_un_espacio_de_mas_no_cambian_la_especie():
    especie = Especie.objects.create(nombre_cientifico="Prosopis pallida", alias="Algarrobo")

    assert resolver_especie("  ALGARROBO ") == especie
    assert resolver_especie("Prosopis  Pallida") == especie


@pytest.mark.parametrize("texto", [None, "", "   ", "Otra especie"])
def test_sin_coincidencia_no_hay_especie_y_nunca_se_crea(molle, texto):
    assert resolver_especie(texto) is None
    assert Especie.objects.count() == 1


def test_un_nombre_que_coincide_con_varias_especies_no_se_resuelve():
    Especie.objects.create(nombre_cientifico="Prosopis pallida", alias="Algarrobo")
    Especie.objects.create(nombre_cientifico="Prosopis juliflora", alias="Algarrobo")

    assert resolver_especie("algarrobo") is None


# --- catálogo y grupo -------------------------------------------------------------------------


def test_el_valor_se_busca_en_el_catalogo_de_su_campo_y_normalizado():
    bueno = crear_valor()
    crear_valor("estado_copa", "Bueno")

    assert resolver_valor("estado_general", " bueno ") == bueno
    assert resolver_valor("estado_general", "Excelente") is None
    assert resolver_valor("estado_general", None) is None


def test_un_valor_inactivo_tambien_se_resuelve():
    inactivo = crear_valor(activo=False)

    assert resolver_valor("estado_general", "Bueno") == inactivo


def test_el_grupo_se_busca_por_nombre_o_alias(grupo):
    assert resolver_grupo("sopita") == grupo
    assert resolver_grupo(" LA   sopa ") == grupo
    assert resolver_grupo("Brigada A") is None
    assert resolver_grupo(None) is None


def test_un_nombre_de_grupo_repetido_en_dos_brigadas_no_se_resuelve(grupo):
    otra = Brigada.objects.create(nombre="Brigada B")
    GrupoBrigada.objects.create(brigada=otra, nombre="Sopita")

    assert resolver_grupo("Sopita") is None


# --- resolver_valores: las referencias y lo que queda en valores_originales ---------------------


def test_un_nombre_por_alias_resuelve_la_especie_y_anota_el_texto_original(molle):
    bueno = crear_valor()

    resueltos = resolver_valores(
        {"nombre_cientifico": "Schinus", "nombre_comun": "Molle", "estado_general": "Bueno"}
    )

    assert resueltos["especie"] == molle
    assert resueltos["estado_general"] == bueno
    assert resueltos["valores_originales"] == {"nombre_cientifico": "Schinus"}
    assert "nombre_cientifico" not in resueltos


def test_lo_que_no_se_resuelve_queda_en_los_originales_y_la_referencia_en_none(molle):
    crear_valor()

    resueltos = resolver_valores(
        {
            "nombre_cientifico": "Especie inventada",
            "nombre_comun": "Algo",
            "origen": "Nativa",
            "estado_general": "Excelente",
            "estado_copa": None,
            "brigada": "Brigada A",
            "observaciones": "tal cual",
        }
    )

    assert resueltos["especie"] is None
    assert resueltos["estado_general"] is None
    assert resueltos["grupo"] is None
    assert resueltos["observaciones"] == "tal cual"
    assert resueltos["valores_originales"] == {
        "nombre_cientifico": "Especie inventada",
        "nombre_comun": "Algo",
        "origen": "Nativa",
        "estado_general": "Excelente",
        "brigada": "Brigada A",
    }


def test_el_origen_distinto_al_de_la_especie_queda_anotado_y_manda_la_especie(molle):
    nativa = crear_valor("origen", "Nativa")
    molle.origen = nativa
    molle.save()

    resueltos = resolver_valores({"nombre_cientifico": "Schinus molle", "origen": "Introducida"})

    assert resueltos["valores_originales"] == {"origen": "Introducida"}
    assert (
        resolver_valores({"nombre_cientifico": "Schinus molle", "origen": "nativa"})[
            "valores_originales"
        ]
        == {}
    )


def test_la_brigada_que_trae_el_nombre_de_un_grupo_se_resuelve_a_ese_grupo(grupo):
    resueltos = resolver_valores({"brigada": "Sopita"})

    assert resueltos["grupo"] == grupo
    assert resueltos["valores_originales"] == {"brigada": "Sopita"}
    assert resolver_valores({"brigada": "Brigada A"})["grupo"] is None


def test_un_resolutor_armado_una_vez_no_vuelve_a_consultar_la_bd(
    molle, grupo, django_assert_num_queries
):
    crear_valor()
    resolutor = Resolutor.desde_bd()

    with django_assert_num_queries(0):
        for _ in range(5):
            resolutor.resolver({"nombre_cientifico": "schinus", "estado_general": "bueno"})
            resolutor.resolver({"brigada": "Sopita"})


def test_el_nombre_cientifico_de_unos_valores_resueltos(molle):
    assert nombre_cientifico_de(resolver_valores({"nombre_cientifico": "schinus"})) == (
        "Schinus molle"
    )
    assert nombre_cientifico_de(resolver_valores({"nombre_cientifico": "Otra"})) == "Otra"
    assert nombre_cientifico_de(resolver_valores({})) is None


# --- texto_de ---------------------------------------------------------------------------------


def test_texto_de_lee_las_tablas_y_cae_en_los_originales(sectores, molle, grupo):
    bueno = crear_valor()
    arbol = Arbol(codigo="S01-A001", sector_id=1, especie=molle, estado_general=bueno, grupo=grupo)
    arbol.valores_originales = {"estado_copa": "Rara", "origen": "Nativa"}

    assert texto_de(arbol, "nombre_comun") == "Molle"
    assert texto_de(arbol, "nombre_cientifico") == "Schinus molle"
    assert texto_de(arbol, "estado_general") == "Bueno"
    assert texto_de(arbol, "estado_copa") == "Rara"  # sin referencia: lo que trajo la planilla
    assert texto_de(arbol, "origen") == "Nativa"  # la especie no tiene origen: cae en el original
    assert texto_de(arbol, "brigada") == "Brigada A"
    assert texto_de(arbol, "grupo") == "Sopita"
    assert texto_de(arbol, "tronco_danos") is None
    assert texto_de(arbol, "codigo") == "S01-A001"


def test_la_referencia_manda_sobre_el_texto_original(sectores, molle):
    arbol = Arbol(codigo="S01-A001", sector_id=1, especie=molle)
    arbol.valores_originales = {"nombre_cientifico": "Schinus"}

    assert texto_de(arbol, "nombre_cientifico") == "Schinus molle"


# --- aplicar_textos y fusionar_originales -----------------------------------------------------


def test_aplicar_textos_solo_toca_lo_que_se_menciona(sectores, molle):
    bueno = crear_valor()
    arbol = Arbol(codigo="S01-A001", sector_id=1, especie=molle, estado_general=bueno)

    aplicar_textos(arbol, {"estado_copa": "Rara"})

    assert arbol.especie == molle
    assert arbol.estado_general == bueno
    assert arbol.estado_copa is None
    assert arbol.valores_originales == {"estado_copa": "Rara"}


def test_fusionar_originales_quita_lo_que_ahora_se_resuelve_y_suma_lo_nuevo():
    existentes = {"estado_general": "Excelente", "estado_copa": "Rara", "brigada": "X"}
    valores = {
        "estado_general": ValorCatalogo(campo="estado_general", valor="Bueno"),
        "estado_copa": None,
        "valores_originales": {"tronco_danos": "Raro"},
    }

    assert fusionar_originales(existentes, valores) == {
        "estado_copa": "Rara",
        "brigada": "X",
        "tronco_danos": "Raro",
    }
    assert fusionar_originales(None, {}) == {}


# --- la regla de calidad con las tablas -------------------------------------------------------


def test_un_nombre_sin_especie_manda_a_revision_con_el_motivo_y_sin_inventar_nada(sectores):
    arbol = arbol_evaluado("S01-A001")
    arbol.especie = None
    arbol.valores_originales = {
        **arbol.valores_originales,
        "nombre_cientifico": "Quercus",
        "nombre_comun": "Roble",
    }

    motivos = aplicar(arbol)

    assert [m.porque for m in motivos] == [MOTIVO_ESPECIE_NO_REGISTRADA.format(texto="Quercus")]
    assert Especie.objects.filter(nombre_cientifico="Quercus").count() == 0


def test_con_el_catalogo_cargado_un_estado_sin_referencia_va_a_revision(sectores):
    crear_valor("estado_general", "Bueno")
    arbol = arbol_evaluado("S01-A001", estado_general="Excelente")

    assert arbol.estado_general is None
    assert arbol.valores_originales["estado_general"] == "Excelente"
    assert [m.porque for m in aplicar(arbol)] == [
        "Valor fuera del catálogo en Estado general: «Excelente»"
    ]


def test_sin_grupo_ni_brigada_un_arbol_real_se_publica(sectores):
    arbol = arbol_evaluado("S01-A001", brigada=None)

    assert arbol.demo is False
    assert arbol.grupo is None
    assert aplicar(arbol) == []


# --- una fila sobre un árbol que ya existe ----------------------------------------------------


@pytest.fixture
def catalogo_de_estados():
    """Con el catálogo de estado general cargado, un árbol con «Bueno» queda con su referencia."""
    return [crear_valor("estado_general", valor) for valor in ("Bueno", "Regular")]


def _con_la_fila(existente, textos):
    """El árbol existente con la fila de `textos` encima, como la carga web con «conservar»."""
    resueltos = Resolutor.desde_bd().resolver(textos)
    for campo, valor in valores_sobre_existente(existente, resueltos).items():
        setattr(existente, campo, valor)
    return existente


def test_un_estado_nuevo_que_no_resuelve_quita_el_viejo_y_manda_a_revision(
    sectores, catalogo_de_estados
):
    existente = arbol_evaluado("S01-A001")
    assert existente.estado_general is not None and aplicar(existente) == []

    arbol = _con_la_fila(existente, {"estado_general": "Excelente"})

    assert arbol.estado_general is None
    assert arbol.valores_originales["estado_general"] == "Excelente"
    assert [m.porque for m in aplicar(arbol)] == [
        "Valor fuera del catálogo en Estado general: «Excelente»"
    ]


def test_una_especie_nueva_que_no_resuelve_quita_la_vieja_y_manda_a_revision(
    sectores, catalogo_de_estados
):
    existente = arbol_evaluado("S01-A001")
    assert existente.especie is not None

    arbol = _con_la_fila(existente, {"nombre_cientifico": "Quercus"})

    assert arbol.especie is None
    assert arbol.valores_originales["nombre_cientifico"] == "Quercus"
    assert MOTIVO_ESPECIE_NO_REGISTRADA.format(texto="Quercus") in [
        m.porque for m in aplicar(arbol)
    ]


def test_una_celda_vacia_sigue_conservando_el_estado_y_la_especie(sectores, catalogo_de_estados):
    existente = arbol_evaluado("S01-A001")
    especie, estado = existente.especie, existente.estado_general

    arbol = _con_la_fila(existente, {"estado_general": "  ", "nombre_cientifico": None})

    assert (arbol.especie, arbol.estado_general) == (especie, estado)
    assert aplicar(arbol) == []


def test_un_estado_nuevo_que_si_resuelve_reemplaza_al_viejo(sectores, catalogo_de_estados):
    existente = arbol_evaluado("S01-A001")
    otro = next(v for v in catalogo_de_estados if v != existente.estado_general)

    arbol = _con_la_fila(existente, {"estado_general": otro.valor})

    assert arbol.estado_general == otro
    assert "estado_general" not in arbol.valores_originales
