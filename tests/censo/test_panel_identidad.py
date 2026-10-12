"""Tests de las listas del panel (filtros, búsqueda, chips) y sus textos."""

import re

import pytest
from django.apps import apps as registro_de_apps
from django.contrib import admin
from django.contrib.admin.utils import label_for_field
from django.urls import reverse

from apps.censo.models import (
    Arbol,
    ArbolEnPapelera,
    AyudaCampo,
    Brigada,
    Especie,
    GrupoBrigada,
    LoteCarga,
    ValorCatalogo,
)
from config.constantes.calidad import PARAMETRO_FILTRO_ESTADO_REGISTRO
from config.constantes.carga import ESTADO_LOTE_CONFIRMADO
from config.constantes.panel import PAGINA_ADMIN, TEXTOS_CHIPS_ADMIN
from tests.censo.conftest import arbol_de_ejemplo, arbol_evaluado

PALABRAS_SIN_TILDE = re.compile(
    r"\b(arbol|arbols|sectors|explicacion|cientifico|comun|ubicacion|identificacion|condicion"
    r"|danos|raices|revision|eliminacion|clasificacion|decision|leidas|vacios|numero|codigo"
    r"|titulo|observacion|co2|el ficha|que es)\b",
    re.IGNORECASE,
)


def texto_visible(html):
    sin_codigo = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", sin_codigo)


def modelos_del_censo():
    modelos = registro_de_apps.get_app_config("censo").get_models()
    return [modelo for modelo in modelos if not modelo._meta.model_name.startswith("historical")]


def nombres_de_filtros(modelo):
    """El nombre con que cada filtro de la lista llega en la URL."""
    nombres = []
    for filtro in admin.site._registry[modelo].list_filter:
        if isinstance(filtro, str):
            nombres.append(filtro)
        elif isinstance(filtro, tuple):
            nombres.append(filtro[0])
        else:
            nombres.append(filtro.parameter_name)
    return nombres


# --- listas ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "modelo", [Arbol, ArbolEnPapelera, Especie, Brigada, AyudaCampo, ValorCatalogo, LoteCarga]
)
def test_cada_lista_pagina_con_la_constante(modelo):
    assert admin.site._registry[modelo].list_per_page == PAGINA_ADMIN


def test_la_lista_de_arboles_trae_los_filtros_y_la_busqueda_pedidos():
    busqueda = set(admin.site._registry[Arbol].search_fields)

    filtros = set(nombres_de_filtros(Arbol))
    assert {"sector", "especie", "grupo", "demo", "destacado"} <= filtros
    assert PARAMETRO_FILTRO_ESTADO_REGISTRO in filtros
    assert {"codigo", "especie__nombre_comun", "especie__nombre_cientifico"} <= busqueda
    assert "especie__alias" in busqueda


def test_buscar_por_alias_y_por_nombre_cientifico(cliente_administrador, sectores):
    arbol_de_ejemplo("S01-A001", nombre_comun="Molle", nombre_cientifico="Schinus molle")
    arbol_de_ejemplo("S01-A002", nombre_comun="Huarango", nombre_cientifico="Prosopis pallida")
    Especie.objects.filter(nombre_comun="Huarango").update(alias="Algarrobo costeño")
    lista = reverse("admin:censo_arbol_changelist")

    por_alias = cliente_administrador.get(lista, {"q": "costeño"}).content.decode()
    por_cientifico = cliente_administrador.get(lista, {"q": "Schinus"}).content.decode()

    assert "S01-A002" in por_alias and "S01-A001" not in por_alias
    assert "S01-A001" in por_cientifico and "S01-A002" not in por_cientifico


def test_los_filtros_de_especie_grupo_y_ejemplo_filtran(cliente_administrador, sectores):
    molle = arbol_de_ejemplo("S01-A001", nombre_comun="Molle", nombre_cientifico="Schinus molle")
    arbol_evaluado("S01-A002", nombre_comun="Huarango", nombre_cientifico="Prosopis pallida")
    grupo = GrupoBrigada.objects.create(
        brigada=Brigada.objects.create(nombre="Brigada de prueba tres"), nombre="G1"
    )
    Arbol.objects.filter(codigo="S01-A002").update(grupo=grupo)
    lista = reverse("admin:censo_arbol_changelist")

    def codigos(filtro):
        respuesta = cliente_administrador.get(lista, filtro)
        return [arbol.codigo for arbol in respuesta.context["cl"].result_list]

    assert codigos({"especie__id__exact": molle.especie_id}) == ["S01-A001"]
    assert codigos({"demo__exact": "1"}) == ["S01-A001"]
    assert codigos({"grupo__id__exact": grupo.pk}) == ["S01-A002"]


def test_la_lista_de_brigadas_filtra_por_grupo(cliente_administrador, db):
    brigada = Brigada.objects.create(nombre="Brigada de prueba uno")
    GrupoBrigada.objects.create(
        brigada=Brigada.objects.create(nombre="Brigada de prueba dos"), nombre="G2"
    )
    grupo = GrupoBrigada.objects.create(brigada=brigada, nombre="Grupo 1")

    respuesta = cliente_administrador.get(
        reverse("admin:censo_brigada_changelist"), {"grupos__id__exact": grupo.pk}
    )

    assert [b.nombre for b in respuesta.context["cl"].result_list] == ["Brigada de prueba uno"]


