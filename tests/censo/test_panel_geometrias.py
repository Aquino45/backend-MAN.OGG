"""Tests del mapa editable del panel: capas, coordenadas, pin, marca de ubicación y endpoints."""

import json
import re

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.gis.geos import Point
from django.test import Client
from django.test.utils import override_settings
from django.urls import reverse

import config.constantes.mapa as constantes_mapa
from apps.censo.admin_geometrias import MapaEditable
from apps.censo.models import Arbol, Sector
from apps.censo.servicios import geometrias
from config.constantes.calidad import ESTADO_REGISTRO_EN_REVISION, ESTADO_REGISTRO_PUBLICADO
from config.constantes.general import SRID_MAPA, SRID_UTM_CENSO
from tests.censo.conftest import FUENTE_PANEL, arbol_evaluado, cliente_de
from tests.censo.test_admin import formulario_completo, mensajes

CLAVE_FALSA_DE_ESRI = "clave-falsa-de-esri-123"
SRID_DEL_WIDGET = 3857
DESPLAZAMIENTO_M = 6


def datos_del_arbol(codigo="S01-A001", **extra):
    """El formulario de un árbol completo (menos la ubicación) tal como lo manda el panel."""
    datos = {"codigo": codigo, "sector": 1, "fuente": FUENTE_PANEL, **formulario_completo()}
    datos.update(extra)
    return datos


def punto_utm(este, norte):
    return Point(este, norte, srid=SRID_UTM_CENSO)


def en_el_widget(punto):
    """La ubicación como la manda el widget: GeoJSON en el SRID del mapa."""
    return punto.transform(SRID_DEL_WIDGET, clone=True).json


def configuracion_del_mapa(respuesta):
    """El JSON de configuración que el widget deja en la página."""
    encontrado = re.search(
        r'<script id="[^"]*_configuracion" type="application/json">(.*?)</script>',
        respuesta.content.decode(),
        re.DOTALL,
    )
    assert encontrado, "la página no trae la configuración del mapa"
    return json.loads(encontrado.group(1))


@pytest.fixture
def arbol(sectores):
    return arbol_evaluado("S01-A001")


def ruta_de_cambio(arbol):
    return reverse("admin:censo_arbol_change", args=[arbol.pk])


def ubicacion_en_api(cliente_api, codigo):
    cuerpo = cliente_api.get(reverse("arbol", kwargs={"codigo": codigo})).json()
    return cuerpo["utm_este_m"], cuerpo["utm_norte_m"]


# --- el widget y las capas ---------------------------------------------------------------------


def test_el_campo_ubicacion_usa_el_widget_del_mapa_editable(cliente_editor, arbol):
    formulario = cliente_editor.get(ruta_de_cambio(arbol)).context["adminform"].form

    widget = formulario.fields["ubicacion"].widget
    assert isinstance(widget, MapaEditable)
    assert widget.attrs["default_lon"] == constantes_mapa.MAPA_ADMIN_LON
    assert widget.attrs["default_lat"] == constantes_mapa.MAPA_ADMIN_LAT
    assert widget.attrs["default_zoom"] == constantes_mapa.MAPA_ADMIN_ZOOM


@override_settings(ESRI_CLAVE="")
def test_sin_clave_de_esri_la_unica_capa_es_openstreetmap_con_su_atribucion(cliente_editor, arbol):
    respuesta = cliente_editor.get(ruta_de_cambio(arbol))

    configuracion = configuracion_del_mapa(respuesta)
    assert [capa["id"] for capa in configuracion["capas"]] == ["calles"]
    assert configuracion["capa_inicial"] == "calles"
    assert "openstreetmap.org" in configuracion["capas"][0]["url"]
    assert "OpenStreetMap" in configuracion["capas"][0]["atribucion"]
    assert "arcgis" not in respuesta.content.decode().lower()


