"""Tests de `completar_ejemplo`: llena solo vacíos, no pisa, es repetible y rechaza todo o nada."""

import hashlib
import json
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.censo.models import Arbol
from apps.censo.servicios.cargar_demo import cargar_demo
from apps.censo.servicios.completar_ejemplo import completar_ejemplo
from apps.censo.servicios.resolver_campos import texto_de
from config.constantes.calidad import ESTADO_REGISTRO_EN_REVISION, ESTADO_REGISTRO_PUBLICADO
from tests.censo.conftest import arbol_de_ejemplo, arbol_evaluado

RAIZ = Path(__file__).resolve().parents[2]
RUTA_COMPLETAR = RAIZ / "datos" / "demo" / "completar-ejemplo-v1.json"
RUTA_DEMO = RAIZ / "datos" / "demo" / "arboles-demo-v0.json"
SHA256_DEL_ARCHIVO = "a9227467f8d830a9913c33f5f62d899884db0a0a2ee45956bb1ff37756a68b3e"
TOTAL_DE_REGISTROS = 73
TIPO_ARBOL = "Árbol ≥1.30 m (medir DAP)"
NOTA = "Tipo de individuo simulado."


def registro(codigo="S01-A001", campos=None, **cambios):
    datos = {
        "codigo": codigo,
        "marcar_ejemplo": True,
        "campos": campos or {"tipo_individuo": TIPO_ARBOL},
        "campos_simulados": list(campos or {"tipo_individuo": TIPO_ARBOL}),
        "nota_fuente": NOTA,
    }
    datos.update(cambios)
    return datos


def escribir(tmp_path, registros):
    ruta = tmp_path / "completar-prueba.json"
    ruta.write_text(json.dumps(registros, ensure_ascii=False), encoding="utf-8")
    return ruta


def test_el_archivo_del_repo_es_la_copia_literal_del_contexto():
    assert hashlib.sha256(RUTA_COMPLETAR.read_bytes()).hexdigest() == SHA256_DEL_ARCHIVO
    assert len(json.loads(RUTA_COMPLETAR.read_text(encoding="utf-8"))) == TOTAL_DE_REGISTROS


def test_llena_un_campo_vacio_y_publica_el_registro(sectores, tmp_path):
    arbol_de_ejemplo(tipo_individuo=None)
    assert Arbol.objects.get().estado_registro == ESTADO_REGISTRO_EN_REVISION

    reporte = completar_ejemplo(escribir(tmp_path, [registro()]))

    arbol = Arbol.objects.get()
    assert texto_de(arbol, "tipo_individuo") == TIPO_ARBOL
    assert arbol.estado_registro == ESTADO_REGISTRO_PUBLICADO
    assert arbol.motivos_revision == ""
    assert reporte.completados == ["S01-A001"]
    assert (reporte.publicados, reporte.en_revision) == (1, 0)


def test_no_pisa_lo_que_ya_tiene_y_lo_informa(sectores, tmp_path):
    arbol_de_ejemplo(tipo_individuo="Juvenil <1.30 m (sin DAP)", estado_general="Regular")
    campos = {"tipo_individuo": TIPO_ARBOL, "estado_general": "Malo"}

    reporte = completar_ejemplo(escribir(tmp_path, [registro(campos=campos)]))

    arbol = Arbol.objects.get()
    assert (texto_de(arbol, "tipo_individuo"), texto_de(arbol, "estado_general")) == (
        "Juvenil <1.30 m (sin DAP)",
        "Regular",
    )
    assert {(v.campo, v.actual, v.propuesto) for v in reporte.no_se_pisa} == {
        ("tipo_individuo", "Juvenil <1.30 m (sin DAP)", TIPO_ARBOL),
        ("estado_general", "Regular", "Malo"),
    }
    assert reporte.completados == []


def test_lo_que_ya_vale_lo_mismo_no_se_informa_como_pisado(sectores, tmp_path):
    arbol_de_ejemplo(tipo_individuo=TIPO_ARBOL, dap_cm=Decimal("35.25"))
    campos = {"tipo_individuo": TIPO_ARBOL, "dap_cm": 35.25}

    reporte = completar_ejemplo(escribir(tmp_path, [registro(campos=campos)]))

    assert reporte.no_se_pisa == []
    assert reporte.sin_cambios == 1


def test_llena_un_numero_como_decimal(sectores, tmp_path):
    arbol_de_ejemplo(dap_cm=None, tipo_individuo=TIPO_ARBOL)

    completar_ejemplo(escribir(tmp_path, [registro(campos={"dap_cm": 12.5})]))

    assert Arbol.objects.get().dap_cm == Decimal("12.5")


