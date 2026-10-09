"""Fixtures compartidas de los tests de la API."""

import pytest
from rest_framework.test import APIClient

from config.constantes import PREFIJO_API


@pytest.fixture
def cliente_api():
    """Cliente de DRF para llamar a la API sin servidor ni puertos."""
    return APIClient()


@pytest.fixture
def url_salud():
    """Ruta relativa de la salud, armada con el prefijo de la API."""
    return f"/{PREFIJO_API}salud"
