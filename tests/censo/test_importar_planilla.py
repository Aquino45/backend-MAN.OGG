"""Tests del importador de la planilla de la brigada.

Las planillas y los sectores de prueba salen de `conftest.py`; nunca se usa el archivo real.
"""

import datetime
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from openpyxl import Workbook

from apps.censo.models import Arbol
from apps.censo.servicios.importar_planilla import importar_planilla
from config.constantes import HOJA_PLANILLA, SRID_UTM_CENSO
from tests.censo.conftest import (
    MEDIDAS_FILA_COMPLETA,
    NOMBRE_ARCHIVO,
    TEXTOS_FILA_COMPLETA,
    crear_planilla,
    fila,
)


def test_una_fila_completa_se_importa_con_todos_sus_campos_y_su_fuente(ruta_planilla, punto_dentro):
    este, norte = punto_dentro
    fecha = datetime.datetime(2026, 10, 7)
    crear_planilla(
        ruta_planilla,
        [
            fila(
                fecha_registro=fecha,
                utm_este_m=este,
                utm_norte_m=norte,
                **TEXTOS_FILA_COMPLETA,
                **MEDIDAS_FILA_COMPLETA,
            )
        ],
    )

    reporte = importar_planilla(ruta_planilla)

    arbol = Arbol.objects.get(codigo="S01-A001")
    assert (reporte.filas_leidas, reporte.creados, reporte.actualizados) == (1, 1, 0)
    assert arbol.sector_id == 1
    assert arbol.fecha_registro == fecha.date()
    assert arbol.brigada == "Brigada A"
    for campo, valor in TEXTOS_FILA_COMPLETA.items():
        assert getattr(arbol, campo) == valor, campo
    for campo, valor in MEDIDAS_FILA_COMPLETA.items():
        assert getattr(arbol, campo) == Decimal(str(valor)), campo
    assert arbol.ubicacion.srid == SRID_UTM_CENSO
    assert (arbol.ubicacion.x, arbol.ubicacion.y) == pytest.approx((este, norte))
    assert arbol.fuente == f"Brigada A, hoja Registro_Campo de {NOMBRE_ARCHIVO}, fila 2"
    assert arbol.fila_origen == 2
    assert arbol.demo is False
    assert reporte.sin_coordenadas == 0
    assert not (reporte.numeros_no_validos or reporte.fuera_de_catalogo or reporte.fuera_de_sector)


def test_formula_sin_valor_guardado_numera_cada_sector_por_separado(ruta_planilla, sectores):
    crear_planilla(ruta_planilla, [fila(sector=id_sector) for id_sector in (1, 2, 1, 1, 2)])

    reporte = importar_planilla(ruta_planilla)

    codigos = list(Arbol.objects.values_list("codigo", flat=True))
    assert codigos == ["S01-A001", "S01-A002", "S01-A003", "S02-A001", "S02-A002"]
    assert reporte.codigos_calculados == 5
    filas_por_codigo = dict(Arbol.objects.values_list("codigo", "fila_origen"))
    assert filas_por_codigo["S01-A002"] == 4
    assert filas_por_codigo["S02-A001"] == 3


def test_codigo_con_valor_guardado_se_usa_tal_cual(ruta_planilla, sectores):
    crear_planilla(ruta_planilla, [fila(codigo="S01-A777"), fila()])

    reporte = importar_planilla(ruta_planilla)

    assert sorted(Arbol.objects.values_list("codigo", flat=True)) == ["S01-A002", "S01-A777"]
    assert reporte.codigos_calculados == 1


def test_calcular_en_gabinete_queda_en_null_y_va_al_reporte(ruta_planilla, sectores):
    crear_planilla(
        ruta_planilla,
        [fila(co2_almacenado_kg="CALCULAR EN GABINETE", co2_captura_anual_kg=12)],
    )

    reporte = importar_planilla(ruta_planilla)

    arbol = Arbol.objects.get()
    assert arbol.co2_almacenado_kg is None
    assert arbol.co2_captura_anual_kg == Decimal("12")
    assert arbol.observaciones is None  # el CO₂ no deja nota, solo DAP y copas
    assert [(v.codigo, v.columna, v.texto) for v in reporte.numeros_no_validos] == [
        ("S01-A001", "CO₂ almacenado (kg CO₂e)", "CALCULAR EN GABINETE")
    ]


