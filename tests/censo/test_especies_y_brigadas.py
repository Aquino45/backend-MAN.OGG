"""Tests de Especie, Brigada y GrupoBrigada: reglas, historial, permisos por rol y panel."""

import importlib

import pytest
from django.apps import apps as registro_de_apps
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.urls import reverse

from apps.censo.admin_catalogos import EspecieForm
from apps.censo.models import Brigada, Especie, GrupoBrigada, ValorCatalogo
from apps.censo.servicios.validar_especie import validar_nombres_de_especie
from config.constantes import (
    FORMA_PALMA,
    NOMBRE_ROL_ADMINISTRADOR,
    NOMBRE_ROL_EDITOR,
    PERMISOS_CATALOGOS_POR_ROL,
)
from tests.censo.conftest import arbol_evaluado

MIGRACION_DE_PERMISOS = "apps.censo.migrations.0013_permisos_de_especies_y_brigadas"
FUENTE_FICHA = "Fuente de prueba de la ficha"

pytestmark = pytest.mark.django_db


def crear_especie(nombre_cientifico="Schinus molle", **extra):
    datos = {"nombre_comun": "Molle"}
    datos.update(extra)
    return Especie.objects.create(nombre_cientifico=nombre_cientifico, **datos)


# --- Especie ----------------------------------------------------------------------------------


def test_el_nombre_cientifico_es_unico():
    crear_especie()

    with pytest.raises(IntegrityError), transaction.atomic():
        crear_especie()


def test_una_especie_nueva_nace_revisada_y_con_la_ficha_sin_publicar():
    especie = crear_especie()

    assert (especie.revisada, especie.ficha_publicada) == (True, False)
    assert (especie.beneficios, especie.fuente_ficha) == ("", "")


def test_la_forma_solo_acepta_las_de_las_constantes():
    crear_especie(forma=FORMA_PALMA).full_clean()

    with pytest.raises(ValidationError) as error:
        crear_especie("Otra", forma="enredadera").full_clean()
    assert "forma" in error.value.message_dict


def test_el_origen_solo_acepta_valores_del_catalogo_de_origen():
    nativa = ValorCatalogo.objects.create(campo="origen", valor="Nativa", explicacion="x")
    bueno = ValorCatalogo.objects.create(campo="estado_general", valor="Bueno", explicacion="x")

    crear_especie(origen=nativa).full_clean()
    with pytest.raises(ValidationError) as error:
        crear_especie("Otra", origen=bueno).full_clean()
    assert "origen" in error.value.message_dict


def validar(nombre_cientifico, alias="", pk=None):
    validar_nombres_de_especie(nombre_cientifico, alias, pk)


def test_un_alias_no_puede_repetirse_entre_especies_ni_chocar_con_otro_nombre():
    crear_especie(alias="Schinus\nPimiento")

    with pytest.raises(ValidationError) as error:
        validar("Otra", "  PIMIENTO ")
    assert "alias" in error.value.message_dict
    with pytest.raises(ValidationError):
        validar("Otra 2", "schinus MOLLE")
    validar("Otra 3", "Pimiento falso")


def test_un_alias_no_puede_ser_el_nombre_comun_de_otra_especie():
    crear_especie(nombre_comun="Molle")

    with pytest.raises(ValidationError) as error:
        validar("Otra", "  MOLLE ")

    assert "Molle" in str(error.value.message_dict["alias"])


def test_un_nombre_cientifico_no_puede_ser_el_alias_ni_el_nombre_comun_de_otra_especie():
    crear_especie(nombre_comun="Molle", alias="Pimiento")

    for choque in ("pimiento", "  MOLLE", "schinus  Molle"):
        with pytest.raises(ValidationError) as error:
            validar(choque)
        assert "nombre_cientifico" in error.value.message_dict
    validar("Roystonea regia")


def test_una_especie_no_choca_consigo_misma_y_un_nombre_comun_repetido_se_permite():
    molle = crear_especie(nombre_comun="Molle", alias="Pimiento")

    validar(molle.nombre_cientifico, molle.alias, pk=molle.pk)
    validar("Otra", "Algo distinto")  # su nombre común puede repetirse: la ingesta lo trata


def test_el_formulario_de_la_especie_usa_la_misma_validacion():
    crear_especie(nombre_comun="Molle", alias="Pimiento")

    malo = EspecieForm(data={"nombre_cientifico": "Pimiento", "alias": "molle", "revisada": True})
    bueno = EspecieForm(data={"nombre_cientifico": "Roystonea regia", "revisada": True})

    assert not malo.is_valid()
    assert {"nombre_cientifico", "alias"} <= set(malo.errors)
    assert bueno.is_valid(), bueno.errors


