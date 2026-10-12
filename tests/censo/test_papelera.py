"""Tests de la papelera de árboles: mover, restaurar, código repetido y eliminación definitiva.

Los árboles de prueba salen de `nuevo_arbol` (siempre `demo=True`); nunca se usa la planilla real.
"""

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.censo.models import Arbol, ArbolEnPapelera
from apps.censo.servicios.importar_planilla import importar_planilla
from apps.censo.servicios.papelera import eliminar_definitivamente, mover_a_papelera, restaurar
from config.constantes import TOPE_DESTACADOS_POR_SECTOR
from tests.censo.conftest import arbol_de_ejemplo, crear_planilla, fila

MOTIVO = "Se registró dos veces por error"
MOTIVO_DESTACADO = "Ejemplar de mayor copa del sector"


@pytest.fixture
def usuario(db):
    return User.objects.create_user("quien-borra", password="x", is_staff=True)


def llenar_de_destacados(nuevo_arbol, cantidad=TOPE_DESTACADOS_POR_SECTOR):
    """Crea `cantidad` destacados en el sector 1 (códigos S01-A001, S01-A002…)."""
    return [
        nuevo_arbol(f"S01-A{numero:03d}", destacado=True, motivo_destacado=MOTIVO_DESTACADO)
        for numero in range(1, cantidad + 1)
    ]


# --- mover ------------------------------------------------------------------------------------


def test_mover_a_papelera_guarda_quien_cuando_y_por_que_sin_borrar_la_fila(nuevo_arbol, usuario):
    arbol = nuevo_arbol()

    mover_a_papelera(arbol, usuario, MOTIVO)

    guardado = Arbol.todos.get(codigo="S01-A001")
    assert guardado.eliminado_en is not None
    assert guardado.eliminado_por == usuario
    assert guardado.motivo_eliminacion == MOTIVO
    assert not Arbol.objects.filter(codigo="S01-A001").exists()
    assert list(ArbolEnPapelera.objects.values_list("codigo", flat=True)) == ["S01-A001"]


@pytest.mark.parametrize("motivo", [None, "", "   \n"])
def test_el_motivo_es_obligatorio(nuevo_arbol, usuario, motivo):
    arbol = nuevo_arbol()

    with pytest.raises(ValueError, match="motivo"):
        mover_a_papelera(arbol, usuario, motivo)

    assert Arbol.objects.filter(codigo="S01-A001").exists()
    assert Arbol.todos.get(codigo="S01-A001").eliminado_en is None


def test_un_arbol_en_la_papelera_no_sale_en_la_lista_ni_en_la_cartilla(
    sectores, cliente_api, usuario
):
    arbol_de_ejemplo("S01-A001")
    arbol_de_ejemplo("S01-A002")
    mover_a_papelera(Arbol.objects.get(codigo="S01-A002"), usuario, MOTIVO)

    lista = cliente_api.get(reverse("arboles-de-sector", kwargs={"sector_id": 1})).json()
    cartilla = cliente_api.get(reverse("arbol", kwargs={"codigo": "S01-A002"}))

    assert [feature["id"] for feature in lista["features"]] == ["S01-A001"]
    assert cartilla.status_code == 404
    assert cartilla.json() == {"detail": "No encontrado."}


def test_el_simulado_tambien_va_a_la_papelera_y_vuelve_sin_borrarse(nuevo_arbol, usuario):
    arbol = nuevo_arbol(demo=True)

    mover_a_papelera(arbol, usuario, MOTIVO)
    assert Arbol.todos.filter(codigo="S01-A001", demo=True).count() == 1
    restaurar(Arbol.todos.get(codigo="S01-A001"), usuario)

    assert Arbol.objects.filter(codigo="S01-A001", demo=True).count() == 1


# --- restaurar --------------------------------------------------------------------------------


def test_restaurar_limpia_los_datos_de_la_papelera(nuevo_arbol, usuario):
    arbol = nuevo_arbol()
    mover_a_papelera(arbol, usuario, MOTIVO)

    resultado = restaurar(Arbol.todos.get(codigo="S01-A001"), usuario)

    vuelto = Arbol.objects.get(codigo="S01-A001")
    assert (vuelto.eliminado_en, vuelto.eliminado_por, vuelto.motivo_eliminacion) == (
        None,
        None,
        None,
    )
    assert resultado.perdio_destacado is False
    assert not ArbolEnPapelera.objects.exists()


def test_restaurar_un_arbol_vigente_se_rechaza(nuevo_arbol, usuario):
    arbol = nuevo_arbol()

    with pytest.raises(ValueError, match="papelera"):
        restaurar(arbol, usuario)


# --- código repetido --------------------------------------------------------------------------


def test_el_codigo_de_la_papelera_no_se_puede_reusar(nuevo_arbol, usuario):
    mover_a_papelera(nuevo_arbol("S01-A001"), usuario, MOTIVO)
    repetido = Arbol(codigo="S01-A001", sector_id=1, fuente="Otra prueba")

    with pytest.raises(ValidationError) as error:
        repetido.full_clean()

    mensaje = " ".join(error.value.message_dict["codigo"])
    assert "está en la papelera; puede restaurarse" in mensaje


