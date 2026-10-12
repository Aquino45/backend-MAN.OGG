"""Tests de las cápsulas de ayuda: catálogo, armado por árbol, fichas de especie y carga inicial."""

import importlib
import json
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

import pytest
from django.apps import apps as registro_de_apps
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.censo.models import AyudaCampo, Especie, ValorCatalogo
from apps.censo.selectores import (
    arbol_por_codigo,
    conteo_de_valores_de_arboles,
    valores_fuera_del_catalogo,
)
from apps.censo.servicios.capsulas import (
    armar_capsulas,
    buscar_ficha,
    cargar_capsulas,
    normalizar,
)
from config.constantes import (
    CAMPOS_CATALOGADOS,
    CAMPOS_CON_AYUDA,
    NOMBRE_ROL_ADMINISTRADOR,
    NOMBRE_ROL_EDITOR,
    PERMISOS_CAPSULAS_POR_ROL,
    PERMISOS_POR_ROL,
)
from tests.censo.conftest import arbol_de_ejemplo

RUTA_CAPSULAS = Path(__file__).resolve().parents[2] / "datos" / "capsulas" / "capsulas-v0.json"
MIGRACION_DE_CAPSULAS = "apps.censo.migrations.0006_permisos_de_capsulas"
MIGRACION_DE_ROLES = "apps.censo.migrations.0004_grupos_de_roles"
FUENTE_FICHA = "Fuente de prueba de la ficha"
EXPLICACION_BUENO = "Está sano y no necesita atención."
MODELOS_DE_CAPSULAS = ("ayudacampo", "valorcatalogo")
EN_LA_PAPELERA = {"eliminado_en": datetime(2026, 1, 1, tzinfo=UTC), "motivo_eliminacion": "Prueba"}


def crear_ayuda(campo="estado_general", **extra):
    datos = {"titulo": "Estado general", "que_es": "Cómo se ve el árbol en conjunto."}
    datos.update(extra)
    return AyudaCampo.objects.create(campo=campo, **datos)


def crear_valor(campo="estado_general", valor="Bueno", **extra):
    datos = {"explicacion": EXPLICACION_BUENO}
    datos.update(extra)
    return ValorCatalogo.objects.create(campo=campo, valor=valor, **datos)


def crear_ficha(nombre_cientifico="Schinus molle", **extra):
    datos = {
        "nombre_comun": "Molle",
        "beneficios": "Da sombra\nAtrae aves",
        "fuente_ficha": FUENTE_FICHA,
        "ficha_publicada": True,
    }
    datos.update(extra)
    return Especie.objects.create(nombre_cientifico=nombre_cientifico, **datos)


def escribir(ruta, **secciones):
    ruta.write_text(json.dumps(secciones, ensure_ascii=False), encoding="utf-8")
    return ruta


def ayuda_json(campo="estado_general", **extra):
    return {"campo": campo, "titulo": "Estado general", "que_es": "Cómo se ve.", **extra}


def valor_json(campo="estado_general", valor="Bueno", **extra):
    return {"campo": campo, "valor": valor, "orden": 1, "explicacion": "Sano.", **extra}


def ficha_json(**extra):
    datos = {
        "nombre_cientifico": "Schinus molle",
        "nombre_comun": "Molle",
        "alias": ["Molle costeño"],
        "beneficios": ["Da sombra"],
        "dato_curioso": None,
        "cuidados": None,
        "fuente": FUENTE_FICHA,
        "publicada": False,
    }
    datos.update(extra)
    return datos


def total_en_bd():
    return (AyudaCampo.objects.count(), ValorCatalogo.objects.count(), Especie.objects.count())


# --- normalizar -------------------------------------------------------------------------------


def test_normalizar_ignora_mayusculas_acentos_y_espacios_de_mas():
    assert normalizar("  Árbol   ≥1.30 m ") == normalizar("arbol ≥1.30 m")
    assert normalizar("Bueno") == normalizar("bueno") == "bueno"
    assert normalizar("Prosopis\tPallida") == "prosopis pallida"
    assert normalizar(None) == ""


# --- armar_capsulas ---------------------------------------------------------------------------


def test_una_capsula_por_ayuda_activa_en_su_orden(nuevo_arbol):
    arbol = nuevo_arbol(estado_general="Bueno")
    crear_ayuda("estado_copa", orden=2, titulo="Copa")
    crear_ayuda("estado_general", orden=1)
    crear_ayuda("codigo", orden=2, titulo="Código")
    crear_ayuda("origen", activo=False)

    capsulas = armar_capsulas(arbol, AyudaCampo.objects.all(), [])

    assert [c["campo"] for c in capsulas] == ["estado_general", "codigo", "estado_copa"]
    assert set(capsulas[0]) == {"campo", "titulo", "que_es", "en_este_arbol"}