def test_las_columnas_de_arboles_son_ordenables(cliente_administrador, sectores):
    arbol_de_ejemplo("S01-A001")
    modelo = admin.site._registry[Arbol]

    for columna in ("chip_estado_registro", "chip_ejemplo", "chip_destacado", "miniatura"):
        assert getattr(modelo, columna).admin_order_field, columna
        posicion = list(modelo.list_display).index(columna)
        lista = reverse("admin:censo_arbol_changelist")
        assert cliente_administrador.get(lista, {"o": str(posicion + 1)}).status_code == 200


# --- chips -------------------------------------------------------------------------------------


def lista_de_arboles(cliente):
    return cliente.get(reverse("admin:censo_arbol_changelist")).content.decode()


def test_los_chips_muestran_el_estado_del_registro(cliente_administrador, sectores):
    arbol_evaluado("S01-A001")
    Arbol.objects.filter(codigo="S01-A001").update(estado_registro="en_revision")
    arbol_evaluado("S01-A002")

    html = lista_de_arboles(cliente_administrador)

    assert 'class="chip chip--revision">En revisión<' in html
    assert 'class="chip chip--publicado">Publicado<' in html


def test_los_chips_de_ejemplo_y_destacado(cliente_administrador, sectores):
    arbol_de_ejemplo("S01-A001", destacado=True)
    arbol_evaluado("S01-A002")

    html = lista_de_arboles(cliente_administrador)

    assert f'class="chip chip--ejemplo">{TEXTOS_CHIPS_ADMIN["ejemplo"]}<' in html
    assert f'class="chip chip--censo">{TEXTOS_CHIPS_ADMIN["censo"]}<' in html
    assert html.count('class="chip chip--destacado"') == 1


def test_la_miniatura_con_y_sin_foto(cliente_administrador, sectores):
    arbol_de_ejemplo("S01-A001", foto_archivo="IMG_0001.jpg")
    arbol_de_ejemplo("S01-A002")

    html = lista_de_arboles(cliente_administrador)

    assert html.count('class="glifo-pixel"') >= 2
    assert html.count(f">{TEXTOS_CHIPS_ADMIN['con_foto']}<") == 1
    assert html.count(f">{TEXTOS_CHIPS_ADMIN['sin_foto']}<") == 1


def test_el_estado_del_lote_sale_en_un_chip(cliente_administrador, usuario_administrador):
    LoteCarga.objects.create(
        usuario=usuario_administrador,
        nombre_archivo="a.xlsx",
        sha256="0" * 64,
        estado=ESTADO_LOTE_CONFIRMADO,
    )

    html = cliente_administrador.get(reverse("admin:censo_lotecarga_changelist")).content.decode()

    assert 'class="chip chip--publicado">Confirmado<' in html


def test_los_chips_de_especies_y_catalogo(cliente_administrador, db):
    Especie.objects.create(nombre_cientifico="Schinus molle", revisada=False)
    ValorCatalogo.objects.create(
        campo="estado_general", valor="Bueno", explicacion="x", activo=False
    )

    especies = cliente_administrador.get(reverse("admin:censo_especie_changelist"))
    catalogo = cliente_administrador.get(reverse("admin:censo_valorcatalogo_changelist"))

    assert "chip--revision" in especies.content.decode()
    assert "chip--inactivo" in catalogo.content.decode()


# --- textos ------------------------------------------------------------------------------------


def test_ningun_nombre_de_modelo_ni_de_campo_queda_sin_tilde():
    fallas = []
    for modelo in modelos_del_censo():
        textos = [str(modelo._meta.verbose_name), str(modelo._meta.verbose_name_plural)]
        for campo in modelo._meta.get_fields():
            if not hasattr(campo, "verbose_name"):
                continue
            etiqueta = str(campo.verbose_name)
            textos += [etiqueta, str(getattr(campo, "help_text", ""))]
        fallas += [f"{modelo.__name__}: {t}" for t in textos if PALABRAS_SIN_TILDE.search(t)]
    assert not fallas


def test_el_indice_y_las_listas_no_tienen_faltas(cliente_administrador, sectores):
    arbol_de_ejemplo("S01-A001")
    paginas = [reverse("admin:index")]
    for modelo in admin.site._registry:
        if modelo._meta.app_label == "censo":
            paginas.append(reverse(f"admin:censo_{modelo._meta.model_name}_changelist"))
    fallas = []
    for ruta in paginas:
        respuesta = cliente_administrador.get(ruta)
        assert respuesta.status_code == 200, ruta
        texto = texto_visible(respuesta.content.decode())
        fallas += [f"{ruta}: {m.group(0)}" for m in PALABRAS_SIN_TILDE.finditer(texto)]
    assert not fallas


def test_el_indice_y_las_columnas_llevan_tilde(cliente_administrador):
    html = cliente_administrador.get(reverse("admin:index")).content.decode()
    modelo_admin = admin.site._registry[Especie]
    etiquetas = [label_for_field(c, Especie, modelo_admin) for c in modelo_admin.list_display]

    assert "Árboles" in html and "Sectores" in html
    nombres = [str(etiqueta).capitalize() for etiqueta in etiquetas]
    assert "Nombre científico" in nombres and "Nombre común" in nombres
