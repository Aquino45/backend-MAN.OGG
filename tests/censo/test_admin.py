"""Tests del panel de administración: páginas por rol, permisos, mapa, papelera y avisos."""

import importlib

import pytest
from django.apps import apps as registro_de_apps
from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.contrib.gis.db.models.functions import Transform
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.censo.models import Arbol, Sector
from apps.censo.servicios.papelera import mover_a_papelera
from config import constantes
from config.constantes import (
    CAMPO_MOTIVO_ELIMINACION,
    NOMBRE_ROL_ADMINISTRADOR,
    NOMBRE_ROL_EDITOR,
    PERMISOS_POR_ROL,
    SRID_MAPA,
    TITULO_ADMIN,
    TOPE_DESTACADOS_POR_SECTOR,
)
from tests.censo.conftest import FUENTE_PANEL, cliente_de, usuario_con_rol

MOTIVO = "Se registró dos veces por error"
MOTIVO_DESTACADO = "Ejemplar de mayor copa del sector"
MIGRACION_DE_ROLES = "apps.censo.migrations.0004_grupos_de_roles"
ROLES = ["cliente_administrador", "cliente_editor"]


def datos_de_alta(**extra):
    datos = {"codigo": "S01-A010", "sector": 1, "fuente": FUENTE_PANEL}
    datos.update(extra)
    return datos


def mensajes(respuesta):
    return [str(mensaje) for mensaje in respuesta.context["messages"]]


@pytest.fixture
def panel_con_datos(nuevo_arbol, usuario_administrador):
    """Un árbol vigente y otro en la papelera; devuelve (vigente, en_papelera)."""
    vigente = nuevo_arbol("S01-A001", nombre_comun="Molle")
    en_papelera = nuevo_arbol("S01-A002")
    mover_a_papelera(en_papelera, usuario_administrador, MOTIVO)
    return vigente, Arbol.todos.get(codigo="S01-A002")


# --- páginas ----------------------------------------------------------------------------------


@pytest.mark.parametrize("rol", ROLES)
def test_las_paginas_del_panel_responden_200_a_cada_rol(rol, panel_con_datos, request):
    cliente = request.getfixturevalue(rol)
    vigente, en_papelera = panel_con_datos
    rutas = [
        reverse("admin:censo_arbol_changelist"),
        reverse("admin:censo_arbol_add"),
        reverse("admin:censo_arbol_change", args=[vigente.pk]),
        reverse("admin:censo_arbolenpapelera_changelist"),
        reverse("admin:censo_arbolenpapelera_change", args=[en_papelera.pk]),
        reverse("admin:censo_sector_changelist"),
        reverse("admin:censo_sector_change", args=[1]),
    ]

    assert [cliente.get(ruta).status_code for ruta in rutas] == [200] * len(rutas)


def test_solo_el_administrador_crea_sectores(cliente_administrador, cliente_editor, sectores):
    assert cliente_administrador.get(reverse("admin:censo_sector_add")).status_code == 200
    assert cliente_editor.get(reverse("admin:censo_sector_add")).status_code == 403


def test_el_editor_no_edita_sectores(cliente_editor, sectores):
    ruta = reverse("admin:censo_sector_change", args=[1])

    respuesta = cliente_editor.post(ruta, {"nombre": "Otro nombre"})

    assert respuesta.status_code == 403
    assert Sector.objects.get(id=1).nombre != "Otro nombre"


def test_los_sectores_no_se_borran_desde_el_panel(cliente_administrador, sectores):
    ruta = reverse("admin:censo_sector_delete", args=[1])

    assert cliente_administrador.get(ruta).status_code == 403
    assert cliente_administrador.post(ruta, {"post": "yes"}).status_code == 403
    assert Sector.objects.filter(id=1).exists()


def test_el_encabezado_y_el_titulo_salen_de_las_constantes():
    assert admin.site.site_header == TITULO_ADMIN
    assert admin.site.site_title == TITULO_ADMIN
    assert admin.site.index_title == TITULO_ADMIN


