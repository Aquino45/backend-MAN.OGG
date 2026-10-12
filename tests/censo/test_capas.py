"""Las capas de docs/ARQUITECTURA.md §4: quién puede importar a quién."""

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2] / "apps" / "censo"
PREFIJO_DE_SERVICIOS = "apps.censo.servicios"


def modulos_importados(ruta):
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            yield from (alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            yield nodo.module


@pytest.mark.parametrize("archivo", ["api/serializers.py", "models.py", "models_catalogos.py"])
def test_los_serializers_y_los_modelos_no_importan_servicios(archivo):
    importados = list(modulos_importados(RAIZ / archivo))

    assert [m for m in importados if m.startswith(PREFIJO_DE_SERVICIOS)] == []
