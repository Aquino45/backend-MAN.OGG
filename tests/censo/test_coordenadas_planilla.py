"""Tests de las coordenadas de la planilla: UTM, grados WGS 84 y UTM con el rótulo equivocado.

Las planillas se arman en el test con openpyxl; nunca se usa el archivo real.
"""

from io import StringIO

import pytest
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse

from apps.censo.models import Arbol, GrupoBrigada, LoteCarga
from apps.censo.servicios.carga_planilla import aplicar_decisiones, evaluar
from apps.censo.servicios.importar_planilla import importar_planilla
from apps.censo.servicios.lectura_planilla import entero_sector, leer
from config.constantes.carga import (
    CLASIFICACION_INCONSISTENTE,
    CLASIFICACION_LISTO,
    DECISION_CONSERVAR,
)
from config.constantes.general import SRID_MAPA, SRID_UTM_CENSO
from config.constantes.planilla import AVISO_COLUMNAS_COORDENADAS_CON_UTM
from tests.censo.conftest import (
    MEDIDAS_FILA_COMPLETA,
    TEXTOS_FILA_COMPLETA,
    crear_planilla,
    fila,
)

pytestmark = pytest.mark.usefixtures("especie_molle")

COLUMNAS_EN_GRADOS = {"UTM Este (m)": "Latitud", "UTM Norte (m)": "Longitud"}
"""Los encabezados con que llegan las coordenadas en la planilla del stakeholder."""

TEXTO_AVISO = "Columnas Latitud/Longitud con valores UTM: se tomaron como UTM"


def fila_en(primera, segunda, codigo="S01-A001"):
    """Una fila completa con sus dos coordenadas tal como se escriben bajo cada encabezado."""
    datos = {**TEXTOS_FILA_COMPLETA, **MEDIDAS_FILA_COMPLETA}
    return fila(**{**datos, "codigo": codigo, "utm_este_m": primera, "utm_norte_m": segunda})


def planilla_con(ruta, filas, renombrar=COLUMNAS_EN_GRADOS):
    return leer(crear_planilla(ruta, filas, renombrar=renombrar))


def en_grados(punto_utm):
    """(latitud, longitud) del punto UTM, calculadas con el mismo PROJ."""
    punto = Point(punto_utm[0], punto_utm[1], srid=SRID_UTM_CENSO).transform(SRID_MAPA, clone=True)
    return punto.y, punto.x


# --- lectura ---------------------------------------------------------------------------------


def test_los_grados_del_campus_se_convierten_a_utm_18s(ruta_planilla, punto_dentro):
    latitud, longitud = en_grados(punto_dentro)

    planilla = planilla_con(ruta_planilla, [fila_en(latitud, longitud)])

    datos = planilla.filas[0][1]
    assert (float(datos["utm_este_m"]), float(datos["utm_norte_m"])) == pytest.approx(
        punto_dentro, abs=0.01
    )
    assert planilla.avisos == []


def test_los_grados_como_texto_con_coma_decimal_tambien_se_convierten(ruta_planilla, punto_dentro):
    latitud, longitud = en_grados(punto_dentro)
    texto_latitud, texto_longitud = (
        f"{valor:.7f}".replace(".", ",") for valor in (latitud, longitud)
    )

    planilla = planilla_con(ruta_planilla, [fila_en(texto_latitud, texto_longitud)])

    datos = planilla.filas[0][1]
    assert (float(datos["utm_este_m"]), float(datos["utm_norte_m"])) == pytest.approx(
        punto_dentro, abs=0.05
    )


def test_los_valores_utm_bajo_latitud_y_longitud_se_toman_como_utm_y_avisan(
    ruta_planilla, punto_dentro
):
    este, norte = punto_dentro

    planilla = planilla_con(ruta_planilla, [fila_en(int(este), int(norte))])

    datos = planilla.filas[0][1]
    assert (datos["utm_este_m"], datos["utm_norte_m"]) == (int(este), int(norte))
    assert planilla.avisos == [AVISO_COLUMNAS_COORDENADAS_CON_UTM]
    assert AVISO_COLUMNAS_COORDENADAS_CON_UTM == TEXTO_AVISO


def test_el_aviso_de_utm_mal_rotulado_sale_una_sola_vez(ruta_planilla, punto_dentro):
    este, norte = punto_dentro
    filas = [
        fila_en(int(este), int(norte), "S01-A001"),
        fila_en(int(este) + 1, int(norte), "S01-A002"),
    ]

    planilla = planilla_con(ruta_planilla, filas)

    assert planilla.avisos == [AVISO_COLUMNAS_COORDENADAS_CON_UTM]