def test_el_codigo_de_un_vigente_sigue_siendo_unico(nuevo_arbol):
    nuevo_arbol("S01-A001")

    with pytest.raises(ValidationError) as error:
        Arbol(codigo="S01-A001", sector_id=1, fuente="Otra prueba").full_clean()

    assert "codigo" in error.value.message_dict


def test_el_arbol_de_la_papelera_se_valida_a_si_mismo_sin_chocar(nuevo_arbol, usuario):
    mover_a_papelera(nuevo_arbol("S01-A001"), usuario, MOTIVO)

    Arbol.todos.get(codigo="S01-A001").full_clean()  # no choca consigo mismo


def test_importar_planilla_rechaza_la_fila_de_un_arbol_en_la_papelera(
    nuevo_arbol, usuario, ruta_planilla
):
    arbol = nuevo_arbol("S01-A001", observaciones="Molle")
    mover_a_papelera(arbol, usuario, MOTIVO)
    crear_planilla(ruta_planilla, [fila(codigo="S01-A001", observaciones="Palma")])

    with pytest.raises(ValueError, match="está en la papelera; puede restaurarse"):
        importar_planilla(ruta_planilla)

    guardado = Arbol.todos.get(codigo="S01-A001")
    assert guardado.observaciones == "Molle"  # no se actualizó en silencio
    assert guardado.eliminado_en is not None


def test_importar_planilla_sigue_actualizando_a_los_vigentes(nuevo_arbol, ruta_planilla):
    nuevo_arbol("S01-A001", observaciones="Molle", demo=False)
    crear_planilla(ruta_planilla, [fila(codigo="S01-A001", observaciones="Palma")])

    reporte = importar_planilla(ruta_planilla)

    assert reporte.actualizados == 1
    assert Arbol.objects.get(codigo="S01-A001").observaciones == "Palma"


# --- eliminación definitiva -------------------------------------------------------------------


def test_eliminar_definitivamente_borra_la_fila_de_la_papelera(nuevo_arbol, usuario):
    mover_a_papelera(nuevo_arbol("S01-A001", demo=False), usuario, MOTIVO)

    eliminar_definitivamente(Arbol.todos.get(codigo="S01-A001"), usuario)

    assert not Arbol.todos.filter(codigo="S01-A001").exists()


def test_no_se_elimina_en_definitiva_un_arbol_vigente(nuevo_arbol, usuario):
    arbol = nuevo_arbol(demo=False)

    with pytest.raises(ValueError, match="papelera"):
        eliminar_definitivamente(arbol, usuario)

    assert Arbol.objects.filter(codigo="S01-A001").exists()


def test_no_se_elimina_en_definitiva_un_simulado(nuevo_arbol, usuario):
    mover_a_papelera(nuevo_arbol("S01-A001", demo=True), usuario, MOTIVO)

    with pytest.raises(ValueError, match="ejemplo"):
        eliminar_definitivamente(Arbol.todos.get(codigo="S01-A001"), usuario)

    assert Arbol.todos.filter(codigo="S01-A001").exists()


# --- destacados y papelera --------------------------------------------------------------------


def test_el_tope_de_destacados_se_respeta_sin_papelera(nuevo_arbol):
    llenar_de_destacados(nuevo_arbol)
    sexto = Arbol(
        codigo="S01-A006",
        sector_id=1,
        fuente="Prueba",
        destacado=True,
        motivo_destacado=MOTIVO_DESTACADO,
    )

    with pytest.raises(ValidationError) as error:
        sexto.full_clean()

    assert "destacado" in error.value.message_dict


def test_un_destacado_en_la_papelera_deja_de_contar_para_el_tope(nuevo_arbol, usuario):
    destacados = llenar_de_destacados(nuevo_arbol)
    mover_a_papelera(destacados[0], usuario, MOTIVO)

    sexto = nuevo_arbol("S01-A006")
    sexto.destacado, sexto.motivo_destacado = True, MOTIVO_DESTACADO
    sexto.full_clean()
    sexto.save()

    assert Arbol.objects.filter(sector_id=1, destacado=True).count() == TOPE_DESTACADOS_POR_SECTOR


def test_restaurar_en_un_sector_lleno_vuelve_sin_la_marca(nuevo_arbol, usuario):
    destacados = llenar_de_destacados(nuevo_arbol)
    mover_a_papelera(destacados[0], usuario, MOTIVO)
    sexto = nuevo_arbol("S01-A006")
    sexto.destacado, sexto.motivo_destacado = True, MOTIVO_DESTACADO
    sexto.save()

    resultado = restaurar(Arbol.todos.get(codigo="S01-A001"), usuario)

    vuelto = Arbol.objects.get(codigo="S01-A001")
    assert resultado.perdio_destacado is True
    assert (vuelto.destacado, vuelto.motivo_destacado) == (False, None)
    assert Arbol.objects.filter(sector_id=1, destacado=True).count() == TOPE_DESTACADOS_POR_SECTOR


def test_restaurar_con_lugar_en_el_sector_conserva_la_marca(nuevo_arbol, usuario):
    destacados = llenar_de_destacados(nuevo_arbol)
    mover_a_papelera(destacados[0], usuario, MOTIVO)

    resultado = restaurar(Arbol.todos.get(codigo="S01-A001"), usuario)

    assert resultado.perdio_destacado is False
    assert Arbol.objects.get(codigo="S01-A001").destacado is True