def test_una_especie_puede_repetir_sus_propios_alias_al_guardar_de_nuevo():
    especie = crear_especie(alias="Schinus")

    validar(especie.nombre_cientifico, especie.alias, pk=especie.pk)
    especie.full_clean()


def test_la_ficha_publicada_exige_beneficios_fuente_y_nombre_comun():
    ficha = {"beneficios": "Da sombra", "fuente_ficha": FUENTE_FICHA}
    crear_especie(**ficha, ficha_publicada=True).full_clean()

    for faltante in ({"beneficios": ""}, {"fuente_ficha": ""}, {"nombre_comun": None}):
        datos = {"nombre_comun": "Molle", **ficha, **faltante}
        with pytest.raises(ValidationError) as error:
            Especie(nombre_cientifico="X", ficha_publicada=True, **datos).full_clean()
        assert "ficha_publicada" in error.value.message_dict


def test_la_bd_tambien_impide_publicar_una_ficha_incompleta():
    with pytest.raises(IntegrityError), transaction.atomic():
        crear_especie(ficha_publicada=True)


def test_los_opcionales_vacios_se_guardan_como_null():
    especie = crear_especie(familia="  ", dato_curioso="", cuidados="  ", fuente_densidad="")

    especie.full_clean()

    assert (especie.familia, especie.dato_curioso, especie.cuidados) == (None, None, None)
    assert especie.fuente_densidad is None


def test_los_cambios_de_una_especie_quedan_en_el_historial():
    especie = crear_especie()
    especie.nombre_comun = "Pimiento"
    especie.save()

    assert especie.history.count() == 2
    assert especie.history.first().nombre_comun == "Pimiento"


def test_una_especie_con_arboles_no_se_borra(sectores):
    arbol = arbol_evaluado("S01-A001")

    with pytest.raises(ProtectedError):
        arbol.especie.delete()


# --- Brigada y grupos -------------------------------------------------------------------------


def test_el_nombre_de_la_brigada_es_unico_y_el_del_grupo_lo_es_dentro_de_su_brigada():
    primera = Brigada.objects.create(nombre="Brigada Z")
    otra = Brigada.objects.create(nombre="Brigada Y")
    GrupoBrigada.objects.create(brigada=primera, nombre="Uno")
    GrupoBrigada.objects.create(brigada=otra, nombre="Uno")

    with pytest.raises(IntegrityError), transaction.atomic():
        Brigada.objects.create(nombre="Brigada Z")
    with pytest.raises(IntegrityError), transaction.atomic():
        GrupoBrigada.objects.create(brigada=primera, nombre="Uno")


def test_una_brigada_y_un_grupo_activos_por_defecto_y_con_historial():
    brigada = Brigada.objects.create(nombre="Brigada Z")
    grupo = GrupoBrigada.objects.create(brigada=brigada, nombre="Uno", integrantes="Ana\nLuis")
    grupo.nombre = "Dos"
    grupo.save()

    assert (brigada.activa, grupo.activo) == (True, True)
    assert brigada.history.count() == 1
    assert grupo.history.count() == 2
    assert str(grupo) == "Brigada Z · Dos"


def test_la_migracion_deja_la_brigada_inicial_con_sus_tres_grupos():
    grupos = Brigada.objects.get(nombre="Brigada A").grupos.values_list("nombre", flat=True)

    assert sorted(grupos) == ["Sopita", "zapatito", "zapato"]


def test_un_grupo_con_arboles_no_se_borra(sectores):
    grupo = GrupoBrigada.objects.get(nombre="zapato")
    arbol = arbol_evaluado("S01-A001")
    arbol.grupo = grupo
    arbol.save()

    with pytest.raises(ProtectedError):
        grupo.delete()


# --- permisos por rol -------------------------------------------------------------------------


def permisos_del_grupo(nombre):
    return set(Group.objects.get(name=nombre).permissions.values_list("codename", flat=True))


def test_el_administrador_hace_todo_y_el_editor_agrega_edita_y_ve():
    editor = permisos_del_grupo(NOMBRE_ROL_EDITOR)
    administrador = permisos_del_grupo(NOMBRE_ROL_ADMINISTRADOR)

    for modelo in ("especie", "brigada", "grupobrigada"):
        sin_borrar = {f"add_{modelo}", f"change_{modelo}", f"view_{modelo}"}
        assert sin_borrar <= editor
        assert f"delete_{modelo}" not in editor
        assert sin_borrar | {f"delete_{modelo}"} <= administrador


