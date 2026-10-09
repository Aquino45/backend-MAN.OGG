"""Tests de GET {PREFIJO_API}salud y de las constantes de negocio."""

from unittest import mock

import pytest
from django.db import OperationalError, connection

from config import constantes


@pytest.mark.django_db
def test_salud_responde_200_y_estado_ok(cliente_api, url_salud):
    respuesta = cliente_api.get(url_salud)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "ok"
    assert cuerpo["base_de_datos"] == "ok"
    assert cuerpo["postgis"]


@pytest.mark.django_db
def test_postgis_version_responde():
    assert connection.ops.postgis_version()


def test_salud_responde_503_sin_base_de_datos(cliente_api, url_salud):
    with mock.patch("apps.core.api.views.connection") as conexion_falsa:
        conexion_falsa.cursor.side_effect = OperationalError("sin conexion")
        respuesta = cliente_api.get(url_salud)

    assert respuesta.status_code == 503
    assert respuesta.json() == {"estado": "error", "base_de_datos": "sin conexión"}


def test_constantes_valen_lo_esperado():
    assert constantes.PREFIJO_API == "api/v1/"
    assert constantes.PREFIJO_API.endswith("/")
    assert constantes.SRID_UTM_CENSO == 32718
    assert constantes.SRID_MAPA == 4326
