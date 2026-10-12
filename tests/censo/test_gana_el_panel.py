"""Tests de «gana el panel»: una ubicación corregida a mano sobrevive a la reimportación.

Vale para la consola y para la carga web, que comparten el camino de guardado.
"""

from io import StringIO

import pytest
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse

from apps.censo.models import Arbol, LoteCarga
from apps.censo.servicios.importar_planilla import importar_planilla
from config.constantes.calidad import ESTADO_REGISTRO_PUBLICADO
from config.constantes.carga import (
    AVISO_UBICACION_DEL_PANEL,
    ESTADO_LOTE_CONFIRMADO,
    PREFIJO_CONSERVAR_CARGA,
)
from config.constantes.general import SRID_UTM_CENSO
from tests.censo.conftest import (
    MEDIDAS_FILA_COMPLETA,
    TEXTOS_FILA_COMPLETA,
    arbol_evaluado,
    crear_planilla,
    fila,
)

pytestmark = pytest.mark.usefixtures("especie_molle")

TEXTO_AVISO = "Ubicación corregida en el panel; se mantiene"
CODIGO = "S01-A001"
DESPLAZAMIENTO_M = 4


def fila_en(este, norte, **extra):
    datos = {**TEXTOS_FILA_COMPLETA, **MEDIDAS_FILA_COMPLETA}
    return fila(**{**datos, "codigo": CODIGO, "utm_este_m": este, "utm_norte_m": norte, **extra})


def punto_utm(este, norte):
    return Point(este, norte, srid=SRID_UTM_CENSO)


@pytest.fixture
def arbol_del_panel(punto_dentro):
    """Un árbol de campo cuya ubicación se corrigió a mano en el panel."""
    este, norte = punto_dentro
    arbol = arbol_evaluado(CODIGO, ubicacion=punto_utm(este + 2, norte + 2))
    Arbol.todos.filter(pk=arbol.pk).update(ubicacion_editada_en_panel=True)
    return Arbol.todos.get(pk=arbol.pk)


def subir_y_confirmar(cliente, ruta, conservar_las_filas_con_problema=False):
    """Sube la planilla y la confirma; con la bandera, pasa por la revisión y conserva todo."""
    archivo = SimpleUploadedFile("arb.xlsx", ruta.read_bytes())
    cliente.post(reverse("admin:censo_lotecarga_changelist"), {"planilla": archivo})
    lote = LoteCarga.objects.latest("id")
    if conservar_las_filas_con_problema:
        marcas = {
            f"{PREFIJO_CONSERVAR_CARGA}{fila_carga.pk}": "on" for fila_carga in lote.filas.all()
        }
        cliente.post(reverse("admin:censo_lotecarga_revisar", args=[lote.pk]), marcas)
    else:
        cliente.post(reverse("admin:censo_lotecarga_confirmar", args=[lote.pk]))
    lote.refresh_from_db()
    return lote


def ubicacion_de(codigo):
    ubicacion = Arbol.todos.get(codigo=codigo).ubicacion
    return ubicacion.x, ubicacion.y


# --- el modelo ---------------------------------------------------------------------------------


def test_un_arbol_nuevo_no_trae_la_marca_del_panel(punto_dentro):
    arbol = arbol_evaluado(CODIGO)

    assert arbol.ubicacion_editada_en_panel is False
    assert arbol.fecha_ubicacion_editada is None


# --- consola ---------------------------------------------------------------------------------


def test_la_consola_conserva_la_ubicacion_del_panel_y_avisa(
    ruta_planilla, arbol_del_panel, punto_dentro
):
    este, norte = punto_dentro
    crear_planilla(ruta_planilla, [fila_en(este + DESPLAZAMIENTO_M, norte)])

    reporte = importar_planilla(ruta_planilla)

    ubicacion = arbol_del_panel.ubicacion
    assert ubicacion_de(CODIGO) == pytest.approx((ubicacion.x, ubicacion.y))
    assert reporte.ubicaciones_del_panel == [CODIGO]
    assert Arbol.todos.get(codigo=CODIGO).ubicacion_editada_en_panel is True


def test_el_reporte_de_la_consola_imprime_el_aviso_con_el_codigo(
    ruta_planilla, arbol_del_panel, punto_dentro
):
    este, norte = punto_dentro
    crear_planilla(ruta_planilla, [fila_en(este + DESPLAZAMIENTO_M, norte)])
    salida = StringIO()

    call_command("importar_planilla", str(ruta_planilla), stdout=salida)

    assert f"{AVISO_UBICACION_DEL_PANEL}: 1" in salida.getvalue()
    assert f"  {CODIGO}" in salida.getvalue()
    assert AVISO_UBICACION_DEL_PANEL == TEXTO_AVISO


