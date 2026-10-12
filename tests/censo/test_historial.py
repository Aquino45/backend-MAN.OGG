"""Tests del historial con versiones: quién, cuándo, qué cambió y la vuelta a una versión."""

import pytest
from django.urls import reverse

from apps.censo.models import Arbol, Sector
from apps.censo.servicios.papelera import mover_a_papelera, restaurar
from config.constantes import TOPE_DESTACADOS_POR_SECTOR
from tests.censo.conftest import FUENTE_PANEL

MOTIVO = "Se registró dos veces por error"
MOTIVO_DESTACADO = "Ejemplar de mayor copa del sector"


def datos_de_alta(**extra):
    datos = {"codigo": "S01-A010", "sector": 1, "fuente": FUENTE_PANEL}
    datos.update(extra)
    return datos


def test_el_alta_desde_el_panel_queda_con_el_usuario_del_request(
    sectores, cliente_editor, usuario_editor
):
    respuesta = cliente_editor.post(reverse("admin:censo_arbol_add"), datos_de_alta())

    assert respuesta.status_code == 302
    version = Arbol.todos.get(codigo="S01-A010").history.get()
    assert version.history_type == "+"
    assert version.history_user == usuario_editor
    assert version.history_date is not None


def test_cada_cambio_queda_con_sus_diferencias(
    nuevo_arbol, cliente_administrador, usuario_administrador
):
    arbol = nuevo_arbol("S01-A010", observaciones="Molle")
    datos = datos_de_alta(observaciones="Palma real")

    cliente_administrador.post(reverse("admin:censo_arbol_change", args=[arbol.pk]), datos)

    ultima, anterior = arbol.history.all()[:2]
    assert ultima.history_type == "~"
    assert ultima.history_user == usuario_administrador
    cambios = ultima.diff_against(anterior).changes
    assert {(cambio.field, cambio.old, cambio.new) for cambio in cambios} >= {
        ("observaciones", "Molle", "Palma real")
    }


def test_mover_a_la_papelera_y_restaurar_quedan_en_el_historial(nuevo_arbol, usuario_editor):
    arbol = nuevo_arbol()

    mover_a_papelera(arbol, usuario_editor, MOTIVO)
    restaurar(Arbol.todos.get(codigo="S01-A001"), usuario_editor)

    alta, papelera, restauracion = reversed(list(arbol.history.all()))
    assert (papelera.history_user, restauracion.history_user) == (usuario_editor, usuario_editor)
    assert MOTIVO in papelera.history_change_reason
    assert papelera.eliminado_en is not None
    assert restauracion.eliminado_en is None
    campos = {cambio.field for cambio in papelera.diff_against(alta).changes}
    assert {"eliminado_en", "eliminado_por", "motivo_eliminacion"} <= campos


def test_un_cambio_de_sector_tambien_queda_en_el_historial(sectores, usuario_editor):
    sector = Sector.objects.get(id=1)
    sector.nombre = "Sector renombrado en la prueba"
    sector._history_user = usuario_editor
    sector.save()

    ultima = sector.history.first()
    assert ultima.history_type == "~"
    assert ultima.history_user == usuario_editor


def test_el_panel_lista_las_versiones_de_un_arbol(nuevo_arbol, cliente_administrador):
    arbol = nuevo_arbol()

    respuesta = cliente_administrador.get(reverse("admin:censo_arbol_history", args=[arbol.pk]))

    assert respuesta.status_code == 200


@pytest.mark.parametrize("rol", ["cliente_administrador", "cliente_editor"])
def test_volver_a_una_version_anterior_queda_en_el_historial(nuevo_arbol, rol, request):
    cliente = request.getfixturevalue(rol)
    usuario = request.getfixturevalue(rol.replace("cliente", "usuario"))
    arbol = nuevo_arbol("S01-A010", observaciones="Molle")
    arbol.observaciones = "Palma real"
    arbol.save()
    version_vieja = arbol.history.filter(observaciones="Molle").get()
    url = reverse("admin:censo_arbol_simple_history", args=[arbol.pk, version_vieja.pk])

    assert cliente.get(url).status_code == 200
    respuesta = cliente.post(url, datos_de_alta(observaciones="Molle"))

    assert respuesta.status_code == 302
    assert Arbol.objects.get(pk=arbol.pk).observaciones == "Molle"
    ultima = arbol.history.first()
    assert ultima.observaciones == "Molle"
    assert ultima.history_user == usuario
    assert arbol.history.count() == 3