def test_el_mapa_arranca_centrado_en_el_campus_en_grados(cliente_administrador, sectores):
    formulario = (
        cliente_administrador.get(reverse("admin:censo_arbol_add")).context["adminform"].form
    )
    atributos = formulario.fields["ubicacion"].widget.attrs
    cajas = [
        sector.mapa.extent for sector in Sector.objects.annotate(mapa=Transform("geom", SRID_MAPA))
    ]

    assert atributos["default_lon"] == constantes.MAPA_ADMIN_LON
    assert atributos["default_lat"] == constantes.MAPA_ADMIN_LAT
    assert atributos["default_zoom"] == constantes.MAPA_ADMIN_ZOOM
    assert min(caja[0] for caja in cajas) < atributos["default_lon"] < max(c[2] for c in cajas)
    assert min(caja[1] for caja in cajas) < atributos["default_lat"] < max(c[3] for c in cajas)


# --- permisos y roles -------------------------------------------------------------------------


def codigos_de_permisos(usuario):
    return {permiso.split(".", 1)[1] for permiso in usuario.get_all_permissions()}


def test_el_administrador_tiene_todo_y_el_editor_no(usuario_administrador, usuario_editor):
    administrador = codigos_de_permisos(usuario_administrador)
    editor = codigos_de_permisos(usuario_editor)

    assert administrador == set(PERMISOS_POR_ROL[NOMBRE_ROL_ADMINISTRADOR])
    assert editor == set(PERMISOS_POR_ROL[NOMBRE_ROL_EDITOR])
    assert {"change_sector", "cambiar_demo", "delete_arbolenpapelera"} <= administrador
    assert not {"change_sector", "add_sector", "cambiar_demo", "delete_arbolenpapelera"} & editor
    assert {"add_arbol", "change_arbol", "delete_arbol", "change_arbolenpapelera"} <= editor


def test_la_migracion_de_roles_se_puede_repetir_sin_duplicar(db):
    crear_grupos = importlib.import_module(MIGRACION_DE_ROLES).crear_grupos

    crear_grupos(registro_de_apps, None)
    crear_grupos(registro_de_apps, None)

    nombres = list(Group.objects.filter(name__in=PERMISOS_POR_ROL).values_list("name", flat=True))
    assert sorted(nombres) == sorted(PERMISOS_POR_ROL)
    for nombre, codigos in PERMISOS_POR_ROL.items():
        asignados = Group.objects.get(name=nombre).permissions.values_list("codename", flat=True)
        assert sorted(asignados) == sorted(codigos)


def test_la_migracion_de_roles_crea_los_permisos_si_aun_no_existen(db):
    crear_grupos = importlib.import_module(MIGRACION_DE_ROLES).crear_grupos
    Permission.objects.filter(content_type__app_label="censo").delete()
    Group.objects.filter(name__in=PERMISOS_POR_ROL).delete()

    crear_grupos(registro_de_apps, None)

    for nombre, codigos in PERMISOS_POR_ROL.items():
        asignados = Group.objects.get(name=nombre).permissions.values_list("codename", flat=True)
        assert sorted(asignados) == sorted(codigos)


def test_la_marca_demo_solo_la_cambia_quien_tiene_el_permiso(
    sectores, cliente_editor, cliente_administrador
):
    cliente_editor.post(reverse("admin:censo_arbol_add"), datos_de_alta(demo="on"))
    cliente_administrador.post(
        reverse("admin:censo_arbol_add"), datos_de_alta(codigo="S01-A011", demo="on")
    )

    assert Arbol.objects.get(codigo="S01-A010").demo is False
    assert Arbol.objects.get(codigo="S01-A011").demo is True


def test_las_contrasenas_debiles_se_rechazan():
    for clave in ("12345678", "password", "corta"):
        with pytest.raises(ValidationError):
            validate_password(clave)


# --- formulario -------------------------------------------------------------------------------


def test_la_fuente_es_obligatoria_en_el_alta(sectores, cliente_editor):
    respuesta = cliente_editor.post(reverse("admin:censo_arbol_add"), datos_de_alta(fuente=""))

    assert respuesta.status_code == 200
    assert "fuente" in respuesta.context["adminform"].form.errors
    assert not Arbol.todos.exists()


@pytest.mark.parametrize("motivo", ["", "    "])
def test_un_destacado_solo_con_espacios_se_rechaza_en_el_panel(sectores, cliente_editor, motivo):
    datos = datos_de_alta(destacado="on", motivo_destacado=motivo)

    respuesta = cliente_editor.post(reverse("admin:censo_arbol_add"), datos)

    assert respuesta.status_code == 200
    assert "motivo_destacado" in respuesta.context["adminform"].form.errors
    assert not Arbol.todos.exists()