def test_agrega_a_la_fuente_la_nota_y_los_campos_simulados(sectores, tmp_path):
    arbol_de_ejemplo(tipo_individuo=None, fuente="Dato simulado (demo)")

    completar_ejemplo(escribir(tmp_path, [registro()]))

    assert Arbol.objects.get().fuente == (
        f"Dato simulado (demo) | {NOTA} (campos simulados: tipo_individuo)"
    )


def test_es_idempotente_la_segunda_corrida_no_cambia_nada(sectores, tmp_path):
    arbol_de_ejemplo(tipo_individuo=None)
    ruta = escribir(tmp_path, [registro()])
    completar_ejemplo(ruta)
    despues_de_la_primera = Arbol.objects.values().get()
    versiones = Arbol.objects.get().history.count()

    segunda = completar_ejemplo(ruta)

    assert Arbol.objects.values().get() == despues_de_la_primera
    assert Arbol.objects.get().history.count() == versiones
    assert (segunda.completados, segunda.sin_cambios, segunda.no_se_pisa) == ([], 1, [])


def test_deja_rastro_en_el_historial(sectores, tmp_path):
    arbol_de_ejemplo(tipo_individuo=None)

    completar_ejemplo(escribir(tmp_path, [registro()]))

    assert Arbol.objects.get().history.first().history_change_reason == "Completar datos de ejemplo"


def test_un_arbol_real_no_se_toca(sectores, tmp_path):
    arbol_evaluado(tipo_individuo=None)

    reporte = completar_ejemplo(escribir(tmp_path, [registro()]))

    arbol = Arbol.objects.get()
    assert (arbol.demo, texto_de(arbol, "tipo_individuo")) == (False, None)
    assert reporte.reales_sin_tocar == ["S01-A001"]


@pytest.mark.parametrize(
    "malo",
    [
        registro(codigo="S01-A00"),
        registro(marcar_ejemplo="si"),
        registro(nota_fuente=" "),
        registro(campos={}),
        registro(campos={"ubicacion": "x"}, campos_simulados=[]),
        registro(campos={"dap_cm": "muerto"}),
        registro(campos_simulados=["otro_campo"]),
        registro(codigo="S01-A099"),  # no existe en la BD
        {"codigo": "S01-A001"},
        "no es un objeto",
    ],
    ids=lambda malo: str(malo)[:40],
)
def test_un_registro_malo_rechaza_el_archivo_entero_sin_tocar_la_bd(sectores, tmp_path, malo):
    arbol_de_ejemplo(tipo_individuo=None)
    antes = Arbol.objects.values().get()

    with pytest.raises(ValueError, match="no se guardó nada"):
        completar_ejemplo(escribir(tmp_path, [registro(), malo]))

    assert Arbol.objects.values().get() == antes


def test_un_codigo_repetido_en_el_archivo_lo_rechaza(sectores, tmp_path):
    arbol_de_ejemplo(tipo_individuo=None)

    with pytest.raises(ValueError, match="repetido"):
        completar_ejemplo(escribir(tmp_path, [registro(), registro()]))


@pytest.mark.parametrize("contenido", ["{no es json", "{}", "[]"])
def test_un_archivo_que_no_es_una_lista_de_registros_se_rechaza(sectores, tmp_path, contenido):
    ruta = tmp_path / "malo.json"
    ruta.write_text(contenido, encoding="utf-8")

    with pytest.raises(ValueError):
        completar_ejemplo(ruta)


def test_un_archivo_inexistente_da_error_claro(sectores, tmp_path):
    with pytest.raises(ValueError, match="No existe el archivo"):
        completar_ejemplo(tmp_path / "no-esta.json")


def test_el_comando_imprime_el_reporte_y_convierte_el_error(sectores, tmp_path):
    arbol_de_ejemplo(tipo_individuo=None)
    salida = StringIO()

    call_command("completar_ejemplo", str(escribir(tmp_path, [registro()])), stdout=salida)

    assert "Árboles completados: 1" in salida.getvalue()
    with pytest.raises(CommandError, match="No existe el archivo"):
        call_command("completar_ejemplo", str(tmp_path / "no-esta.json"))


def test_el_archivo_real_publica_los_73_simulados_de_s2_a_s5(sectores, especies_demo):
    cargar_demo(RUTA_DEMO)
    assert Arbol.objects.filter(estado_registro=ESTADO_REGISTRO_PUBLICADO).count() == 0

    reporte = completar_ejemplo(RUTA_COMPLETAR)

    assert (reporte.registros, len(reporte.completados)) == (TOTAL_DE_REGISTROS,) * 2
    assert reporte.no_se_pisa == []
    assert reporte.en_revision == 0
    assert Arbol.objects.filter(estado_registro=ESTADO_REGISTRO_PUBLICADO).count() == 73
    assert completar_ejemplo(RUTA_COMPLETAR).sin_cambios == TOTAL_DE_REGISTROS