def test_la_migracion_de_permisos_se_repite_sin_duplicar():
    sumar = importlib.import_module(MIGRACION_DE_PERMISOS).sumar_permisos
    antes = {nombre: permisos_del_grupo(nombre) for nombre in PERMISOS_CATALOGOS_POR_ROL}

    sumar(registro_de_apps, None)
    sumar(registro_de_apps, None)

    for nombre, codigos in PERMISOS_CATALOGOS_POR_ROL.items():
        assert permisos_del_grupo(nombre) == antes[nombre]
        assert set(codigos) <= permisos_del_grupo(nombre)


def test_la_ficha_de_especie_ya_no_tiene_permisos():
    assert not Group.objects.filter(permissions__codename__endswith="fichaespecie").exists()


# --- panel ------------------------------------------------------------------------------------

FORMULARIO_DE_ESPECIE = {
    "nombre_cientifico": "Schinus molle",
    "nombre_comun": "Molle",
    "alias": "Schinus",
    "revisada": "on",
}


@pytest.mark.parametrize("rol", ["cliente_administrador", "cliente_editor"])
def test_las_paginas_de_especie_y_brigada_responden_200(rol, request):
    cliente = request.getfixturevalue(rol)
    especie = crear_especie()
    brigada = Brigada.objects.get(nombre="Brigada A")

    for tabla, objeto in (("especie", especie), ("brigada", brigada)):
        for nombre, args in (("changelist", []), ("add", []), ("change", [objeto.pk])):
            assert (
                cliente.get(reverse(f"admin:censo_{tabla}_{nombre}", args=args)).status_code == 200
            )
        assert (
            cliente.get(reverse(f"admin:censo_{tabla}_history", args=[objeto.pk])).status_code
            == 200
        )


def test_el_editor_agrega_y_edita_una_especie_con_su_ficha_y_el_alta_queda_en_el_historial(
    cliente_editor,
):
    respuesta = cliente_editor.post(reverse("admin:censo_especie_add"), FORMULARIO_DE_ESPECIE)

    especie = Especie.objects.get(nombre_cientifico="Schinus molle")
    assert respuesta.status_code == 302
    assert especie.history.count() == 1
    respuesta = cliente_editor.post(
        reverse("admin:censo_especie_change", args=[especie.pk]),
        {
            **FORMULARIO_DE_ESPECIE,
            "beneficios": "Da sombra",
            "fuente_ficha": FUENTE_FICHA,
            "ficha_publicada": "on",
        },
    )
    especie.refresh_from_db()
    assert respuesta.status_code == 302
    assert especie.ficha_publicada is True


def test_el_editor_no_borra_una_especie_y_el_administrador_si(
    cliente_editor, cliente_administrador
):
    especie = crear_especie()
    url = reverse("admin:censo_especie_delete", args=[especie.pk])

    assert cliente_editor.post(url, {"post": "yes"}).status_code == 403
    assert Especie.objects.count() == 1
    cliente_administrador.post(url, {"post": "yes"})
    assert Especie.objects.count() == 0


def test_un_alias_repetido_no_se_guarda_desde_el_panel(cliente_editor):
    crear_especie("Prosopis pallida", alias="Algarrobo")

    respuesta = cliente_editor.post(
        reverse("admin:censo_especie_add"), {**FORMULARIO_DE_ESPECIE, "alias": "algarrobo"}
    )

    assert respuesta.status_code == 200
    assert Especie.objects.count() == 1


def test_los_grupos_se_editan_dentro_de_la_brigada(cliente_editor):
    brigada = Brigada.objects.get(nombre="Brigada A")
    url = reverse("admin:censo_brigada_change", args=[brigada.pk])
    grupos = list(brigada.grupos.order_by("pk"))
    datos = {
        "nombre": brigada.nombre,
        "activa": "on",
        "grupos-TOTAL_FORMS": len(grupos) + 1,
        "grupos-INITIAL_FORMS": len(grupos),
        "grupos-MIN_NUM_FORMS": 0,
        "grupos-MAX_NUM_FORMS": 1000,
    }
    for indice, grupo in enumerate(grupos):
        datos.update(
            {
                f"grupos-{indice}-id": grupo.pk,
                f"grupos-{indice}-brigada": brigada.pk,
                f"grupos-{indice}-nombre": grupo.nombre,
                f"grupos-{indice}-activo": "on",
            }
        )
    nuevo = len(grupos)
    datos.update({f"grupos-{nuevo}-brigada": brigada.pk, f"grupos-{nuevo}-nombre": "Cuarto"})
    datos[f"grupos-{nuevo}-activo"] = "on"

    respuesta = cliente_editor.post(url, datos)

    assert respuesta.status_code == 302
    assert brigada.grupos.filter(nombre="Cuarto").exists()