@pytest.mark.parametrize(
    "primera, segunda",
    [(5, 7), (-11.99, 8673480), (299536, -76.84), ("a", "b"), (-11.99, None)],
    ids=["fuera de rango", "grados y utm mezclados", "utm y grados", "texto", "falta una"],
)
def test_otra_cosa_deja_la_fila_sin_ubicacion_y_la_manda_a_revision_con_su_motivo(
    ruta_planilla, sectores, primera, segunda
):
    planilla = planilla_con(ruta_planilla, [fila_en(primera, segunda)])

    datos = planilla.filas[0][1]
    assert (datos["utm_este_m"], datos["utm_norte_m"]) == (None, None)
    fila_evaluada = evaluar(planilla).filas[0]
    assert fila_evaluada.clasificacion == CLASIFICACION_INCONSISTENTE
    assert "Ubicación" in " ".join(str(motivo) for motivo in fila_evaluada.motivos)
    assert fila_evaluada.valores["ubicacion"] is None


def test_una_ubicacion_vacia_no_es_un_error_de_coordenadas(ruta_planilla, sectores):
    planilla = planilla_con(ruta_planilla, [fila_en(None, None)])

    fila_evaluada = evaluar(planilla).filas[0]

    assert fila_evaluada.sin_coordenadas is True
    assert fila_evaluada.numeros_no_validos == []


def test_con_encabezados_utm_no_se_interpreta_nada_ni_se_avisa(ruta_planilla, punto_dentro):
    este, norte = punto_dentro

    planilla = planilla_con(ruta_planilla, [fila_en(este, norte)], renombrar={})

    assert planilla.avisos == []
    assert planilla.filas[0][1]["utm_este_m"] == pytest.approx(este)


def test_con_solo_una_columna_nueva_el_error_sigue_nombrando_las_utm(ruta_planilla):
    with pytest.raises(
        ValueError, match=r"Faltan columnas en la planilla: UTM Este \(m\), UTM Norte \(m\)"
    ):
        leer(
            crear_planilla(
                ruta_planilla,
                [fila_en(1, 2)],
                sin_columnas=["UTM Norte (m)"],
                renombrar={"UTM Este (m)": "Latitud"},
            )
        )


def test_sin_ningun_par_de_coordenadas_el_error_nombra_las_columnas_utm(ruta_planilla):
    with pytest.raises(
        ValueError, match=r"Faltan columnas en la planilla: UTM Este \(m\), UTM Norte \(m\)"
    ):
        leer(crear_planilla(ruta_planilla, [fila()], sin_columnas=list(COLUMNAS_EN_GRADOS)))


# --- consola ---------------------------------------------------------------------------------


def test_la_consola_importa_las_coordenadas_en_grados(ruta_planilla, punto_dentro):
    latitud, longitud = en_grados(punto_dentro)
    crear_planilla(ruta_planilla, [fila_en(latitud, longitud)], renombrar=COLUMNAS_EN_GRADOS)

    reporte = importar_planilla(ruta_planilla)

    arbol = Arbol.objects.get(codigo="S01-A001")
    assert (arbol.ubicacion.x, arbol.ubicacion.y) == pytest.approx(punto_dentro, abs=0.01)
    assert arbol.ubicacion.srid == SRID_UTM_CENSO
    assert reporte.avisos == []


def test_la_consola_avisa_cuando_las_columnas_traen_utm(ruta_planilla, punto_dentro):
    este, norte = punto_dentro
    crear_planilla(ruta_planilla, [fila_en(int(este), int(norte))], renombrar=COLUMNAS_EN_GRADOS)
    salida = StringIO()

    call_command("importar_planilla", str(ruta_planilla), stdout=salida)

    assert TEXTO_AVISO in salida.getvalue()
    assert Arbol.objects.get(codigo="S01-A001").ubicacion.x == pytest.approx(int(este))


# --- carga web ---------------------------------------------------------------------------------


def subir(cliente, ruta):
    archivo = SimpleUploadedFile("arb.xlsx", ruta.read_bytes())
    return cliente.post(reverse("admin:censo_lotecarga_changelist"), {"planilla": archivo})


def test_la_carga_web_acepta_latitud_y_longitud_con_utm_y_el_lote_avisa(
    cliente_administrador, ruta_planilla, punto_dentro
):
    este, norte = punto_dentro
    crear_planilla(ruta_planilla, [fila_en(int(este), int(norte))], renombrar=COLUMNAS_EN_GRADOS)

    respuesta = subir(cliente_administrador, ruta_planilla)

    assert respuesta.status_code == 302
    lote = LoteCarga.objects.get()
    assert lote.resultado["avisos"] == [AVISO_COLUMNAS_COORDENADAS_CON_UTM]
    assert lote.listos == 1
    resumen = cliente_administrador.get(respuesta["Location"])
    assert TEXTO_AVISO in resumen.content.decode()


def test_el_aviso_del_lote_sobrevive_a_confirmar_y_sale_en_el_resultado(
    cliente_administrador, ruta_planilla, punto_dentro
):
    este, norte = punto_dentro
    crear_planilla(ruta_planilla, [fila_en(int(este), int(norte))], renombrar=COLUMNAS_EN_GRADOS)
    subir(cliente_administrador, ruta_planilla)
    lote = LoteCarga.objects.get()

    cliente_administrador.post(reverse("admin:censo_lotecarga_confirmar", args=[lote.pk]))

    lote.refresh_from_db()
    assert lote.resultado["avisos"] == [AVISO_COLUMNAS_COORDENADAS_CON_UTM]
    resultado = cliente_administrador.get(
        reverse("admin:censo_lotecarga_resultado", args=[lote.pk])
    )
    assert TEXTO_AVISO in resultado.content.decode()
    assert Arbol.objects.get(codigo="S01-A001").ubicacion.x == pytest.approx(int(este))


