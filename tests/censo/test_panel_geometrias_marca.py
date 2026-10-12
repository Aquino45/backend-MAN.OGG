"""Tests del enlace pin y coordenadas al cargar la página y de la fecha de la marca de ubicación."""

from datetime import UTC, datetime

import pytest
from django.urls import reverse

from apps.censo.models import Arbol
from apps.censo.servicios import geometrias
from tests.censo.conftest import arbol_evaluado
from tests.censo.test_panel_geometrias import (
    configuracion_del_mapa,
    datos_del_arbol,
    en_el_widget,
    ruta_de_cambio,
)

ANTES = datetime(2026, 1, 1, tzinfo=UTC)
AHORA = datetime(2026, 6, 1, tzinfo=UTC)


@pytest.fixture
def arbol(sectores):
    return arbol_evaluado("S01-A001")


# --- el enlace se inicializa cuando el formulario ya existe ------------------------------------


def test_el_formulario_del_arbol_enlaza_el_pin_al_cargar_el_documento(cliente_editor, arbol):
    contenido = cliente_editor.get(ruta_de_cambio(arbol)).content.decode()

    assert "function enlazarCoordenadas()" in contenido
    assert "DOMContentLoaded" in contenido
    assert "document.readyState" in contenido
    assert "addEventListener('DOMContentLoaded', enlazarCoordenadas)" in contenido


def test_el_enlace_sale_sin_error_si_falta_un_campo_de_la_pagina(cliente_editor, arbol):
    contenido = cliente_editor.get(ruta_de_cambio(arbol)).content.decode()

    assert "return !entradas[clave]" in contenido


def test_el_mapa_del_sector_no_usa_el_enlace_de_coordenadas(cliente_administrador, sectores):
    respuesta = cliente_administrador.get(reverse("admin:censo_sector_change", args=[1]))

    assert configuracion_del_mapa(respuesta)["campos"] is None


# --- la fecha sigue a la marca ------------------------------------------------------------------


def test_el_administrador_que_quita_la_marca_deja_la_fecha_en_null(cliente_administrador, arbol):
    Arbol.todos.filter(pk=arbol.pk).update(
        ubicacion_editada_en_panel=True, fecha_ubicacion_editada=ANTES
    )
    datos = datos_del_arbol(ubicacion=en_el_widget(arbol.ubicacion), demo="")
    datos.pop("ubicacion_editada_en_panel", None)

    cliente_administrador.post(ruta_de_cambio(arbol), datos)

    arbol.refresh_from_db()
    assert arbol.ubicacion_editada_en_panel is False
    assert arbol.fecha_ubicacion_editada is None
    assert arbol.history.first().fecha_ubicacion_editada is None


def test_el_administrador_que_pone_la_marca_llena_la_fecha(cliente_administrador, arbol):
    datos = datos_del_arbol(
        ubicacion=en_el_widget(arbol.ubicacion), ubicacion_editada_en_panel="on", demo=""
    )

    cliente_administrador.post(ruta_de_cambio(arbol), datos)

    arbol.refresh_from_db()
    assert arbol.ubicacion_editada_en_panel is True
    assert arbol.fecha_ubicacion_editada is not None
    assert arbol.history.first().fecha_ubicacion_editada is not None


# --- la regla de la fecha ----------------------------------------------------------------------


def test_sin_marca_no_hay_fecha():
    assert geometrias.fecha_de_la_marca(False, ANTES, AHORA) is None


def test_con_marca_y_sin_fecha_se_usa_la_actual():
    assert geometrias.fecha_de_la_marca(True, None, AHORA) == AHORA


def test_con_marca_y_con_fecha_se_conserva_la_que_ya_estaba():
    assert geometrias.fecha_de_la_marca(True, ANTES, AHORA) == ANTES
