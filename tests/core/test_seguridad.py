"""Tests de la seguridad mínima: solo lectura, throttling para anónimos y admin en ruta propia."""

import importlib
import os

import pytest
from django.conf import settings as ajustes
from django.core.cache import cache
from django.test import Client
from django.urls import clear_url_caches

from apps.core.seguridad import LimiteAnonimo, SoloLectura

METODOS_SEGUROS = ["get", "head", "options"]
METODOS_DE_ESCRITURA = ["post", "put", "patch", "delete"]
RUTA_ADMIN_DE_PRUEBA = "ruta-de-prueba/"


@pytest.fixture(autouse=True)
def cache_limpia():
    """El contador del throttling vive en la caché: cada test arranca de cero."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_get_a_salud_pasa(cliente_api, url_salud):
    assert cliente_api.get(url_salud).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("metodo", METODOS_DE_ESCRITURA)
def test_escritura_a_salud_se_rechaza_con_detail(cliente_api, url_salud, metodo):
    respuesta = getattr(cliente_api, metodo)(url_salud, {}, format="json")

    assert respuesta.status_code in (403, 405)
    assert list(respuesta.json()) == ["detail"]


@pytest.mark.django_db
def test_escritura_explica_que_la_api_es_de_solo_lectura(cliente_api, url_salud):
    respuesta = cliente_api.post(url_salud, {}, format="json")

    assert respuesta.status_code == 403
    assert respuesta.json() == {"detail": SoloLectura.message}


def test_la_api_no_usa_autenticacion():
    assert ajustes.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == []


@pytest.mark.django_db
def test_options_a_salud_pasa(cliente_api, url_salud):
    assert cliente_api.options(url_salud).status_code == 200


@pytest.mark.parametrize("metodo", METODOS_SEGUROS)
def test_solo_lectura_deja_pasar_los_metodos_seguros(rf, metodo):
    peticion = getattr(rf, metodo)("/")

    assert SoloLectura().has_permission(peticion, None) is True


@pytest.mark.parametrize("metodo", METODOS_DE_ESCRITURA)
def test_solo_lectura_rechaza_los_metodos_de_escritura(rf, metodo):
    peticion = getattr(rf, metodo)("/")

    assert SoloLectura().has_permission(peticion, None) is False


def test_la_tasa_de_anonimos_sale_de_api_limite_anonimo():
    assert LimiteAnonimo().get_rate() == os.environ["API_LIMITE_ANONIMO"]


@pytest.mark.django_db
def test_pasado_el_limite_responde_429_con_detail(monkeypatch, cliente_api, url_salud):
    monkeypatch.setattr(LimiteAnonimo, "THROTTLE_RATES", {LimiteAnonimo.scope: "2/min"})

    codigos = [cliente_api.get(url_salud).status_code for _ in range(2)]
    tercera = cliente_api.get(url_salud)

    assert codigos == [200, 200]
    assert tercera.status_code == 429
    assert list(tercera.json()) == ["detail"]


@pytest.fixture
def urls_con_admin_en_ruta_propia(settings):
    """Recarga `config.urls` con otra `ADMIN_RUTA` y la deja como estaba al terminar."""
    import config.urls

    ruta_original = ajustes.ADMIN_RUTA
    settings.ADMIN_RUTA = RUTA_ADMIN_DE_PRUEBA
    clear_url_caches()
    importlib.reload(config.urls)
    yield
    settings.ADMIN_RUTA = ruta_original
    clear_url_caches()
    importlib.reload(config.urls)


@pytest.mark.django_db
def test_admin_responde_en_admin_ruta_y_pide_login():
    respuesta = Client().get(f"/{ajustes.ADMIN_RUTA}")

    assert respuesta.status_code == 302
    assert "login" in respuesta["Location"]


@pytest.mark.django_db
def test_admin_sigue_la_ruta_configurada(urls_con_admin_en_ruta_propia):
    respuesta = Client().get(f"/{RUTA_ADMIN_DE_PRUEBA}")

    assert respuesta.status_code == 302
    assert respuesta["Location"].startswith(f"/{RUTA_ADMIN_DE_PRUEBA}login/")


@pytest.mark.django_db
def test_admin_fijo_ya_no_existe_si_admin_ruta_es_otra(urls_con_admin_en_ruta_propia):
    assert Client().get("/admin/").status_code == 404