@override_settings(ESRI_CLAVE=CLAVE_FALSA_DE_ESRI)
def test_con_clave_de_esri_la_capa_inicial_es_satelital_con_la_atribucion_de_esri(
    cliente_editor, arbol
):
    configuracion = configuracion_del_mapa(cliente_editor.get(ruta_de_cambio(arbol)))

    satelite, calles = configuracion["capas"]
    assert (satelite["id"], calles["id"]) == ("satelite", "calles")
    assert configuracion["capa_inicial"] == "satelite"
    assert satelite["url"].startswith(
        "https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/"
    )
    assert "{z}/{y}/{x}" in satelite["url"]
    assert satelite["url"].endswith(f"token={CLAVE_FALSA_DE_ESRI}")
    assert "Esri" in satelite["atribucion"] and "Maxar" in satelite["atribucion"]
    assert "ExportTiles" not in satelite["url"]


@override_settings(ESRI_CLAVE=CLAVE_FALSA_DE_ESRI)
def test_el_widget_trae_el_selector_de_capas_y_la_atribucion_visible(cliente_editor, arbol):
    contenido = cliente_editor.get(ruta_de_cambio(arbol)).content.decode()

    assert "Satélite" in contenido and "Calles" in contenido
    assert 'class="mapa-atribucion"' in contenido
    assert "ol.layer.Tile" in contenido


def test_la_clave_de_esri_es_opcional_y_viene_del_entorno(settings):
    assert isinstance(settings.ESRI_CLAVE, str)


# --- los campos de coordenadas -----------------------------------------------------------------


def test_el_formulario_muestra_utm_editable_y_grados_de_solo_lectura(cliente_editor, arbol):
    formulario = cliente_editor.get(ruta_de_cambio(arbol)).context["adminform"].form

    este, norte = arbol.ubicacion.x, arbol.ubicacion.y
    latitud, longitud = geometrias.utm_a_grados(este, norte)
    assert float(formulario.initial["utm_este_m"]) == pytest.approx(este, abs=0.01)
    assert float(formulario.initial["utm_norte_m"]) == pytest.approx(norte, abs=0.01)
    assert float(formulario.initial["latitud"]) == pytest.approx(latitud, abs=1e-6)
    assert float(formulario.initial["longitud"]) == pytest.approx(longitud, abs=1e-6)
    assert formulario.fields["utm_este_m"].label == "UTM Este (m)"
    assert formulario.fields["utm_norte_m"].label == "UTM Norte (m)"
    assert not formulario.fields["utm_este_m"].disabled
    assert formulario.fields["latitud"].disabled and formulario.fields["longitud"].disabled


def test_el_alta_trae_los_campos_de_coordenadas_vacios(cliente_editor, sectores):
    formulario = cliente_editor.get(reverse("admin:censo_arbol_add")).context["adminform"].form

    assert not formulario.initial.get("utm_este_m")
    assert "utm_norte_m" in formulario.fields and "latitud" in formulario.fields


def test_los_grados_que_llegan_en_el_formulario_se_ignoran(cliente_editor, arbol, cliente_api):
    este, norte = arbol.ubicacion.x, arbol.ubicacion.y
    datos = datos_del_arbol(latitud="1", longitud="2", utm_este_m=f"{este + DESPLAZAMIENTO_M:.2f}")
    datos["utm_norte_m"] = f"{norte:.2f}"

    cliente_editor.post(ruta_de_cambio(arbol), datos)

    assert ubicacion_en_api(cliente_api, "S01-A001") == pytest.approx(
        (este + DESPLAZAMIENTO_M, norte), abs=0.01
    )


# --- guardar una ubicación nueva ---------------------------------------------------------------


def test_escribir_las_utm_mueve_el_arbol_y_la_api_devuelve_la_nueva_ubicacion(
    cliente_editor, arbol, cliente_api
):
    este, norte = arbol.ubicacion.x, arbol.ubicacion.y
    datos = datos_del_arbol(utm_este_m=f"{este + DESPLAZAMIENTO_M:.2f}", utm_norte_m=f"{norte:.2f}")

    cliente_editor.post(ruta_de_cambio(arbol), datos)

    arbol.refresh_from_db()
    assert (arbol.ubicacion.x, arbol.ubicacion.y) == pytest.approx(
        (este + DESPLAZAMIENTO_M, norte), abs=0.01
    )
    assert ubicacion_en_api(cliente_api, "S01-A001") == pytest.approx(
        (este + DESPLAZAMIENTO_M, norte), abs=0.01
    )


