"""Tests de la lectura de configuración desde el entorno."""

import importlib.util
from pathlib import Path

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.core.seguridad import LimiteAnonimo

RUTA_SETTINGS = Path(__file__).resolve().parents[2] / "config" / "settings.py"
VARIABLES_OBLIGATORIAS = [
    "DJANGO_SECRET_KEY",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "DB_HOST",
    "DB_PUERTO",
    "DB_ESQUEMA",
    "TZ",
    "ADMIN_RUTA",
    "API_LIMITE_ANONIMO",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DJANGO_SECURE_SSL_REDIRECT",
    "DJANGO_SECURE_HSTS_SECONDS",
    "DJANGO_SESSION_COOKIE_SECURE",
    "DJANGO_CSRF_COOKIE_SECURE",
]


def _cargar_settings_nuevo():
    """Ejecuta settings.py desde cero para que relea el entorno."""
    especificacion = importlib.util.spec_from_file_location("settings_de_prueba", RUTA_SETTINGS)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize("variable", VARIABLES_OBLIGATORIAS)
def test_falta_variable_obligatoria_da_error_claro(monkeypatch, variable):
    monkeypatch.delenv(variable, raising=False)

    with pytest.raises(ImproperlyConfigured, match=variable):
        _cargar_settings_nuevo()


def test_busqueda_de_esquema_usa_db_esquema(monkeypatch):
    monkeypatch.setenv("DB_ESQUEMA", "esquema_de_prueba")

    modulo = _cargar_settings_nuevo()

    opciones = modulo.DATABASES["default"]["OPTIONS"]["options"]
    assert opciones == "-c search_path=esquema_de_prueba,public"


def test_admin_ruta_se_lee_del_entorno(monkeypatch):
    monkeypatch.setenv("ADMIN_RUTA", "ruta-de-prueba/")

    modulo = _cargar_settings_nuevo()

    assert modulo.ADMIN_RUTA == "ruta-de-prueba/"


def test_limite_anonimo_se_lee_del_entorno(monkeypatch):
    monkeypatch.setenv("API_LIMITE_ANONIMO", "7/min")

    modulo = _cargar_settings_nuevo()

    tasas = modulo.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert tasas[LimiteAnonimo.scope] == "7/min"


def test_origenes_csrf_de_confianza_se_leen_del_entorno(monkeypatch):
    monkeypatch.setenv("DJANGO_CSRF_TRUSTED_ORIGINS", "https://uno.test,https://dos.test")

    modulo = _cargar_settings_nuevo()

    assert modulo.CSRF_TRUSTED_ORIGINS == ["https://uno.test", "https://dos.test"]


@pytest.mark.parametrize(
    ("variable", "setting"),
    [
        ("DJANGO_SECURE_SSL_REDIRECT", "SECURE_SSL_REDIRECT"),
        ("DJANGO_SESSION_COOKIE_SECURE", "SESSION_COOKIE_SECURE"),
        ("DJANGO_CSRF_COOKIE_SECURE", "CSRF_COOKIE_SECURE"),
    ],
)
@pytest.mark.parametrize(("texto", "esperado"), [("true", True), ("false", False)])
def test_banderas_de_produccion_se_leen_del_entorno(
    monkeypatch, variable, setting, texto, esperado
):
    monkeypatch.setenv(variable, texto)

    modulo = _cargar_settings_nuevo()

    assert getattr(modulo, setting) is esperado


def test_hsts_se_lee_del_entorno_como_entero(monkeypatch):
    monkeypatch.setenv("DJANGO_SECURE_HSTS_SECONDS", "31536000")

    modulo = _cargar_settings_nuevo()

    assert modulo.SECURE_HSTS_SECONDS == 31536000


def test_drf_usa_permiso_throttle_y_manejador_del_proyecto():
    assert settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == [
        "apps.core.seguridad.SoloLectura"
    ]
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] == [
        "apps.core.seguridad.LimiteAnonimo"
    ]
    assert settings.REST_FRAMEWORK["EXCEPTION_HANDLER"] == "apps.core.excepciones.manejar_excepcion"


@pytest.mark.parametrize(
    "middleware",
    [
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
    ],
)
def test_middlewares_de_sesion_csrf_y_clickjacking_siguen_activos(middleware):
    assert middleware in settings.MIDDLEWARE