def test_en_este_arbol_trae_la_explicacion_del_valor_del_arbol(nuevo_arbol):
    arbol = nuevo_arbol(estado_general="Bueno", estado_copa="Parcial")
    crear_ayuda("estado_general")
    crear_ayuda("estado_copa", titulo="Copa")
    crear_valor("estado_general", "Bueno")

    capsulas = armar_capsulas(arbol, AyudaCampo.objects.all(), ValorCatalogo.objects.all())

    por_campo = {c["campo"]: c["en_este_arbol"] for c in capsulas}
    assert por_campo == {"estado_general": EXPLICACION_BUENO, "estado_copa": None}


def test_el_valor_se_compara_normalizado_bueno_es_igual_a_Bueno(nuevo_arbol):
    arbol = nuevo_arbol(estado_general="  bueno ")
    crear_ayuda()
    crear_valor(valor="Bueno")

    capsulas = armar_capsulas(arbol, AyudaCampo.objects.all(), ValorCatalogo.objects.all())

    assert capsulas[0]["en_este_arbol"] == EXPLICACION_BUENO


def test_en_este_arbol_es_null_si_el_campo_no_es_del_arbol_o_esta_vacio(nuevo_arbol):
    arbol = nuevo_arbol(estado_general=None)
    crear_ayuda("estado_general")
    crear_ayuda("ubicacion", titulo="Ubicación")
    crear_valor("estado_general", "Bueno")

    capsulas = armar_capsulas(arbol, AyudaCampo.objects.all(), ValorCatalogo.objects.all())

    assert [c["en_este_arbol"] for c in capsulas] == [None, None]


def test_un_valor_inactivo_no_explica_nada(nuevo_arbol):
    arbol = nuevo_arbol(estado_general="Bueno")
    crear_ayuda()
    crear_valor(activo=False)

    capsulas = armar_capsulas(arbol, AyudaCampo.objects.all(), ValorCatalogo.objects.all())

    assert capsulas[0]["en_este_arbol"] is None


def test_un_valor_de_otro_campo_no_explica_este_campo(nuevo_arbol):
    arbol = nuevo_arbol(estado_general="Completa")
    crear_ayuda()
    crear_valor("estado_copa", "Completa", explicacion="Copa llena.")

    capsulas = armar_capsulas(arbol, AyudaCampo.objects.all(), ValorCatalogo.objects.all())

    assert capsulas[0]["en_este_arbol"] is None


# --- buscar_ficha -----------------------------------------------------------------------------


def test_la_ficha_sale_de_la_especie_del_arbol(nuevo_arbol):
    crear_ficha(beneficios="Da sombra\n\n  Atrae aves \n")
    arbol = nuevo_arbol(nombre_cientifico="  schinus   MOLLE")

    ficha = buscar_ficha(arbol)

    assert ficha == {
        "nombre_cientifico": "Schinus molle",
        "nombre_comun": "Molle",
        "beneficios": ["Da sombra", "Atrae aves"],
        "dato_curioso": None,
        "cuidados": None,
        "fuente": FUENTE_FICHA,
    }


def test_los_arboles_que_llegan_por_alias_tienen_la_ficha_de_su_especie(nuevo_arbol):
    crear_ficha("Prosopis pallida", alias="Algarrobo\nProsopis Pallida")
    por_nombre = nuevo_arbol(nombre_cientifico="Prosopis pallida")
    por_alias = nuevo_arbol("S01-A002", nombre_cientifico="prosopis  PALLIDA ")
    por_otro_alias = nuevo_arbol("S01-A003", nombre_cientifico="algarrobo")

    for arbol in (por_nombre, por_alias, por_otro_alias):
        assert buscar_ficha(arbol)["nombre_cientifico"] == "Prosopis pallida"


def test_una_ficha_sin_publicar_no_sale(sectores):
    crear_ficha(ficha_publicada=False)
    arbol = arbol_de_ejemplo(nombre_cientifico="Schinus molle")

    assert buscar_ficha(arbol) is None
    assert arbol_por_codigo("S01-A001").ficha_especie is None


def test_sin_especie_o_sin_ficha_no_hay_ficha(nuevo_arbol):
    crear_ficha()

    assert buscar_ficha(nuevo_arbol(nombre_cientifico=None)) is None
    assert buscar_ficha(nuevo_arbol("S01-A002", nombre_cientifico="Otra")) is None


