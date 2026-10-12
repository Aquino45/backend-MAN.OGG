"""Tests de la identidad del panel (Unfold + hoja propia) y de que las pantallas siguen vivas."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.contrib.staticfiles import finders
from django.urls import reverse

from apps.censo.models import Arbol
from apps.censo.servicios.papelera import mover_a_papelera
from config.constantes import (
    CAMPO_MOTIVO_ELIMINACION,
    FAVICON_ADMIN,
    HOJA_COMPONENTES_ADMIN,
    HOJA_IDENTIDAD_ADMIN,
    LOGO_ADMIN,
    NOMBRE_PUBLICO_ADMIN,
    PESOS_ESCALA_COLOR_ADMIN,
    VARIANTES_CHIP,
)
from tests.censo.ayuda_css import (
    COLOR_HEX,
    bloques,
    color_de,
    contraste,
    sin_comentarios,
    variables_del_tema,
)
from tests.censo.conftest import CLAVE_PRUEBA, arbol_de_ejemplo, cliente_de
from tests.censo.test_admin import datos_de_alta
from tests.censo.test_carga_planilla import lote_mixto, punto  # noqa: F401
from tests.censo.test_panel_geometrias import configuracion_del_mapa

PALETA = {
    "#e02040",
    "#c00080",
    "#a00080",
    "#202040",
    "#413e59",
    "#f6eef2",
    "#2b2a52",
    "#d9cfe3",
    "#e7dcee",
    "#ffffff",
    "#ffd166",
}
TOKENS_DEL_FRONT = Path(r"D:\MAN.OGG\frontend-MAN.OGG\src\styles\tokens.css")
MINIMO_AA = 4.5
VARIABLES_DEL_MAPA = {"--body-bg", "--body-fg", "--error-fg"}
PARES_CLARO = [
    ("--marca-base-600", "--marca-base-50"),
    ("--marca-base-900", "--marca-base-50"),
    ("--marca-base-500", "--marca-base-50"),
    ("--marca-primario-600", "--marca-base-50"),
    ("--blanco", "--marca-primario-600"),
    ("--blanco", "--marca-primario-700"),
    ("--marca-base-600", "--blanco"),
    ("--marca-primario-700", "--marca-primario-100"),
    ("--body-fg", "--body-bg"),
    ("--error-fg", "--body-bg"),
]
PARES_OSCURO = [
    ("--marca-base-300", "--marca-base-900"),
    ("--marca-base-100", "--marca-base-900"),
    ("--marca-base-400", "--marca-base-900"),
    ("--marca-primario-500", "--marca-base-900"),
    ("--marca-base-300", "--marca-base-800"),
    ("--blanco", "--marca-primario-600"),
    ("--marca-primario-300", "--marca-base-800"),
    ("--body-fg", "--body-bg"),
    ("--error-fg", "--body-bg"),
]
PARES_DE_CHIPS = [(f"--chip-{v}-fg", f"--chip-{v}-bg") for v in VARIANTES_CHIP]


def texto_de_la_hoja(hoja=HOJA_IDENTIDAD_ADMIN):
    ruta = finders.find(hoja)
    assert ruta, f"{hoja} no se sirve por staticfiles"
    return Path(ruta).read_text(encoding="utf8")


# --- identidad ---------------------------------------------------------------------------------


def test_el_panel_carga_con_la_hoja_el_logo_y_el_favicon(cliente_administrador):
    html = cliente_administrador.get(reverse("admin:index")).content.decode()

    assert HOJA_IDENTIDAD_ADMIN in html and HOJA_COMPONENTES_ADMIN in html
    assert LOGO_ADMIN in html
    assert FAVICON_ADMIN in html
    assert NOMBRE_PUBLICO_ADMIN in html


def test_el_acceso_al_panel_tambien_trae_la_hoja_y_el_favicon(client):
    html = client.get(reverse("admin:login")).content.decode()

    assert HOJA_IDENTIDAD_ADMIN in html and FAVICON_ADMIN in html


def test_la_marca_y_la_fuente_se_sirven_desde_el_back():
    for ruta in (LOGO_ADMIN, FAVICON_ADMIN, "admin/censo/fuentes/OFL.txt"):
        assert finders.find(ruta), ruta
    for peso in (400, 600, 800):
        nombre = f"bricolage-grotesque-latin-{peso}-normal.woff2"
        assert finders.find(f"admin/censo/fuentes/{nombre}")
        assert nombre in texto_de_la_hoja()


def test_los_colores_viven_solo_en_el_unico_bloque_root():
    texto = sin_comentarios(texto_de_la_hoja())
    selector, declaraciones = bloques(texto)[0]
    en_el_bloque = " ".join(declaraciones.values())
    resto = texto[texto.index("}") + 1 :]

    assert selector == ":root"
    assert [s for s, _ in bloques(texto) if s == ":root"] == [":root"]
    assert not COLOR_HEX.findall(sin_comentarios(texto_de_la_hoja(HOJA_COMPONENTES_ADMIN)))
    assert set(COLOR_HEX.findall(en_el_bloque.lower())) <= PALETA
    assert not COLOR_HEX.findall(resto)
    assert "misma paleta que el sitio público" in texto_de_la_hoja()


@pytest.mark.skipif(not TOKENS_DEL_FRONT.exists(), reason="el front no está junto a este repo")
def test_la_paleta_coincide_con_los_tokens_del_front():
    tokens = TOKENS_DEL_FRONT.read_text(encoding="utf8").lower()
    primero = bloques(texto_de_la_hoja())[0][1]

    for valor in COLOR_HEX.findall(" ".join(primero.values()).lower()):
        assert valor in tokens


def test_la_hoja_define_las_variables_del_mapa_y_no_toca_sus_clases():
    texto = texto_de_la_hoja()
    for tema in ("claro", "oscuro"):
        assert VARIABLES_DEL_MAPA <= set(variables_del_tema(texto, tema))
    assert not re.search(r"\.dj_map|\.mapa-", sin_comentarios(texto))


def test_las_escalas_de_unfold_apuntan_a_variables_de_la_hoja():
    texto = texto_de_la_hoja()
    colores = settings.UNFOLD["COLORS"]
    definidas = set(variables_del_tema(texto, "claro"))

    for escala in ("base", "primary"):
        assert [int(peso) for peso in colores[escala]] == list(PESOS_ESCALA_COLOR_ADMIN)
        for valor in colores[escala].values():
            assert re.fullmatch(r"var\((--[\w-]+)\)", valor).group(1) in definidas


@pytest.mark.parametrize(("tema", "pares"), [("claro", PARES_CLARO), ("oscuro", PARES_OSCURO)])
def test_el_texto_y_los_chips_cumplen_el_contraste_aa(tema, pares):
    variables = variables_del_tema(texto_de_la_hoja(), tema)

    fallas = []
    for texto, fondo in [*pares, *PARES_DE_CHIPS]:
        razon = contraste(color_de(texto, variables), color_de(fondo, variables))
        if razon < MINIMO_AA:
            fallas.append((texto, fondo, round(razon, 2)))
    assert not fallas


# --- el mapa, la carga, la papelera, el historial -----------------------------------------------


def test_los_formularios_con_mapa_responden_200_con_el_widget(cliente_administrador, sectores):
    arbol = arbol_de_ejemplo("S01-A001")
    rutas = [
        reverse("admin:censo_arbol_change", args=[arbol.pk]),
        reverse("admin:censo_arbol_add"),
        reverse("admin:censo_sector_change", args=[1]),
    ]

    for ruta in rutas:
        respuesta = cliente_administrador.get(ruta)
        assert respuesta.status_code == 200, ruta
        assert "dj_map" in respuesta.content.decode(), ruta


@pytest.mark.parametrize("nombre", ["subir", "resumen", "revisar"])
def test_las_pantallas_de_carga_responden_200(nombre, lote_mixto, cliente_administrador):  # noqa: F811
    if nombre == "subir":
        ruta = reverse("admin:censo_lotecarga_changelist")
    else:
        ruta = reverse(f"admin:censo_lotecarga_{nombre}", args=[lote_mixto.pk])

    assert cliente_administrador.get(ruta).status_code == 200


def test_el_resultado_de_la_carga_responde_200(lote_mixto, cliente_administrador):  # noqa: F811
    cliente_administrador.post(reverse("admin:censo_lotecarga_confirmar", args=[lote_mixto.pk]))

    ruta = reverse("admin:censo_lotecarga_resultado", args=[lote_mixto.pk])
    assert cliente_administrador.get(ruta).status_code == 200


def test_la_papelera_pide_el_motivo_manda_y_restaura(cliente_administrador, sectores):
    arbol = arbol_de_ejemplo("S01-A001")

    pantalla = cliente_administrador.get(reverse("admin:censo_arbol_delete", args=[arbol.pk]))
    assert pantalla.status_code == 200
    assert f'name="{CAMPO_MOTIVO_ELIMINACION}"' in pantalla.content.decode()

    cliente_administrador.post(
        reverse("admin:censo_arbol_delete", args=[arbol.pk]),
        {"post": "yes", CAMPO_MOTIVO_ELIMINACION: "Duplicado"},
    )
    assert Arbol.todos.get(pk=arbol.pk).eliminado_en is not None

    cliente_administrador.post(
        reverse("admin:censo_arbolenpapelera_changelist"),
        {"action": "restaurar", "_selected_action": [arbol.pk]},
    )
    assert Arbol.todos.get(pk=arbol.pk).eliminado_en is None


def test_el_historial_y_la_vuelta_a_una_version_responden_200(cliente_administrador, sectores):
    arbol = arbol_de_ejemplo("S01-A001")
    arbol.observaciones = "Cambio"
    arbol.save()
    version = arbol.history.last()

    historial = reverse("admin:censo_arbol_history", args=[arbol.pk])
    revertir = reverse("admin:censo_arbol_simple_history", args=[arbol.pk, version.pk])

    assert cliente_administrador.get(historial).status_code == 200
    assert cliente_administrador.get(revertir).status_code == 200


def test_los_botones_de_la_carga_llevan_las_clases_de_boton(cliente_administrador):
    html = cliente_administrador.get(reverse("admin:censo_lotecarga_changelist")).content.decode()

    assert "carga-planilla" in html
    boton = re.search(r'<input type="submit"[^>]*>', html).group(0)
    assert 'class="button default"' in boton


@pytest.mark.parametrize("nombre", ["resumen", "revisar", "no"])
def test_las_pantallas_de_un_lote_real_estan_dentro_de_la_carga_con_botones(
    nombre,
    lote_mixto,  # noqa: F811
    cliente_administrador,
):
    html = cliente_administrador.get(
        reverse(f"admin:censo_lotecarga_{nombre}", args=[lote_mixto.pk])
    ).content.decode()

    assert "carga-planilla" in html
    assert re.search(r'class="button[^"]*"', html)


def test_el_formulario_del_arbol_trae_las_coordenadas_iniciales_y_el_js_del_mapa(
    cliente_administrador, sectores
):
    arbol = arbol_de_ejemplo("S01-A001")

    respuesta = cliente_administrador.get(reverse("admin:censo_arbol_change", args=[arbol.pk]))

    formulario = respuesta.context["adminform"].form
    assert float(formulario.initial["utm_este_m"]) == pytest.approx(arbol.ubicacion.x, abs=0.01)
    assert float(formulario.initial["utm_norte_m"]) == pytest.approx(arbol.ubicacion.y, abs=0.01)
    assert configuracion_del_mapa(respuesta)["capas"]
    assert "ol.layer.Tile" in respuesta.content.decode()


def test_el_historial_revierte_de_verdad_el_valor(cliente_administrador, sectores):
    arbol = arbol_de_ejemplo("S01-A010", observaciones="Molle")
    arbol.observaciones = "Palma real"
    arbol.save()
    version = arbol.history.filter(observaciones="Molle").get()
    ruta = reverse("admin:censo_arbol_simple_history", args=[arbol.pk, version.pk])

    respuesta = cliente_administrador.post(ruta, datos_de_alta(observaciones="Molle"))

    assert respuesta.status_code == 302
    assert Arbol.objects.get(pk=arbol.pk).observaciones == "Molle"


def test_el_editor_no_ve_ni_hace_lo_que_no_le_toca(cliente_editor, sectores):
    arbol = arbol_de_ejemplo("S01-A001")
    mover_a_papelera(arbol, User.objects.create(username="otra-persona"), "Duplicado")

    lista = cliente_editor.get(reverse("admin:censo_arbolenpapelera_changelist"))
    acciones = lista.context["cl"].model_admin.get_actions(lista.wsgi_request)

    assert "delete_selected" not in acciones and "restaurar" in acciones
    borrar = reverse("admin:censo_arbolenpapelera_delete", args=[arbol.pk])
    assert cliente_editor.post(borrar, {"post": "yes"}).status_code == 403
    assert cliente_editor.get(reverse("admin:censo_sector_add")).status_code == 403
    assert Arbol.todos.filter(pk=arbol.pk).exists()


def test_sin_el_permiso_de_cargar_el_indice_no_enlaza_la_carga_y_la_url_da_403(db, sectores):
    usuario = User.objects.create_user("sin-carga", password=CLAVE_PRUEBA, is_staff=True)
    usuario.user_permissions.add(Permission.objects.get(codename="view_arbol"))
    cliente = cliente_de(usuario)
    carga = reverse("admin:censo_lotecarga_changelist")

    indice = cliente.get(reverse("admin:index")).content.decode()

    assert carga not in indice
    assert cliente.get(carga).status_code == 403
    assert cliente.get(reverse("admin:censo_arbol_changelist")).status_code == 200