def test_dap_muerto_con_espacio_queda_null_con_nota_y_no_duplica_al_reimportar(
    ruta_planilla, sectores
):
    crear_planilla(ruta_planilla, [fila(dap_cm="muerto ")])

    reporte = importar_planilla(ruta_planilla)

    arbol = Arbol.objects.get()
    assert arbol.dap_cm is None
    assert arbol.observaciones == "DAP (cm) en planilla: muerto"
    assert [(v.codigo, v.columna, v.texto) for v in reporte.numeros_no_validos] == [
        ("S01-A001", "DAP (cm)", "muerto")
    ]

    importar_planilla(ruta_planilla)

    assert Arbol.objects.get().observaciones == "DAP (cm) en planilla: muerto"


def test_un_numero_que_no_cabe_en_el_campo_queda_null_y_no_rompe_la_bd(ruta_planilla, sectores):
    demasiado_grande = 10**12
    crear_planilla(
        ruta_planilla,
        [fila(dap_cm=demasiado_grande, altura_total_m=demasiado_grande, copa_ns_m=4.5)],
    )

    reporte = importar_planilla(ruta_planilla)

    arbol = Arbol.objects.get()
    assert (arbol.dap_cm, arbol.altura_total_m) == (None, None)
    assert arbol.copa_ns_m == Decimal("4.5")
    assert arbol.observaciones == f"DAP (cm) en planilla: {demasiado_grande}"
    assert [(v.columna, v.texto) for v in reporte.numeros_no_validos] == [
        ("Altura total (m)", str(demasiado_grande)),
        ("DAP (cm)", str(demasiado_grande)),
    ]


def test_las_notas_se_unen_a_las_observaciones_de_la_fila_con_punto_y_coma(ruta_planilla, sectores):
    crear_planilla(
        ruta_planilla,
        [fila(observaciones="Tronco seco", dap_cm="muerto", copa_ns_m="muerto", copa_eo_m=3)],
    )

    reporte = importar_planilla(ruta_planilla)

    arbol = Arbol.objects.get()
    assert arbol.observaciones == (
        "Tronco seco; DAP (cm) en planilla: muerto; Diámetro copa N-S (m) en planilla: muerto"
    )
    assert arbol.copa_eo_m == Decimal("3")
    assert len(reporte.numeros_no_validos) == 2


def test_importar_dos_veces_no_duplica_nada(ruta_planilla, sectores):
    crear_planilla(ruta_planilla, [fila(nombre_comun="Molle"), fila(sector=2)])

    primero = importar_planilla(ruta_planilla)
    segundo = importar_planilla(ruta_planilla)

    assert (primero.creados, primero.actualizados) == (2, 0)
    assert (segundo.creados, segundo.actualizados) == (0, 2)
    assert Arbol.objects.count() == 2


def test_reimportar_actualiza_lo_que_cambio_en_la_planilla(ruta_planilla, sectores):
    crear_planilla(ruta_planilla, [fila(nombre_comun="Molle")])
    importar_planilla(ruta_planilla)
    crear_planilla(ruta_planilla, [fila(nombre_comun="Eucalipto")])

    importar_planilla(ruta_planilla)

    assert Arbol.objects.get().nombre_comun == "Eucalipto"


def test_falta_una_columna_y_el_error_la_nombra(ruta_planilla, sectores):
    crear_planilla(ruta_planilla, [fila()], sin_columnas=["DAP (cm)", "Brigada"])

    with pytest.raises(ValueError, match=r"Brigada, DAP \(cm\)"):
        importar_planilla(ruta_planilla)

    assert Arbol.objects.count() == 0


def test_falta_la_hoja_y_el_error_la_nombra(tmp_path, sectores):
    libro = Workbook()
    libro.active.title = "Otra"
    ruta = tmp_path / "sin-hoja.xlsx"
    libro.save(ruta)

    with pytest.raises(ValueError, match=HOJA_PLANILLA):
        importar_planilla(ruta)


def test_las_filas_sin_sector_se_saltan_sin_contarse(ruta_planilla, sectores):
    crear_planilla(ruta_planilla, [fila(), {"nombre_comun": "Fila vacía de sector"}, fila()])

    reporte = importar_planilla(ruta_planilla)

    assert reporte.filas_leidas == 2
    assert reporte.codigos_calculados == 2
    assert Arbol.objects.count() == 2