# --- el selector de la cartilla ---------------------------------------------------------------


def test_la_cartilla_trae_capsulas_y_ficha_con_dos_consultas_extra(
    sectores, django_assert_max_num_queries
):
    crear_ficha()
    arbol_de_ejemplo(estado_general="Bueno", nombre_cientifico="Schinus molle")
    crear_ayuda()
    crear_valor()

    with django_assert_max_num_queries(1 + 2):
        cartilla = arbol_por_codigo("S01-A001")

    assert cartilla.capsulas[0]["en_este_arbol"] == EXPLICACION_BUENO
    assert cartilla.ficha_especie["nombre_comun"] == "Molle"


def test_la_cartilla_sin_ayudas_ni_fichas_trae_lista_vacia_y_null(sectores):
    arbol_de_ejemplo()

    cartilla = arbol_por_codigo("S01-A001")

    assert cartilla.capsulas == []
    assert cartilla.ficha_especie is None


def test_la_cartilla_no_muestra_ayudas_inactivas_ni_valores_inactivos(sectores):
    arbol_de_ejemplo(estado_general="Bueno")
    crear_ayuda(activo=False)
    crear_ayuda("estado_copa", titulo="Copa")
    crear_valor(activo=False)

    cartilla = arbol_por_codigo("S01-A001")

    assert [c["campo"] for c in cartilla.capsulas] == ["estado_copa"]


def test_un_codigo_inexistente_no_consulta_el_catalogo(sectores, django_assert_num_queries):
    with django_assert_num_queries(1):
        assert arbol_por_codigo("S01-Z999") is None


# --- control de los estados -------------------------------------------------------------------


def test_cuenta_los_arboles_vigentes_por_campo_y_valor(nuevo_arbol):
    nuevo_arbol("S01-A001", estado_general="Bueno")
    nuevo_arbol("S01-A002", estado_general="Bueno", estado_copa="Parcial")
    nuevo_arbol("S01-A003", estado_general="bueno")
    nuevo_arbol("S01-A004", estado_general="Bueno", **EN_LA_PAPELERA)

    conteo = conteo_de_valores_de_arboles()

    assert conteo[("estado_general", "Bueno")] == 2
    assert conteo[("estado_general", "bueno")] == 1
    assert conteo[("estado_copa", "Parcial")] == 1


def test_valores_fuera_del_catalogo_compara_exacto_y_omite_vacios_y_papelera(nuevo_arbol):
    nuevo_arbol("S01-A001", estado_general="Bueno")
    nuevo_arbol("S01-A002", estado_general="bueno")
    nuevo_arbol("S01-A003", estado_general="bueno", estado_copa="")
    nuevo_arbol("S01-A004", estado_general="  ", origen=None)
    nuevo_arbol("S01-A005", estado_general="bueno", **EN_LA_PAPELERA)
    crear_valor("estado_general", "Bueno")

    fuera = valores_fuera_del_catalogo()

    assert fuera == [{"campo": "estado_general", "valor": "bueno", "total_arboles": 2}]


def test_un_valor_inactivo_sigue_en_el_catalogo(nuevo_arbol):
    nuevo_arbol(estado_general="Bueno")
    crear_valor(activo=False)

    assert valores_fuera_del_catalogo() == []


# --- modelos ----------------------------------------------------------------------------------


def test_la_ayuda_solo_acepta_campos_de_las_constantes(db):
    ayuda = AyudaCampo(campo="inventado", titulo="X", que_es="Y")

    with pytest.raises(ValidationError) as error:
        ayuda.full_clean()

    assert "campo" in error.value.message_dict


def test_el_catalogo_solo_acepta_campos_catalogados_y_valores_unicos(db):
    with pytest.raises(ValidationError):
        ValorCatalogo(campo="codigo", valor="x", explicacion="y").full_clean()
    crear_valor()
    with pytest.raises(ValidationError):
        ValorCatalogo(campo="estado_general", valor="Bueno", explicacion="otra").full_clean()


def test_una_ficha_publicada_exige_fuente_beneficios_y_nombre_comun(db):
    completa = {
        "nombre_cientifico": "A",
        "nombre_comun": "B",
        "beneficios": "C",
        "fuente_ficha": FUENTE_FICHA,
        "ficha_publicada": True,
    }
    Especie(**completa).full_clean()
    for faltante in ({"fuente_ficha": ""}, {"beneficios": ""}, {"nombre_comun": None}):
        with pytest.raises(ValidationError) as error:
            Especie(**{**completa, **faltante}).full_clean()
        assert "ficha_publicada" in error.value.message_dict