def test_mover_el_pin_guarda_la_ubicacion_que_manda_el_widget(cliente_editor, arbol):
    nueva = punto_utm(arbol.ubicacion.x + DESPLAZAMIENTO_M, arbol.ubicacion.y)

    cliente_editor.post(ruta_de_cambio(arbol), datos_del_arbol(ubicacion=en_el_widget(nueva)))

    arbol.refresh_from_db()
    assert arbol.ubicacion.srid == SRID_UTM_CENSO
    assert (arbol.ubicacion.x, arbol.ubicacion.y) == pytest.approx((nueva.x, nueva.y), abs=0.001)


def test_cambiar_la_ubicacion_marca_el_arbol_y_guarda_la_fecha(cliente_editor, arbol):
    nueva = punto_utm(arbol.ubicacion.x + DESPLAZAMIENTO_M, arbol.ubicacion.y)
    assert arbol.ubicacion_editada_en_panel is False

    cliente_editor.post(ruta_de_cambio(arbol), datos_del_arbol(ubicacion=en_el_widget(nueva)))

    arbol.refresh_from_db()
    assert arbol.ubicacion_editada_en_panel is True
    assert arbol.fecha_ubicacion_editada is not None


def test_guardar_sin_tocar_la_ubicacion_no_pone_la_marca(cliente_editor, arbol):
    datos = datos_del_arbol(ubicacion=en_el_widget(arbol.ubicacion), observaciones="Otra nota")

    cliente_editor.post(ruta_de_cambio(arbol), datos)

    arbol.refresh_from_db()
    assert arbol.observaciones == "Otra nota"
    assert arbol.ubicacion_editada_en_panel is False
    assert arbol.fecha_ubicacion_editada is None


def test_guardar_con_las_utm_de_siempre_tampoco_pone_la_marca(cliente_editor, arbol):
    datos = datos_del_arbol(
        utm_este_m=f"{arbol.ubicacion.x:.2f}", utm_norte_m=f"{arbol.ubicacion.y:.2f}"
    )

    cliente_editor.post(ruta_de_cambio(arbol), datos)

    arbol.refresh_from_db()
    assert arbol.ubicacion_editada_en_panel is False


def test_el_historial_guarda_el_cambio_de_ubicacion(cliente_editor, arbol):
    antes = arbol.history.count()
    nueva = punto_utm(arbol.ubicacion.x + DESPLAZAMIENTO_M, arbol.ubicacion.y)

    cliente_editor.post(ruta_de_cambio(arbol), datos_del_arbol(ubicacion=en_el_widget(nueva)))

    ultima = arbol.history.first()
    assert arbol.history.count() == antes + 1
    assert (ultima.ubicacion.x, ultima.ubicacion.y) == pytest.approx((nueva.x, nueva.y), abs=0.001)
    assert ultima.ubicacion_editada_en_panel is True


def test_mover_un_arbol_fuera_de_su_sector_lo_manda_a_revision_con_el_motivo(
    cliente_editor, arbol, cliente_api
):
    lejos = Sector.objects.get(id=2).geom.point_on_surface
    assert arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO

    respuesta = cliente_editor.post(
        ruta_de_cambio(arbol),
        datos_del_arbol(utm_este_m=f"{lejos.x:.2f}", utm_norte_m=f"{lejos.y:.2f}"),
        follow=True,
    )

    arbol.refresh_from_db()
    assert arbol.estado_registro == ESTADO_REGISTRO_EN_REVISION
    assert "La ubicación cae a" in arbol.motivos_revision
    assert cliente_api.get(reverse("arbol", kwargs={"codigo": "S01-A001"})).status_code == 404
    assert any("quedó en revisión" in mensaje for mensaje in mensajes(respuesta))