def test_el_tope_de_destacados_se_avisa_en_el_panel(nuevo_arbol, cliente_editor):
    for numero in range(1, TOPE_DESTACADOS_POR_SECTOR + 1):
        nuevo_arbol(f"S01-A{numero:03d}", destacado=True, motivo_destacado=MOTIVO_DESTACADO)
    datos = datos_de_alta(destacado="on", motivo_destacado=MOTIVO_DESTACADO)

    respuesta = cliente_editor.post(reverse("admin:censo_arbol_add"), datos)

    assert respuesta.status_code == 200
    assert "destacado" in respuesta.context["adminform"].form.errors


def test_un_codigo_de_la_papelera_se_rechaza_con_mensaje_y_sin_error_de_bd(
    panel_con_datos, cliente_editor
):
    respuesta = cliente_editor.post(
        reverse("admin:censo_arbol_add"), datos_de_alta(codigo="S01-A002")
    )

    assert respuesta.status_code == 200
    assert "está en la papelera; puede restaurarse" in respuesta.content.decode()
    assert Arbol.todos.filter(codigo="S01-A002").count() == 1


def test_un_arbol_de_ejemplo_muestra_el_aviso(panel_con_datos, cliente_editor):
    vigente, _ = panel_con_datos

    pagina = cliente_editor.get(reverse("admin:censo_arbol_change", args=[vigente.pk]))

    assert "Dato de ejemplo" in pagina.content.decode()


# --- eliminar = mover a la papelera -----------------------------------------------------------


def test_el_boton_eliminar_pide_el_motivo_y_no_borra_la_fila(nuevo_arbol, cliente_editor):
    arbol = nuevo_arbol()
    ruta = reverse("admin:censo_arbol_delete", args=[arbol.pk])

    pagina = cliente_editor.get(ruta)
    sin_motivo = cliente_editor.post(ruta, {"post": "yes", CAMPO_MOTIVO_ELIMINACION: "  "})
    assert Arbol.objects.filter(pk=arbol.pk).exists()
    con_motivo = cliente_editor.post(ruta, {"post": "yes", CAMPO_MOTIVO_ELIMINACION: MOTIVO})

    assert "admin/censo/arbol/delete_confirmation.html" in [t.name for t in pagina.templates]
    assert f'name="{CAMPO_MOTIVO_ELIMINACION}"' in pagina.content.decode()
    assert sin_motivo.status_code == 302 and con_motivo.status_code == 302
    guardado = Arbol.todos.get(pk=arbol.pk)
    assert guardado.motivo_eliminacion == MOTIVO
    assert guardado.eliminado_por.username == "editor-prueba"


def test_la_accion_masiva_manda_a_la_papelera_con_motivo(nuevo_arbol, cliente_editor):
    primero, segundo = nuevo_arbol("S01-A001"), nuevo_arbol("S01-A002")
    ruta = reverse("admin:censo_arbol_changelist")
    datos = {"action": "mandar_a_la_papelera", "_selected_action": [primero.pk, segundo.pk]}

    cliente_editor.post(ruta, {**datos, CAMPO_MOTIVO_ELIMINACION: ""}, follow=True)
    assert Arbol.objects.count() == 2
    cliente_editor.post(ruta, {**datos, CAMPO_MOTIVO_ELIMINACION: MOTIVO})

    assert Arbol.objects.count() == 0
    assert Arbol.todos.filter(motivo_eliminacion=MOTIVO).count() == 2


def test_el_admin_no_ofrece_el_borrado_masivo_en_duro_de_arboles(cliente_editor, nuevo_arbol):
    nuevo_arbol()
    respuesta = cliente_editor.get(reverse("admin:censo_arbol_changelist"))

    assert "delete_selected" not in dict(respuesta.context["action_form"].fields["action"].choices)


# --- vista de la papelera ---------------------------------------------------------------------


def test_la_papelera_lista_quien_cuando_y_por_que(panel_con_datos, cliente_editor):
    respuesta = cliente_editor.get(reverse("admin:censo_arbolenpapelera_changelist"))

    contenido = respuesta.content.decode()
    assert "S01-A002" in contenido and "S01-A001" not in contenido
    assert MOTIVO in contenido and "administrador-prueba" in contenido