def test_la_ficha_guarda_null_en_los_opcionales(db):
    especie = Especie(
        nombre_cientifico="A",
        nombre_comun="B",
        beneficios="C",
        fuente_ficha=FUENTE_FICHA,
        dato_curioso="",
        cuidados="  ",
    )
    especie.full_clean()
    especie.save()
    especie.refresh_from_db()
    assert (especie.dato_curioso, especie.cuidados, especie.ficha_publicada) == (None, None, False)


def test_los_cambios_de_las_tres_tablas_quedan_en_el_historial(db):
    ayuda = crear_ayuda()
    ayuda.titulo = "Otro título"
    ayuda.save()
    crear_valor()
    crear_ficha()

    assert ayuda.history.count() == 2
    assert ValorCatalogo.objects.get().history.count() == 1
    assert Especie.objects.get().history.count() == 1


# --- cargar_capsulas --------------------------------------------------------------------------


def test_carga_el_archivo_real_completo_y_las_fichas_quedan_sin_publicar(db):
    reporte = cargar_capsulas(RUTA_CAPSULAS)

    assert total_en_bd() == (18, 39, 3)
    assert (reporte.ayudas.creados, reporte.valores.creados, reporte.fichas.creados) == (18, 39, 3)
    assert set(AyudaCampo.objects.values_list("campo", flat=True)) == set(CAMPOS_CON_AYUDA)
    assert {v.campo for v in ValorCatalogo.objects.all()} <= set(CAMPOS_CATALOGADOS)
    assert not Especie.objects.filter(ficha_publicada=True).exists()
    assert not Especie.objects.filter(fuente_ficha="").exists()


def test_la_carga_es_idempotente(db):
    cargar_capsulas(RUTA_CAPSULAS)

    segunda = cargar_capsulas(RUTA_CAPSULAS)
    tercera = cargar_capsulas(RUTA_CAPSULAS, actualizar=True)

    assert total_en_bd() == (18, 39, 3)
    assert (segunda.ayudas.omitidos, segunda.valores.omitidos, segunda.fichas.omitidos) == (
        18,
        39,
        3,
    )
    assert tercera.ayudas.actualizados == tercera.valores.actualizados == 0
    assert tercera.fichas.actualizados == 0


def test_sin_actualizar_no_pisa_lo_editado_en_el_panel(db, tmp_path):
    ruta = escribir(
        tmp_path / "c.json",
        ayuda_campos=[ayuda_json()],
        valores=[valor_json()],
        fichas_especie=[ficha_json()],
    )
    cargar_capsulas(ruta)
    AyudaCampo.objects.update(que_es="Editado en el panel")
    ValorCatalogo.objects.update(explicacion="Editada en el panel")
    Especie.objects.update(nombre_comun="Editado", ficha_publicada=True)

    reporte = cargar_capsulas(ruta)

    assert AyudaCampo.objects.get().que_es == "Editado en el panel"
    assert ValorCatalogo.objects.get().explicacion == "Editada en el panel"
    assert Especie.objects.get().nombre_comun == "Editado"
    assert reporte.ayudas.omitidos == reporte.valores.omitidos == reporte.fichas.omitidos == 1


def test_con_actualizar_sobrescribe_los_textos_pero_conserva_publicada(db, tmp_path):
    ruta = escribir(
        tmp_path / "c.json",
        ayuda_campos=[ayuda_json()],
        valores=[valor_json()],
        fichas_especie=[ficha_json(publicada=False)],
    )
    cargar_capsulas(ruta)
    AyudaCampo.objects.update(que_es="Editado en el panel", activo=False)
    ValorCatalogo.objects.update(explicacion="Editada en el panel")
    Especie.objects.update(nombre_comun="Editado", ficha_publicada=True)

    reporte = cargar_capsulas(ruta, actualizar=True)

    assert AyudaCampo.objects.get().que_es == "Cómo se ve."
    assert ValorCatalogo.objects.get().explicacion == "Sano."
    especie = Especie.objects.get()
    assert (especie.nombre_comun, especie.ficha_publicada) == ("Molle", True)
    assert reporte.ayudas.actualizados == reporte.valores.actualizados == 1
    assert reporte.fichas.actualizados == 1