def test_la_carga_web_con_grados_publica_el_arbol_sin_aviso(
    cliente_administrador, ruta_planilla, punto_dentro
):
    latitud, longitud = en_grados(punto_dentro)
    crear_planilla(ruta_planilla, [fila_en(latitud, longitud)], renombrar=COLUMNAS_EN_GRADOS)

    subir(cliente_administrador, ruta_planilla)

    lote = LoteCarga.objects.get()
    assert lote.resultado.get("avisos", []) == []
    assert (lote.listos, lote.inconsistentes) == (1, 0)
    assert evaluar(leer(ruta_planilla)).filas[0].clasificacion == CLASIFICACION_LISTO


def test_la_carga_web_manda_a_revision_la_fila_con_coordenadas_ilegibles(
    cliente_administrador, ruta_planilla, sectores
):
    crear_planilla(ruta_planilla, [fila_en(5, 7)], renombrar=COLUMNAS_EN_GRADOS)

    subir(cliente_administrador, ruta_planilla)

    lote = LoteCarga.objects.get()
    assert (lote.listos, lote.inconsistentes) == (0, 1)


# --- el rótulo del sector ("S01") y la planilla real del stakeholder ---------------------------


@pytest.mark.parametrize(
    "valor, esperado",
    [(1, 1), ("1", 1), (1.0, 1), ("S01", 1), ("s1", 1), ("S 01", 1), (" s03 ", 3), ("S5", 5)],
)
def test_entero_sector_acepta_numeros_y_el_rotulo_s_mas_numero(valor, esperado):
    assert entero_sector(valor) == esperado


@pytest.mark.parametrize("valor", ["", None, "Sector 1", "SX1", "S", "1S", "A01", "S01-A001"])
def test_entero_sector_rechaza_cualquier_otra_cosa_con_un_mensaje_claro(valor):
    with pytest.raises(ValueError, match="Sector no válido en la planilla"):
        entero_sector(valor)


GRUPOS_DE_LA_BRIGADA = ("Sopita", "zapatito", "zapato")
ROTULOS_DE_SECTOR = ("S01", "s1", "S 01", "S01", "s1", "S 01")


@pytest.fixture
def grupos(db):
    """Los grupos de la brigada que siembra la migración."""
    return {g.nombre: g for g in GrupoBrigada.objects.select_related("brigada")}


@pytest.fixture
def planilla_del_stakeholder(ruta_planilla, punto_dentro, grupos):
    """Una planilla sintética con la forma de la original: sector «S01», sin código, Latitud y
    Longitud con valores UTM, y la columna «Brigada» con el nombre del grupo."""
    este, norte = punto_dentro
    filas = []
    for orden, rotulo in enumerate(ROTULOS_DE_SECTOR):
        datos = fila_en(int(este) + orden, int(norte) + orden)
        del datos["codigo"]
        datos.update(sector=rotulo, brigada=GRUPOS_DE_LA_BRIGADA[orden % 3])
        filas.append(datos)
    crear_planilla(ruta_planilla, filas, renombrar=COLUMNAS_EN_GRADOS)
    return ruta_planilla


def test_una_planilla_con_la_forma_de_la_del_stakeholder_se_lee_se_evalua_y_se_carga(
    planilla_del_stakeholder, punto_dentro
):
    planilla = leer(planilla_del_stakeholder)

    evaluacion = evaluar(planilla)
    resultado = aplicar_decisiones(
        evaluacion, {fila.numero_fila: DECISION_CONSERVAR for fila in evaluacion.filas}
    )

    total = len(ROTULOS_DE_SECTOR)
    assert len(planilla.filas) == len(evaluacion.filas) == total
    assert planilla.avisos == [AVISO_COLUMNAS_COORDENADAS_CON_UTM]
    assert resultado.creados == total
    assert [a.codigo for a in Arbol.objects.order_by("codigo")] == [
        f"S01-A{orden:03d}" for orden in range(1, total + 1)
    ]
    for arbol in Arbol.todos.all():
        assert arbol.sector_id == 1
        assert arbol.ubicacion.srid == SRID_UTM_CENSO
        assert arbol.ubicacion.x == pytest.approx(punto_dentro[0], abs=total + 1)


def test_el_grupo_se_resuelve_desde_la_columna_de_brigada(planilla_del_stakeholder, grupos):
    evaluacion = evaluar(leer(planilla_del_stakeholder))
    aplicar_decisiones(evaluacion, {f.numero_fila: DECISION_CONSERVAR for f in evaluacion.filas})

    nombres = [a.grupo.nombre for a in Arbol.todos.order_by("codigo")]
    assert nombres == [GRUPOS_DE_LA_BRIGADA[i % 3] for i in range(len(ROTULOS_DE_SECTOR))]
    assert {a.grupo.brigada.nombre for a in Arbol.todos.all()} == {"Brigada A"}