def test_restaurar_desde_la_papelera(panel_con_datos, cliente_editor):
    _, en_papelera = panel_con_datos
    ruta = reverse("admin:censo_arbolenpapelera_changelist")

    cliente_editor.post(ruta, {"action": "restaurar", "_selected_action": [en_papelera.pk]})

    assert Arbol.objects.filter(codigo="S01-A002").exists()


def test_restaurar_en_un_sector_lleno_avisa_que_perdio_el_destacado(
    nuevo_arbol, cliente_editor, usuario_editor
):
    primero = nuevo_arbol("S01-A001", destacado=True, motivo_destacado=MOTIVO_DESTACADO)
    mover_a_papelera(primero, usuario_editor, MOTIVO)
    for numero in range(2, TOPE_DESTACADOS_POR_SECTOR + 2):
        nuevo_arbol(f"S01-A{numero:03d}", destacado=True, motivo_destacado=MOTIVO_DESTACADO)
    ruta = reverse("admin:censo_arbolenpapelera_changelist")

    respuesta = cliente_editor.post(
        ruta, {"action": "restaurar", "_selected_action": [primero.pk]}, follow=True
    )

    assert Arbol.objects.get(codigo="S01-A001").destacado is False
    assert any("S01-A001" in m and "destacado" in m for m in mensajes(respuesta))


def test_solo_el_administrador_elimina_definitivamente(nuevo_arbol, usuario_administrador):
    ruta = reverse("admin:censo_arbolenpapelera_changelist")
    for numero in (1, 2):
        mover_a_papelera(nuevo_arbol(f"S01-A00{numero}", demo=False), usuario_administrador, MOTIVO)
    ids = list(Arbol.todos.values_list("pk", flat=True))
    datos = {"action": "delete_selected", "_selected_action": ids, "post": "yes"}
    editor = cliente_de(usuario_con_rol("otro-editor", NOMBRE_ROL_EDITOR))
    editor.post(ruta, datos)
    assert Arbol.todos.count() == 2

    cliente_de(usuario_administrador).post(ruta, datos)

    assert Arbol.todos.count() == 0


def test_la_papelera_no_permite_crear_arboles(cliente_administrador, sectores):
    assert cliente_administrador.get(reverse("admin:censo_arbolenpapelera_add")).status_code == 403


# --- eliminar con un árbol que no valida: avisa y no deja nada a medias -----------------------


def arbol_que_no_valida(nuevo_arbol, codigo):
    """Destacado con motivo de solo espacios: la BD lo acepta, pero full_clean lo rechaza."""
    arbol = nuevo_arbol(codigo, destacado=True, motivo_destacado=MOTIVO_DESTACADO)
    Arbol.objects.filter(pk=arbol.pk).update(motivo_destacado="   ")
    return arbol


def test_la_accion_masiva_con_un_arbol_invalido_avisa_y_no_mueve_ninguno(
    nuevo_arbol, cliente_editor
):
    bueno, malo = nuevo_arbol("S01-A001"), arbol_que_no_valida(nuevo_arbol, "S01-A002")
    datos = {
        "action": "mandar_a_la_papelera",
        "_selected_action": [bueno.pk, malo.pk],
        CAMPO_MOTIVO_ELIMINACION: MOTIVO,
    }

    respuesta = cliente_editor.post(reverse("admin:censo_arbol_changelist"), datos, follow=True)

    assert respuesta.status_code == 200
    assert Arbol.objects.count() == 2
    assert any("S01-A002" in aviso for aviso in mensajes(respuesta))


def test_el_boton_eliminar_con_un_arbol_invalido_avisa_sin_error_ni_exito(
    nuevo_arbol, cliente_editor
):
    malo = arbol_que_no_valida(nuevo_arbol, "S01-A002")
    ruta = reverse("admin:censo_arbol_delete", args=[malo.pk])

    respuesta = cliente_editor.post(
        ruta, {"post": "yes", CAMPO_MOTIVO_ELIMINACION: MOTIVO}, follow=True
    )

    assert respuesta.status_code == 200
    assert Arbol.objects.filter(pk=malo.pk).exists()
    avisos = mensajes(respuesta)
    assert any("S01-A002" in aviso for aviso in avisos)
    assert not any("puede restaurarse" in aviso for aviso in avisos)
