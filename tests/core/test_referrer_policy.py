"""La cabecera Referrer-Policy real del panel y de la API deja pasar el origen a otros sitios."""

import pytest
from django.conf import settings

POLITICA_ESPERADA = "strict-origin-when-cross-origin"


@pytest.mark.django_db
def test_la_pagina_de_login_del_panel_trae_la_politica_de_referrer(client):
    respuesta = client.get(f"/{settings.ADMIN_RUTA}login/")

    assert respuesta.status_code == 200
    assert respuesta["Referrer-Policy"] == POLITICA_ESPERADA


@pytest.mark.django_db
def test_la_salud_de_la_api_trae_la_politica_de_referrer(cliente_api, url_salud):
    respuesta = cliente_api.get(url_salud)

    assert respuesta.status_code == 200
    assert respuesta["Referrer-Policy"] == POLITICA_ESPERADA