def test_con_la_misma_ubicacion_no_hay_aviso(ruta_planilla, arbol_del_panel):
    ubicacion = arbol_del_panel.ubicacion
    crear_planilla(ruta_planilla, [fila_en(ubicacion.x, ubicacion.y)])
    salida = StringIO()

    call_command("importar_planilla", str(ruta_planilla), stdout=salida)

    assert AVISO_UBICACION_DEL_PANEL not in salida.getvalue()
    assert ubicacion_de(CODIGO) == pytest.approx((ubicacion.x, ubicacion.y))


def test_sin_la_marca_la_planilla_mueve_el_arbol_como_siempre(ruta_planilla, punto_dentro):
    este, norte = punto_dentro
    arbol_evaluado(CODIGO, ubicacion=punto_utm(este + 2, norte + 2))
    crear_planilla(ruta_planilla, [fila_en(este + DESPLAZAMIENTO_M, norte)])

    reporte = importar_planilla(ruta_planilla)

    assert ubicacion_de(CODIGO) == pytest.approx((este + DESPLAZAMIENTO_M, norte))
    assert reporte.ubicaciones_del_panel == []


def test_con_la_marca_una_planilla_sin_coordenadas_no_borra_la_ubicacion_ni_avisa(
    ruta_planilla, arbol_del_panel
):
    ubicacion = arbol_del_panel.ubicacion
    crear_planilla(ruta_planilla, [fila_en(None, None)])

    reporte = importar_planilla(ruta_planilla)

    assert ubicacion_de(CODIGO) == pytest.approx((ubicacion.x, ubicacion.y))
    assert reporte.ubicaciones_del_panel == []


def test_la_calidad_se_calcula_con_la_ubicacion_que_se_mantiene(ruta_planilla, arbol_del_panel):
    lejos = arbol_del_panel.ubicacion.x + 5000
    crear_planilla(ruta_planilla, [fila_en(lejos, arbol_del_panel.ubicacion.y)])

    importar_planilla(ruta_planilla)

    arbol = Arbol.todos.get(codigo=CODIGO)
    assert arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO
    assert "La ubicación cae" not in arbol.motivos_revision


def test_el_historial_guarda_la_ubicacion_que_se_mantiene(ruta_planilla, arbol_del_panel):
    ubicacion = arbol_del_panel.ubicacion
    crear_planilla(ruta_planilla, [fila_en(ubicacion.x + 3, ubicacion.y)])

    importar_planilla(ruta_planilla)

    ultima = Arbol.todos.get(codigo=CODIGO).history.first()
    assert (ultima.ubicacion.x, ultima.ubicacion.y) == pytest.approx((ubicacion.x, ubicacion.y))


# --- carga web ---------------------------------------------------------------------------------


def test_la_carga_web_conserva_la_ubicacion_del_panel_y_el_lote_avisa(
    cliente_administrador, ruta_planilla, arbol_del_panel, punto_dentro
):
    este, norte = punto_dentro
    crear_planilla(ruta_planilla, [fila_en(este + DESPLAZAMIENTO_M, norte)])
    ubicacion = arbol_del_panel.ubicacion

    lote = subir_y_confirmar(cliente_administrador, ruta_planilla)

    assert ubicacion_de(CODIGO) == pytest.approx((ubicacion.x, ubicacion.y))
    assert lote.resultado["ubicaciones_del_panel"] == [CODIGO]
    pantalla = cliente_administrador.get(
        reverse("admin:censo_lotecarga_resultado", args=[lote.pk])
    ).content.decode()
    assert TEXTO_AVISO in pantalla
    assert CODIGO in pantalla


def test_la_carga_web_con_la_misma_ubicacion_no_avisa(
    cliente_administrador, ruta_planilla, arbol_del_panel
):
    ubicacion = arbol_del_panel.ubicacion
    crear_planilla(ruta_planilla, [fila_en(ubicacion.x, ubicacion.y)])

    lote = subir_y_confirmar(cliente_administrador, ruta_planilla)

    assert lote.resultado["ubicaciones_del_panel"] == []
    pantalla = cliente_administrador.get(
        reverse("admin:censo_lotecarga_resultado", args=[lote.pk])
    ).content.decode()
    assert TEXTO_AVISO not in pantalla


def test_la_carga_web_con_celda_vacia_sigue_sin_borrar_la_ubicacion(
    cliente_administrador, ruta_planilla, arbol_del_panel
):
    ubicacion = arbol_del_panel.ubicacion
    crear_planilla(ruta_planilla, [fila_en(None, None)])

    lote = subir_y_confirmar(cliente_administrador, ruta_planilla, True)

    assert lote.estado == ESTADO_LOTE_CONFIRMADO
    assert ubicacion_de(CODIGO) == pytest.approx((ubicacion.x, ubicacion.y))
    assert lote.resultado["ubicaciones_del_panel"] == []
