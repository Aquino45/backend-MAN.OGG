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

from apps.censo.models import Arbol, ValorCatalogo
from apps.censo.servicios.importar_planilla import importar_planilla
from config.constantes import (
    ESTADO_REGISTRO_EN_REVISION,
    ESTADO_REGISTRO_PUBLICADO,
    HOJA_PLANILLA,
    SRID_UTM_CENSO,
)
from tests.censo.conftest import (
    MEDIDAS_FILA_COMPLETA,
    NOMBRE_ARCHIVO,
    TEXTOS_FILA_COMPLETA,
    arbol_de_ejemplo,
    arbol_evaluado,
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


def test_reimportar_conserva_el_uid_y_no_toca_la_marca_de_destacado(ruta_planilla, sectores):
    motivo = "Ejemplar de mayor copa del sector"
    crear_planilla(ruta_planilla, [fila(nombre_comun="Molle")])
    importar_planilla(ruta_planilla)
    Arbol.objects.filter(codigo="S01-A001").update(destacado=True, motivo_destacado=motivo)
    uid_original = Arbol.objects.get(codigo="S01-A001").uid
    crear_planilla(ruta_planilla, [fila(nombre_comun="Molle corregido")])

    reporte = importar_planilla(ruta_planilla)

    arbol = Arbol.objects.get(codigo="S01-A001")
    assert (reporte.creados, reporte.actualizados) == (0, 1)
    assert arbol.nombre_comun == "Molle corregido"
    assert arbol.uid == uid_original
    assert (arbol.destacado, arbol.motivo_destacado) == (True, motivo)


def test_cada_arbol_importado_tiene_su_propio_uid(ruta_planilla, sectores):
    crear_planilla(ruta_planilla, [fila(), fila()])

    importar_planilla(ruta_planilla)

    uids = list(Arbol.objects.values_list("uid", flat=True))
    assert len(uids) == len(set(uids)) == 2


# --- calidad del registro (BE-012) ------------------------------------------------------------


def fila_completa(punto, **extra):
    este, norte = punto
    datos = {**TEXTOS_FILA_COMPLETA, **MEDIDAS_FILA_COMPLETA, "utm_este_m": este}
    return fila(**{**datos, "utm_norte_m": norte, **extra})


def test_una_fila_completa_entra_publicada_y_una_vacia_entra_en_revision(
    ruta_planilla, punto_dentro
):
    crear_planilla(ruta_planilla, [fila_completa(punto_dentro), fila(nombre_comun="Palma")])

    reporte = importar_planilla(ruta_planilla)

    assert Arbol.objects.get(codigo="S01-A001").estado_registro == ESTADO_REGISTRO_PUBLICADO
    en_revision = Arbol.objects.get(codigo="S01-A002")
    assert en_revision.estado_registro == ESTADO_REGISTRO_EN_REVISION
    assert "Falta el dato «Ubicación»" in en_revision.motivos_revision
    assert reporte.publicados == 1
    assert [r.codigo for r in reporte.en_revision] == ["S01-A002"]
    assert "Falta el dato «Ubicación»" in reporte.en_revision[0].motivos


def test_un_vacio_entra_en_revision_por_la_consola_aunque_el_arbol_ya_existiera(
    ruta_planilla, punto_dentro
):
    arbol_evaluado("S01-A001", altura_total_m=Decimal("2.85"))
    crear_planilla(
        ruta_planilla, [fila_completa(punto_dentro, codigo="S01-A001", altura_total_m=None)]
    )

    reporte = importar_planilla(ruta_planilla)

    arbol = Arbol.objects.get(codigo="S01-A001")
    assert arbol.estado_registro == ESTADO_REGISTRO_EN_REVISION
    assert arbol.altura_total_m is None
    assert "Falta el dato «Altura total»" in arbol.motivos_revision
    assert [r.codigo for r in reporte.en_revision] == ["S01-A001"]


def test_nada_se_descarta_por_calidad_aunque_el_registro_este_muy_mal(ruta_planilla, sectores):
    crear_planilla(ruta_planilla, [fila(), fila(dap_cm="muerto")])

    reporte = importar_planilla(ruta_planilla)

    assert Arbol.objects.count() == 2
    assert (reporte.creados, len(reporte.en_revision), reporte.publicados) == (2, 2, 0)


def test_un_dap_con_texto_explica_el_motivo_con_el_texto(ruta_planilla, punto_dentro):
    crear_planilla(ruta_planilla, [fila_completa(punto_dentro, dap_cm="muerto")])

    reporte = importar_planilla(ruta_planilla)

    assert reporte.en_revision[0].motivos == ["DAP no es un número: «muerto»"]
    assert Arbol.objects.get(codigo="S01-A001").dap_cm is None


def test_un_codigo_repetido_en_el_archivo_no_se_incorpora_y_se_lista(ruta_planilla, punto_dentro):
    crear_planilla(
        ruta_planilla,
        [fila_completa(punto_dentro, codigo="S01-A001"), fila(codigo="S01-A001", nombre_comun="X")],
    )

    reporte = importar_planilla(ruta_planilla)

    assert Arbol.objects.count() == 1
    assert Arbol.objects.get().nombre_comun == "Molle"
    assert [d.codigo for d in reporte.duplicados] == ["S01-A001"]
    assert "repetido" in reporte.duplicados[0].motivo


def test_misma_ubicacion_y_misma_especie_es_un_duplicado(ruta_planilla, punto_dentro):
    crear_planilla(ruta_planilla, [fila_completa(punto_dentro), fila_completa(punto_dentro)])

    reporte = importar_planilla(ruta_planilla)

    assert list(Arbol.objects.values_list("codigo", flat=True)) == ["S01-A001"]
    assert [d.codigo for d in reporte.duplicados] == ["S01-A002"]
    assert "S01-A001" in reporte.duplicados[0].motivo


def test_misma_ubicacion_con_otra_especie_no_es_duplicado(ruta_planilla, punto_dentro):
    otra = fila_completa(punto_dentro, nombre_cientifico="Otra especie")
    crear_planilla(ruta_planilla, [fila_completa(punto_dentro), otra])

    reporte = importar_planilla(ruta_planilla)

    assert Arbol.objects.count() == 2
    assert reporte.duplicados == []


def test_una_fila_incompleta_no_pisa_a_un_arbol_de_ejemplo(ruta_planilla, sectores):
    ejemplo = arbol_de_ejemplo("S01-A001", nombre_comun="Del ejemplo")
    crear_planilla(ruta_planilla, [fila(codigo="S01-A001", nombre_comun="Incompleto")])

    reporte = importar_planilla(ruta_planilla)

    ejemplo.refresh_from_db()
    assert (ejemplo.demo, ejemplo.nombre_comun) == (True, "Del ejemplo")
    assert ejemplo.estado_registro == ESTADO_REGISTRO_PUBLICADO
    assert reporte.ejemplo_sin_cambios == ["S01-A001"]
    assert (reporte.creados, reporte.actualizados, reporte.publicados) == (0, 0, 0)


def test_una_fila_completa_reemplaza_al_ejemplo_y_el_reporte_lo_dice(ruta_planilla, punto_dentro):
    ejemplo = arbol_de_ejemplo("S01-A001", nombre_comun="Del ejemplo")
    crear_planilla(ruta_planilla, [fila_completa(punto_dentro, codigo="S01-A001")])

    reporte = importar_planilla(ruta_planilla)

    real = Arbol.objects.get(pk=ejemplo.pk)
    assert (real.demo, real.nombre_comun, real.brigada) == (False, "Molle", "Brigada A")
    assert real.estado_registro == ESTADO_REGISTRO_PUBLICADO
    assert real.uid == ejemplo.uid
    assert reporte.ejemplo_reemplazados == ["S01-A001"]
    assert (reporte.actualizados, reporte.publicados) == (1, 1)


def test_el_valor_fuera_del_catalogo_manda_a_revision(ruta_planilla, punto_dentro):
    ValorCatalogo.objects.create(campo="estado_general", valor="Regular", explicacion="x")
    crear_planilla(ruta_planilla, [fila_completa(punto_dentro, estado_general="Bueno")])

    reporte = importar_planilla(ruta_planilla)

    assert reporte.en_revision[0].motivos == ["Valor fuera del catálogo en Estado general: «Bueno»"]


def test_el_reporte_avisa_si_falta_cargar_el_catalogo(ruta_planilla, punto_dentro):
    crear_planilla(ruta_planilla, [fila_completa(punto_dentro)])

    reporte = importar_planilla(ruta_planilla)

    assert reporte.catalogo_sin_cargar.startswith("Catálogo sin cargar en: ")


def test_seco_da_el_mismo_reporte_de_calidad_y_no_escribe(ruta_planilla, punto_dentro):
    crear_planilla(
        ruta_planilla, [fila_completa(punto_dentro), fila(), fila_completa(punto_dentro)]
    )

    seco = importar_planilla(ruta_planilla, seco=True)
    assert Arbol.todos.count() == 0
    real = importar_planilla(ruta_planilla)

    assert seco.publicados == real.publicados == 1
    assert [r.codigo for r in seco.en_revision] == [r.codigo for r in real.en_revision]
    assert [d.codigo for d in seco.duplicados] == [d.codigo for d in real.duplicados]


def test_el_comando_imprime_publicados_en_revision_y_duplicados(ruta_planilla, punto_dentro):
    crear_planilla(
        ruta_planilla, [fila_completa(punto_dentro), fila(), fila_completa(punto_dentro)]
    )
    salida = StringIO()

    call_command("importar_planilla", str(ruta_planilla), stdout=salida)

    texto = salida.getvalue()
    assert "1 publicados, 1 en revisión, 1 duplicados no incorporados, 0 de ejemplo" in texto
    assert "En revisión S01-A002: Falta el dato" in texto
    assert "Duplicado S01-A003" in texto


# --- CO₂ simulado (BE-015) ---------------------------------------------------------------------


def test_el_co2_de_la_planilla_entra_marcado_como_simulado(ruta_planilla, sectores):
    crear_planilla(ruta_planilla, [fila(co2_almacenado_kg=120.5, co2_captura_anual_kg=10.25)])

    importar_planilla(ruta_planilla)

    assert Arbol.objects.get().co2_simulado is True


def test_la_constante_decide_si_el_co2_de_la_planilla_es_simulado(
    ruta_planilla, sectores, monkeypatch
):
    monkeypatch.setattr("apps.censo.servicios.carga_planilla.CO2_PLANILLA_ES_SIMULADO", False)
    crear_planilla(ruta_planilla, [fila(co2_almacenado_kg=120.5, co2_captura_anual_kg=10.25)])

    importar_planilla(ruta_planilla)

    assert Arbol.objects.get().co2_simulado is False


def test_una_fila_sin_co2_no_queda_marcada_aunque_la_constante_sea_verdadera(
    ruta_planilla, sectores
):
    crear_planilla(ruta_planilla, [fila()])

    importar_planilla(ruta_planilla)

    assert Arbol.objects.get().co2_simulado is False


def test_al_reimportar_la_constante_vuelve_a_marcar_el_co2(ruta_planilla, sectores):
    crear_planilla(ruta_planilla, [fila(co2_almacenado_kg=120.5)])
    importar_planilla(ruta_planilla)
    Arbol.objects.update(co2_simulado=False)

    importar_planilla(ruta_planilla)

    assert Arbol.objects.get().co2_simulado is True