# --- volver a una versión no toca lo que no es del formulario ---------------------------------


def url_de_version(arbol, version):
    return reverse("admin:censo_arbol_simple_history", args=[arbol.pk, version.pk])


@pytest.mark.parametrize("rol", ["cliente_editor", "cliente_administrador"])
def test_volver_a_una_version_no_cambia_la_marca_demo(nuevo_arbol, rol, request):
    cliente = request.getfixturevalue(rol)
    arbol = nuevo_arbol("S01-A010", demo=True)
    arbol.demo = False
    arbol.save()
    version_vieja = arbol.history.filter(demo=True).get()

    cliente.post(url_de_version(arbol, version_vieja), datos_de_alta(demo="on"))

    assert Arbol.objects.get(pk=arbol.pk).demo is False


def test_volver_a_una_version_conserva_uid_y_fila_de_origen(nuevo_arbol, cliente_editor):
    arbol = nuevo_arbol("S01-A010", observaciones="Molle", fila_origen=7)
    uid = arbol.uid
    Arbol.objects.filter(pk=arbol.pk).update(fila_origen=9)
    arbol.refresh_from_db()
    arbol.observaciones = "Palma real"
    arbol.save()
    version_vieja = arbol.history.filter(observaciones="Molle").get()

    cliente_editor.post(url_de_version(arbol, version_vieja), datos_de_alta(observaciones="Molle"))

    actual = Arbol.objects.get(pk=arbol.pk)
    assert (actual.observaciones, actual.uid, actual.fila_origen) == ("Molle", uid, 9)


def test_volver_a_una_version_de_un_arbol_en_la_papelera_lo_deja_en_la_papelera(
    nuevo_arbol, cliente_editor, usuario_administrador
):
    arbol = nuevo_arbol("S01-A010", observaciones="Molle")
    arbol.observaciones = "Palma real"
    arbol.save()
    mover_a_papelera(arbol, usuario_administrador, MOTIVO)
    version_vieja = arbol.history.filter(observaciones="Molle").get()
    versiones_antes = arbol.history.count()

    cliente_editor.post(url_de_version(arbol, version_vieja), datos_de_alta(observaciones="Molle"))

    actual = Arbol.todos.get(pk=arbol.pk)
    assert actual.observaciones == "Molle"
    assert actual.eliminado_en is not None
    assert (actual.eliminado_por, actual.motivo_eliminacion) == (usuario_administrador, MOTIVO)
    assert arbol.history.count() == versiones_antes + 1
    assert "Restaurado" not in (arbol.history.first().history_change_reason or "")


def test_una_version_que_estaba_en_la_papelera_no_manda_al_arbol_vigente_a_ella(
    nuevo_arbol, cliente_editor, usuario_editor
):
    arbol = nuevo_arbol("S01-A010")
    mover_a_papelera(arbol, usuario_editor, MOTIVO)
    restaurar(Arbol.todos.get(pk=arbol.pk), usuario_editor)
    version_en_papelera = arbol.history.filter(eliminado_en__isnull=False).get()

    cliente_editor.post(url_de_version(arbol, version_en_papelera), datos_de_alta())

    actual = Arbol.objects.get(pk=arbol.pk)
    assert (actual.eliminado_en, actual.eliminado_por, actual.motivo_eliminacion) == (
        None,
        None,
        None,
    )


def test_volver_a_una_version_sigue_validando_el_tope_de_destacados(nuevo_arbol, cliente_editor):
    primero = nuevo_arbol("S01-A001", destacado=True, motivo_destacado=MOTIVO_DESTACADO)
    primero.destacado, primero.motivo_destacado = False, None
    primero.save()
    version_vieja = primero.history.filter(destacado=True).get()
    for numero in range(2, TOPE_DESTACADOS_POR_SECTOR + 2):
        nuevo_arbol(f"S01-A{numero:03d}", destacado=True, motivo_destacado=MOTIVO_DESTACADO)
    datos = datos_de_alta(codigo="S01-A001", destacado="on", motivo_destacado=MOTIVO_DESTACADO)

    respuesta = cliente_editor.post(url_de_version(primero, version_vieja), datos)

    assert respuesta.status_code == 200
    assert Arbol.objects.get(pk=primero.pk).destacado is False


def test_volver_a_una_version_devuelve_tambien_la_marca_de_co2_simulado():
    from config.constantes import CAMPOS_FUERA_DE_LA_REVERSION

    assert "co2_simulado" not in CAMPOS_FUERA_DE_LA_REVERSION