def test_un_registro_malo_rechaza_el_archivo_entero_con_todos_los_errores(db, tmp_path):
    ruta = escribir(
        tmp_path / "malo.json",
        ayuda_campos=[ayuda_json(), ayuda_json("inventado"), ayuda_json()],
        valores=[valor_json(), valor_json(campo="codigo"), valor_json(valor=" BUENO ")],
        fichas_especie=[ficha_json(), ficha_json(nombre_cientifico="Otra", fuente="  ")],
    )

    with pytest.raises(ValueError) as error:
        cargar_capsulas(ruta)

    mensaje = str(error.value)
    for pista in ("inventado", "codigo", "fuente", "repetid"):
        assert pista in mensaje
    assert total_en_bd() == (0, 0, 0)


@pytest.mark.parametrize(
    "contenido",
    [
        "no es json",
        json.dumps({"ayuda_campos": [], "valores": []}),
        json.dumps({"ayuda_campos": {}, "valores": [], "fichas_especie": []}),
        json.dumps({"ayuda_campos": [ayuda_json(extra=1)], "valores": [], "fichas_especie": []}),
    ],
)
def test_un_archivo_mal_formado_se_rechaza(db, tmp_path, contenido):
    ruta = tmp_path / "x.json"
    ruta.write_text(contenido, encoding="utf-8")

    with pytest.raises(ValueError):
        cargar_capsulas(ruta)

    assert total_en_bd() == (0, 0, 0)


def test_un_archivo_inexistente_se_rechaza(db, tmp_path):
    with pytest.raises(ValueError):
        cargar_capsulas(tmp_path / "no-existe.json")


def test_el_comando_cuenta_lo_que_creo_actualizo_y_omitio(db):
    salida = StringIO()
    call_command("cargar_capsulas", str(RUTA_CAPSULAS), stdout=salida)
    segunda = StringIO()
    call_command("cargar_capsulas", str(RUTA_CAPSULAS), "--actualizar", stdout=segunda)

    assert "Ayudas: 18 creadas, 0 actualizadas, 0 omitidas" in salida.getvalue()
    assert "Valores del catálogo: 39 creados, 0 actualizados, 0 omitidos" in salida.getvalue()
    assert "Fichas de especie: 3 creadas, 0 actualizadas, 0 omitidas" in salida.getvalue()
    assert "Ayudas: 0 creadas, 0 actualizadas, 18 omitidas" in segunda.getvalue()


def test_el_comando_falla_con_mensaje_si_el_archivo_no_sirve(db, tmp_path):
    with pytest.raises(CommandError, match="No se pudo leer"):
        call_command("cargar_capsulas", str(tmp_path / "no-existe.json"))


# --- permisos por rol -------------------------------------------------------------------------


def permisos_del_grupo(nombre):
    return set(Group.objects.get(name=nombre).permissions.values_list("codename", flat=True))


def test_el_editor_no_borra_y_el_administrador_si(db):
    editor = permisos_del_grupo(NOMBRE_ROL_EDITOR)
    administrador = permisos_del_grupo(NOMBRE_ROL_ADMINISTRADOR)

    for modelo in MODELOS_DE_CAPSULAS:
        sin_borrar = {f"add_{modelo}", f"change_{modelo}", f"view_{modelo}"}
        assert sin_borrar <= editor
        assert f"delete_{modelo}" not in editor
        assert sin_borrar | {f"delete_{modelo}"} <= administrador


def test_la_migracion_de_permisos_se_repite_sin_duplicar_y_conserva_los_previos(db):
    sumar = importlib.import_module(MIGRACION_DE_CAPSULAS).sumar_permisos_de_capsulas
    importlib.import_module(MIGRACION_DE_ROLES).crear_grupos(registro_de_apps, None)
    assert permisos_del_grupo(NOMBRE_ROL_EDITOR) == set(PERMISOS_POR_ROL[NOMBRE_ROL_EDITOR])

    sumar(registro_de_apps, None)
    sumar(registro_de_apps, None)

    for nombre in (NOMBRE_ROL_ADMINISTRADOR, NOMBRE_ROL_EDITOR):
        esperados = set(PERMISOS_POR_ROL[nombre]) | set(PERMISOS_CAPSULAS_POR_ROL[nombre])
        assert permisos_del_grupo(nombre) == esperados
        assert Group.objects.get(name=nombre).permissions.count() == len(esperados)


def test_una_ficha_cuyo_alias_ya_es_de_otra_especie_no_se_guarda(db, tmp_path):
    crear_ficha("Roystonea regia", nombre_comun="Palma real", alias="Pimiento")
    ruta = escribir(
        tmp_path / "c.json",
        ayuda_campos=[],
        valores=[],
        fichas_especie=[ficha_json(alias=["pimiento"])],
    )

    with pytest.raises(ValueError, match="Pimiento|pimiento"):
        cargar_capsulas(ruta)

    assert Especie.objects.count() == 1