def test_el_mensaje_dice_en_que_sector_cae_el_punto(cliente_editor, arbol):
    nueva = punto_utm(arbol.ubicacion.x + DESPLAZAMIENTO_M, arbol.ubicacion.y)

    respuesta = cliente_editor.post(
        ruta_de_cambio(arbol), datos_del_arbol(ubicacion=en_el_widget(nueva)), follow=True
    )

    assert any("cae en el sector 1" in mensaje for mensaje in mensajes(respuesta))


def test_si_cae_en_otro_sector_el_mensaje_lo_dice_y_el_sector_del_arbol_no_cambia(
    cliente_editor, arbol
):
    lejos = Sector.objects.get(id=2).geom.point_on_surface

    respuesta = cliente_editor.post(
        ruta_de_cambio(arbol),
        datos_del_arbol(utm_este_m=f"{lejos.x:.2f}", utm_norte_m=f"{lejos.y:.2f}"),
        follow=True,
    )

    arbol.refresh_from_db()
    assert arbol.sector_id == 1
    assert any(
        "cae en el sector 2" in m and "sigue registrado en el sector 1" in m
        for m in mensajes(respuesta)
    )


# --- dentro del campus -------------------------------------------------------------------------


def test_unas_coordenadas_fuera_del_campus_se_rechazan_con_un_mensaje(
    cliente_editor, arbol, cliente_api
):
    este, norte = arbol.ubicacion.x, arbol.ubicacion.y
    datos = datos_del_arbol(utm_este_m=f"{este + 20000:.2f}", utm_norte_m=f"{norte:.2f}")

    respuesta = cliente_editor.post(ruta_de_cambio(arbol), datos)

    assert respuesta.status_code == 200
    assert "La ubicación está fuera del campus" in respuesta.content.decode()
    arbol.refresh_from_db()
    assert arbol.ubicacion.x == pytest.approx(este)


def test_un_pin_fuera_del_campus_tambien_se_rechaza(cliente_editor, arbol):
    lejos = punto_utm(arbol.ubicacion.x + 20000, arbol.ubicacion.y)

    respuesta = cliente_editor.post(
        ruta_de_cambio(arbol), datos_del_arbol(ubicacion=en_el_widget(lejos))
    )

    assert "La ubicación está fuera del campus" in respuesta.content.decode()


def test_pedir_solo_el_este_o_solo_el_norte_se_rechaza(cliente_editor, arbol):
    respuesta = cliente_editor.post(
        ruta_de_cambio(arbol), datos_del_arbol(utm_este_m="299500", utm_norte_m="")
    )

    assert "Escribe el UTM Este y el UTM Norte" in respuesta.content.decode()


def test_un_arbol_que_ya_estaba_fuera_del_campus_puede_guardar_otros_cambios(
    cliente_editor, sectores
):
    lejos = punto_utm(299_000 + 90_000, 8_673_000)
    arbol = arbol_evaluado("S01-A001", ubicacion=lejos)
    datos = datos_del_arbol(ubicacion=en_el_widget(lejos), observaciones="Solo la nota")

    cliente_editor.post(ruta_de_cambio(arbol), datos)

    arbol.refresh_from_db()
    assert arbol.observaciones == "Solo la nota"


# --- árbol nuevo por pin -----------------------------------------------------------------------


def test_el_alta_por_pin_guarda_el_arbol_con_la_ubicacion_y_la_marca(
    cliente_editor, sectores, cliente_api
):
    punto = Sector.objects.get(id=1).geom.point_on_surface

    cliente_editor.post(
        reverse("admin:censo_arbol_add"),
        datos_del_arbol("S01-A010", ubicacion=en_el_widget(punto)),
    )

    nuevo = Arbol.objects.get(codigo="S01-A010")
    assert (nuevo.ubicacion.x, nuevo.ubicacion.y) == pytest.approx((punto.x, punto.y), abs=0.001)
    assert nuevo.ubicacion_editada_en_panel is True
    assert nuevo.estado_registro in (ESTADO_REGISTRO_PUBLICADO, ESTADO_REGISTRO_EN_REVISION)


