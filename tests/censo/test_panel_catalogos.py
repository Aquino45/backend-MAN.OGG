"""El panel de especies y árboles: buscar la especie, filtros y el origen de la especie."""

import re

import pytest
from django.urls import reverse

from apps.censo.admin import ArbolAdmin
from apps.censo.admin_catalogos import EspecieAdmin
from apps.censo.models import Especie, ValorCatalogo
from config.constantes import FORMA_ARBOL, FORMA_PALMA, TEXTO_ORIGEN_SIN_DATO
from tests.censo.conftest import arbol_evaluado

pytestmark = pytest.mark.django_db


@pytest.fixture
def nativa():
    return ValorCatalogo.objects.create(campo="origen", valor="Nativa", explicacion="x")


@pytest.fixture
def especies(nativa):
    """Una especie confirmada con su origen y alias, y una palma por revisar."""
    molle = Especie.objects.create(
        nombre_cientifico="Schinus molle",
        nombre_comun="Molle",
        alias="Schinus",
        origen=nativa,
        forma=FORMA_ARBOL,
    )
    palma = Especie.objects.create(
        nombre_cientifico="Roystonea regia", forma=FORMA_PALMA, revisada=False
    )
    return molle, palma


def codigos_del_listado(respuesta):
    return {fila.codigo for fila in respuesta.context["cl"].result_list}


# --- autocompletar la especie del árbol --------------------------------------------------------


def buscar_especie(cliente, termino):
    respuesta = cliente.get(
        reverse("admin:autocomplete"),
        {"app_label": "censo", "model_name": "arbol", "field_name": "especie", "term": termino},
    )
    assert respuesta.status_code == 200
    return {resultado["text"] for resultado in respuesta.json()["results"]}


def test_la_especie_del_arbol_se_busca_escribiendo(cliente_administrador, especies):
    assert "especie" in ArbolAdmin.autocomplete_fields
    assert buscar_especie(cliente_administrador, "molle") == {"Schinus molle (Molle)"}
    assert buscar_especie(cliente_administrador, "Roystonea") == {"Roystonea regia"}


def test_la_especie_tambien_se_encuentra_por_alias_y_el_editor_puede_buscarla(
    cliente_editor, especies
):
    assert buscar_especie(cliente_editor, "schinus") == {"Schinus molle (Molle)"}


# --- filtros de las especies -------------------------------------------------------------------


def nombres_del_listado(respuesta):
    return {especie.nombre_cientifico for especie in respuesta.context["cl"].result_list}


def test_las_especies_se_filtran_por_revisada_y_por_forma(cliente_administrador, especies):
    lista = reverse("admin:censo_especie_changelist")

    por_revisar = cliente_administrador.get(lista, {"revisada__exact": "0"})
    palmas = cliente_administrador.get(lista, {"forma__exact": FORMA_PALMA})
    arboles = cliente_administrador.get(lista, {"forma__exact": FORMA_ARBOL})

    assert nombres_del_listado(por_revisar) == {"Roystonea regia"}
    assert nombres_del_listado(palmas) == {"Roystonea regia"}
    assert nombres_del_listado(arboles) == {"Schinus molle"}
    assert {"revisada", "forma"} <= set(EspecieAdmin.list_filter)


# --- el origen del árbol es el de su especie ---------------------------------------------------


def pagina_del_arbol(cliente, arbol):
    return cliente.get(reverse("admin:censo_arbol_change", args=[arbol.pk])).content.decode()


def origen_mostrado(pagina):
    """El texto de solo lectura de la fila «origen de la especie» de la página del árbol."""
    fila = re.search(
        r'Origen \(el de su especie\).*?<div class="readonly[^"]*">(.*?)</div>', pagina, re.S
    )
    return fila.group(1).strip()


def test_el_origen_del_arbol_se_muestra_de_solo_lectura_con_el_de_su_especie(
    cliente_administrador, sectores, especies
):
    arbol = arbol_evaluado("S01-A001", nombre_cientifico="Schinus molle")

    pagina = pagina_del_arbol(cliente_administrador, arbol)

    assert origen_mostrado(pagina) == "Nativa"
    assert 'name="origen"' not in pagina


def test_el_origen_cambia_con_la_especie_y_no_se_edita_en_el_arbol(
    cliente_administrador, sectores, especies, nativa
):
    molle, _ = especies
    arbol = arbol_evaluado("S01-A001", nombre_cientifico="Schinus molle")
    molle.origen = None
    molle.save()

    pagina = pagina_del_arbol(cliente_administrador, arbol)

    assert origen_mostrado(pagina) == TEXTO_ORIGEN_SIN_DATO
    assert "origen" not in ArbolAdmin.fieldsets[1][1]["fields"]
