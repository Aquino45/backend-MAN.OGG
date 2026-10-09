"""Tests de la lectura de configuración desde el entorno."""

import importlib.util
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

RUTA_SETTINGS = Path(__file__).resolve().parent.parent / "config" / "settings.py"
VARIABLES_OBLIGATORIAS = [
    "DJANGO_SECRET_KEY",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "DB_HOST",
    "DB_PUERTO",
    "DB_ESQUEMA",
    "TZ",
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