def test_el_alta_por_coordenadas_incompleta_queda_en_revision_con_el_motivo(
    cliente_editor, sectores
):
    punto = Sector.objects.get(id=1).geom.point_on_surface
    datos = {
        "codigo": "S01-A010",
        "sector": 1,
        "fuente": FUENTE_PANEL,
        "utm_este_m": f"{punto.x:.2f}",
        "utm_norte_m": f"{punto.y:.2f}",
    }

    cliente_editor.post(reverse("admin:censo_arbol_add"), datos)

    nuevo = Arbol.objects.get(codigo="S01-A010")
    assert nuevo.estado_registro == ESTADO_REGISTRO_EN_REVISION
    assert "Falta el dato" in nuevo.motivos_revision
    assert "Falta el dato «Ubicación»" not in nuevo.motivos_revision


# --- la marca: quién la edita ------------------------------------------------------------------


def test_la_casilla_de_la_marca_es_editable_solo_para_el_administrador(
    cliente_administrador, cliente_editor, arbol
):
    del_administrador = cliente_administrador.get(ruta_de_cambio(arbol)).context["adminform"].form
    del_editor = cliente_editor.get(ruta_de_cambio(arbol)).context["adminform"].form

    assert "ubicacion_editada_en_panel" in del_administrador.fields
    assert "ubicacion_editada_en_panel" not in del_editor.fields


def test_el_editor_no_puede_quitar_la_marca(cliente_editor, arbol):
    Arbol.todos.filter(pk=arbol.pk).update(ubicacion_editada_en_panel=True)
    datos = datos_del_arbol(ubicacion=en_el_widget(arbol.ubicacion))

    cliente_editor.post(ruta_de_cambio(arbol), datos)

    arbol.refresh_from_db()
    assert arbol.ubicacion_editada_en_panel is True


def test_el_administrador_quita_la_marca_desde_el_panel(cliente_administrador, arbol):
    Arbol.todos.filter(pk=arbol.pk).update(ubicacion_editada_en_panel=True)
    datos = datos_del_arbol(ubicacion=en_el_widget(arbol.ubicacion), demo="")

    cliente_administrador.post(ruta_de_cambio(arbol), datos)

    arbol.refresh_from_db()
    assert arbol.ubicacion_editada_en_panel is False


def test_el_administrador_que_mueve_el_pin_con_la_casilla_marcada_la_conserva(
    cliente_administrador, arbol
):
    nueva = punto_utm(arbol.ubicacion.x + DESPLAZAMIENTO_M, arbol.ubicacion.y)
    datos = datos_del_arbol(ubicacion=en_el_widget(nueva), demo="")

    cliente_administrador.post(ruta_de_cambio(arbol), datos)

    arbol.refresh_from_db()
    assert arbol.ubicacion_editada_en_panel is True


# --- endpoints del mapa ------------------------------------------------------------------------


def ruta_de_conversion():
    return reverse("admin:censo_arbol_convertir_coordenadas")


def ruta_de_contexto():
    return reverse("admin:censo_arbol_contexto_del_mapa")


def test_el_endpoint_convierte_utm_a_grados(cliente_editor, arbol):
    este, norte = arbol.ubicacion.x, arbol.ubicacion.y

    respuesta = cliente_editor.get(ruta_de_conversion(), {"utm_este_m": este, "utm_norte_m": norte})

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert (cuerpo["latitud"], cuerpo["longitud"]) == pytest.approx(
        geometrias.utm_a_grados(este, norte), abs=1e-6
    )
    assert cuerpo["dentro_del_campus"] is True
    assert cuerpo["sector_id"] == 1
    assert cuerpo["mensaje"] == ""