def test_un_punto_fuera_de_su_sector_sale_en_el_reporte_con_la_distancia(
    ruta_planilla, punto_dentro
):
    este, norte = punto_dentro
    desplazamiento_m = 100000.0
    crear_planilla(
        ruta_planilla,
        [
            fila(utm_este_m=este, utm_norte_m=norte),
            fila(utm_este_m=este + desplazamiento_m, utm_norte_m=norte),
        ],
    )

    reporte = importar_planilla(ruta_planilla)

    assert [(a.codigo, a.sector) for a in reporte.fuera_de_sector] == [("S01-A002", 1)]
    assert reporte.fuera_de_sector[0].distancia_m > 0
    assert Arbol.objects.count() == 2  # solo es un aviso: el sector lo manda la planilla


def test_sin_una_de_las_dos_coordenadas_la_ubicacion_queda_null(ruta_planilla, punto_dentro):
    este, norte = punto_dentro
    crear_planilla(
        ruta_planilla,
        [
            fila(utm_este_m=este),
            fila(utm_norte_m=norte),
            fila(utm_este_m=este, utm_norte_m=norte),
        ],
    )

    reporte = importar_planilla(ruta_planilla)

    assert reporte.sin_coordenadas == 2
    assert Arbol.objects.filter(ubicacion__isnull=True).count() == 2
    completo = Arbol.objects.get(ubicacion__isnull=False)
    assert (completo.ubicacion.x, completo.ubicacion.y) == pytest.approx((este, norte))


def test_un_valor_fuera_del_catalogo_se_guarda_y_va_al_reporte(ruta_planilla, sectores):
    crear_planilla(
        ruta_planilla,
        [fila(estado_general="Excelente", estado_copa="Completa", origen=" Nativa ")],
    )

    reporte = importar_planilla(ruta_planilla)

    arbol = Arbol.objects.get()
    assert arbol.estado_general == "Excelente"
    assert arbol.origen == "Nativa"
    assert [(v.codigo, v.columna, v.texto) for v in reporte.fuera_de_catalogo] == [
        ("S01-A001", "Estado general", "Excelente")
    ]


def test_un_sector_que_no_esta_en_la_bd_falla_con_mensaje_claro(ruta_planilla, db):
    crear_planilla(ruta_planilla, [fila(sector=1)])

    with pytest.raises(ValueError, match="importar_sectores"):
        importar_planilla(ruta_planilla)

    assert Arbol.objects.count() == 0


def test_seco_da_el_mismo_reporte_y_no_escribe(ruta_planilla, punto_dentro):
    este, norte = punto_dentro
    crear_planilla(
        ruta_planilla,
        [fila(utm_este_m=este, utm_norte_m=norte, dap_cm="muerto"), fila()],
    )

    reporte_seco = importar_planilla(ruta_planilla, seco=True)

    assert Arbol.objects.count() == 0
    reporte_real = importar_planilla(ruta_planilla)
    assert Arbol.objects.count() == 2
    for campo in (
        "filas_leidas",
        "creados",
        "actualizados",
        "sin_coordenadas",
        "codigos_calculados",
    ):
        assert getattr(reporte_seco, campo) == getattr(reporte_real, campo)
    assert reporte_seco.numeros_no_validos == reporte_real.numeros_no_validos


def test_archivo_inexistente_da_error_claro(tmp_path, db):
    with pytest.raises(ValueError, match="No existe el archivo"):
        importar_planilla(tmp_path / "no-existe.xlsx")


def test_el_comando_imprime_el_reporte_en_espanol(ruta_planilla, sectores):
    crear_planilla(ruta_planilla, [fila(dap_cm="muerto")])
    salida = StringIO()

    call_command("importar_planilla", str(ruta_planilla), "--seco", stdout=salida)

    texto = salida.getvalue()
    assert "simulacro" in texto
    assert "Filas leídas: 1" in texto
    assert "Códigos calculados: 1" in texto
    assert "S01-A001 · DAP (cm): «muerto»" in texto
    assert Arbol.objects.count() == 0


def test_el_comando_convierte_el_error_en_command_error(ruta_planilla, sectores):
    crear_planilla(ruta_planilla, [fila()], sin_columnas=["Sector"])

    with pytest.raises(CommandError, match="Sector"):
        call_command("importar_planilla", str(ruta_planilla))