def test_el_endpoint_convierte_grados_a_utm(cliente_editor, arbol):
    latitud, longitud = geometrias.utm_a_grados(arbol.ubicacion.x, arbol.ubicacion.y)

    respuesta = cliente_editor.get(ruta_de_conversion(), {"latitud": latitud, "longitud": longitud})

    cuerpo = respuesta.json()
    assert (cuerpo["utm_este_m"], cuerpo["utm_norte_m"]) == pytest.approx(
        (arbol.ubicacion.x, arbol.ubicacion.y), abs=0.01
    )


def test_el_endpoint_avisa_si_el_punto_esta_fuera_del_campus(cliente_editor, arbol):
    este, norte = arbol.ubicacion.x + 20000, arbol.ubicacion.y

    cuerpo = cliente_editor.get(
        ruta_de_conversion(), {"utm_este_m": este, "utm_norte_m": norte}
    ).json()

    assert cuerpo["dentro_del_campus"] is False
    assert "fuera del campus" in cuerpo["mensaje"]


@pytest.mark.parametrize(
    "parametros",
    [{}, {"utm_este_m": "x", "utm_norte_m": "1"}, {"utm_este_m": "1"}, {"latitud": "1"}],
    ids=["vacío", "texto", "falta el norte", "falta la longitud"],
)
def test_el_endpoint_rechaza_coordenadas_ilegibles(cliente_editor, arbol, parametros):
    respuesta = cliente_editor.get(ruta_de_conversion(), parametros)

    assert respuesta.status_code == 400
    assert respuesta.json()["mensaje"]


def test_sin_sesion_los_endpoints_mandan_al_ingreso(db):
    anonimo = Client()

    assert anonimo.get(ruta_de_conversion()).status_code == 302
    assert anonimo.get(ruta_de_contexto()).status_code == 302


def test_quien_solo_puede_ver_arboles_no_usa_los_endpoints(db, sectores):
    usuario = User.objects.create_user("lector", password="x" * 12, is_staff=True)
    usuario.user_permissions.add(Permission.objects.get(codename="view_arbol"))
    cliente = cliente_de(usuario)

    assert cliente.get(ruta_de_conversion(), {"utm_este_m": 1, "utm_norte_m": 1}).status_code == 403
    assert cliente.get(ruta_de_contexto()).status_code == 403


def test_el_endpoint_de_contexto_trae_los_sectores_y_los_demas_arboles(cliente_editor, arbol):
    arbol_evaluado("S01-A002")

    cuerpo = cliente_editor.get(ruta_de_contexto(), {"arbol": arbol.pk}).json()

    tipos = [e["properties"]["tipo"] for e in cuerpo["features"]]
    assert tipos.count("sector") == 5
    codigos = [e["properties"]["codigo"] for e in cuerpo["features"] if "codigo" in e["properties"]]
    assert codigos == ["S01-A002"]


def test_el_widget_conoce_los_endpoints_y_los_campos_que_debe_sincronizar(cliente_editor, arbol):
    configuracion = configuracion_del_mapa(cliente_editor.get(ruta_de_cambio(arbol)))

    assert configuracion["url_convertir"] == ruta_de_conversion()
    assert configuracion["url_contexto"] == ruta_de_contexto()
    assert configuracion["parametros_contexto"] == {"arbol": arbol.pk}
    assert configuracion["campos"] == {
        "utm_este_m": "id_utm_este_m",
        "utm_norte_m": "id_utm_norte_m",
        "latitud": "id_latitud",
        "longitud": "id_longitud",
    }
    assert configuracion["srid_mapa"] == SRID_DEL_WIDGET
    assert SRID_MAPA == 4326


@pytest.mark.parametrize("identificador", ["²", "٣", "abc", "-1", "1.5"])
def test_un_identificador_ilegible_en_el_contexto_da_400_y_no_500(cliente_editor, identificador):
    respuesta = cliente_editor.get(ruta_de_contexto(), {"arbol": identificador})

    assert respuesta.status_code == 400
    assert respuesta.json()["mensaje"]
