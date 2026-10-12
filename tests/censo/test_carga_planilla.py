"""Tests de «Cargar planilla»: validar sin guardar, alertas, revisión por fila y confirmación.

Las planillas se arman en el test con openpyxl (nunca se usa el archivo real) y se suben por el
panel con el cliente de pruebas.
"""

import hashlib
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from apps.censo.models import Arbol, FilaCarga, LoteCarga, ValorCatalogo
from apps.censo.servicios.carga_planilla import evaluar, valores_activos_del_catalogo
from apps.censo.servicios.lectura_planilla import leer
from config.constantes import (
    CLASIFICACION_CAMPOS_VACIOS,
    CLASIFICACION_DUPLICADO,
    CLASIFICACION_INCONSISTENTE,
    CLASIFICACION_LISTO,
    ESTADO_LOTE_CANCELADO,
    ESTADO_LOTE_CONFIRMADO,
    ESTADO_LOTE_VALIDADO,
    ESTADO_REGISTRO_EN_REVISION,
    ESTADO_REGISTRO_PUBLICADO,
    HORAS_VIDA_LOTE_CARGA,
    NOMBRE_ROL_EDITOR,
    PREFIJO_CAMPO_CARGA,
    PREFIJO_CONSERVAR_CARGA,
)
from tests.censo.conftest import (
    CLAVE_PRUEBA,
    MEDIDAS_FILA_COMPLETA,
    NOMBRE_ARCHIVO,
    TEXTOS_FILA_COMPLETA,
    arbol_de_ejemplo,
    arbol_evaluado,
    cliente_de,
    crear_planilla,
    fila,
    usuario_con_rol,
)

URL_SUBIR = "admin:censo_lotecarga_changelist"

pytestmark = pytest.mark.usefixtures("especie_molle")


def fila_buena(punto, codigo, desplazamiento_m=0, **extra):
    """Una fila completa y consistente; cada código lleva su propio punto."""
    este, norte = punto
    datos = {**TEXTOS_FILA_COMPLETA, **MEDIDAS_FILA_COMPLETA}
    datos.update(utm_este_m=este + desplazamiento_m, utm_norte_m=norte, codigo=codigo)
    return fila(**{**datos, **extra})


def planilla_mixta(punto):
    """Un listo, uno con campos vacíos, tres inconsistentes y un código repetido dos veces."""
    return [
        fila_buena(punto, "S01-A001", 1),
        fila(codigo="S01-A002"),
        fila_buena(punto, "S01-A003", 2, dap_cm="muerto"),
        fila_buena(punto, "S01-A004", 3, dap_cm="muerto", observaciones="Del archivo"),
        fila_buena(punto, "S01-A005", 4),
        fila_buena(punto, "S01-A005", 5, observaciones="Otro molle"),
        fila_buena(punto, "S01-A006", 6, dap_cm="muerto"),
    ]


def contenido_de(tmp_path, filas, **opciones):
    ruta = crear_planilla(tmp_path / NOMBRE_ARCHIVO, filas, **opciones)
    return ruta.read_bytes()


def subir(cliente, contenido, nombre=NOMBRE_ARCHIVO):
    archivo = SimpleUploadedFile(nombre, contenido)
    return cliente.post(reverse(URL_SUBIR), {"planilla": archivo})


def cargar(cliente, tmp_path, filas, **opciones):
    """Sube la planilla y devuelve el lote validado que quedó."""
    respuesta = subir(cliente, contenido_de(tmp_path, filas, **opciones))
    assert respuesta.status_code == 302, respuesta.content.decode()
    return LoteCarga.objects.latest("id")


def url(nombre, lote):
    return reverse(f"admin:censo_lotecarga_{nombre}", args=[lote.pk])


def fila_del_lote(lote, codigo, indice=0):
    return lote.filas.filter(codigo=codigo).order_by("numero_fila")[indice]


def texto(respuesta):
    return respuesta.content.decode()


@pytest.fixture
def punto(punto_dentro):
    return punto_dentro


@pytest.fixture
def lote_mixto(cliente_administrador, tmp_path, punto):
    """La planilla mixta ya validada; existe S01-A004 en la BD con otro nombre."""
    arbol_evaluado("S01-A004", observaciones="Ya registrado")
    return cargar(cliente_administrador, tmp_path, planilla_mixta(punto))


# --- validar sin guardar y resumen ------------------------------------------------------------


def test_validar_no_guarda_ningun_arbol_y_el_resumen_cuenta_cada_clase(
    lote_mixto, cliente_administrador
):
    respuesta = cliente_administrador.get(url("resumen", lote_mixto))

    cuerpo = texto(respuesta)
    assert "1 listos · 1 con campos vacíos · 3 inconsistentes · 2 duplicados" in cuerpo
    assert "Se detectaron 6 registros inconsistentes o duplicados. ¿Quieres revisarlos?" in cuerpo
    assert list(Arbol.todos.values_list("codigo", flat=True)) == ["S01-A004"]
    assert Arbol.todos.get().observaciones == "Ya registrado"


def test_el_lote_guarda_las_cuentas_el_hash_y_una_fila_por_registro(
    cliente_administrador, tmp_path, punto, usuario_administrador
):
    contenido = contenido_de(tmp_path, planilla_mixta(punto))

    subir(cliente_administrador, contenido)

    lote = LoteCarga.objects.get()
    assert lote.usuario == usuario_administrador
    assert lote.nombre_archivo == NOMBRE_ARCHIVO
    assert lote.sha256 == hashlib.sha256(contenido).hexdigest()
    assert lote.estado == ESTADO_LOTE_VALIDADO
    assert (lote.filas_leidas, lote.listos, lote.con_campos_vacios) == (7, 1, 1)
    assert (lote.inconsistentes, lote.duplicados) == (3, 2)
    assert lote.filas.count() == 7


def test_sin_problemas_el_resumen_no_alerta_y_ofrece_incorporar(
    cliente_administrador, tmp_path, punto
):
    lote = cargar(cliente_administrador, tmp_path, [fila_buena(punto, "S01-A001")])

    cuerpo = texto(cliente_administrador.get(url("resumen", lote)))

    assert "1 listos · 0 con campos vacíos · 0 inconsistentes · 0 duplicados" in cuerpo
    assert "¿Quieres revisarlos?" not in cuerpo
    assert "Incorporar los registros" in cuerpo


def test_la_alerta_tiene_los_botones_si_y_no_accesibles(lote_mixto, cliente_administrador):
    cuerpo = texto(cliente_administrador.get(url("resumen", lote_mixto)))

    assert 'role="alert"' in cuerpo
    assert url("revisar", lote_mixto) in cuerpo
    assert url("no", lote_mixto) in cuerpo
    assert ">Sí<" in cuerpo
    assert ">No<" in cuerpo


# --- Sí: revisar y guardar ------------------------------------------------------------


def test_la_revision_lista_los_problemas_con_el_campo_editable_y_conservar_sin_marcar(
    lote_mixto, cliente_administrador, punto
):
    ValorCatalogo.objects.create(campo="estado_general", valor="Bueno", explicacion="x")

    cuerpo = texto(cliente_administrador.get(url("revisar", lote_mixto)))

    pk = fila_del_lote(lote_mixto, "S01-A003").pk
    assert f'name="{PREFIJO_CAMPO_CARGA}{pk}-dap_cm"' in cuerpo
    assert 'type="number"' in cuerpo
    assert "DAP no es un número: «muerto»" in cuerpo
    assert f'name="{PREFIJO_CONSERVAR_CARGA}{pk}"' in cuerpo
    assert "checked" not in cuerpo
    assert "S01-A001" not in cuerpo  # el registro bueno no se pregunta


def test_el_campo_de_catalogo_se_elige_de_una_lista_con_los_valores_activos(
    cliente_administrador, tmp_path, punto
):
    ValorCatalogo.objects.create(campo="estado_general", valor="Regular", explicacion="x")
    ValorCatalogo.objects.create(campo="estado_general", valor="Bueno", explicacion="x", orden=2)
    ValorCatalogo.objects.create(
        campo="estado_general", valor="Retirado", explicacion="x", activo=False
    )
    lote = cargar(
        cliente_administrador,
        tmp_path,
        [fila_buena(punto, "S01-A001", estado_general="Excelente")],
    )

    cuerpo = texto(cliente_administrador.get(url("revisar", lote)))

    pk = fila_del_lote(lote, "S01-A001").pk
    assert f'<select name="{PREFIJO_CAMPO_CARGA}{pk}-estado_general"' in cuerpo
    assert ">Regular<" in cuerpo and ">Bueno<" in cuerpo
    assert "Retirado" not in cuerpo
    assert "Excelente" in cuerpo  # el valor que llegó se ve, para saber qué se cambia


def test_guardar_publica_lo_corregido_y_conservado_y_manda_a_revision_lo_que_sigue_mal(
    lote_mixto, cliente_administrador
):
    datos = {
        f"{PREFIJO_CONSERVAR_CARGA}{fila_del_lote(lote_mixto, 'S01-A003').pk}": "on",
        f"{PREFIJO_CAMPO_CARGA}{fila_del_lote(lote_mixto, 'S01-A003').pk}-dap_cm": "30.5",
        f"{PREFIJO_CONSERVAR_CARGA}{fila_del_lote(lote_mixto, 'S01-A004').pk}": "on",
        f"{PREFIJO_CONSERVAR_CARGA}{fila_del_lote(lote_mixto, 'S01-A005', 0).pk}": "on",
    }

    respuesta = cliente_administrador.post(url("revisar", lote_mixto), datos, follow=True)

    cuerpo = texto(respuesta)
    assert "3 publicados · 1 en revisión · 3 no incorporados · 0 de ejemplo sin cambios" in cuerpo
    estados = dict(Arbol.todos.values_list("codigo", "estado_registro"))
    assert estados == {
        "S01-A001": ESTADO_REGISTRO_PUBLICADO,
        "S01-A003": ESTADO_REGISTRO_PUBLICADO,
        "S01-A004": ESTADO_REGISTRO_EN_REVISION,
        "S01-A005": ESTADO_REGISTRO_PUBLICADO,
    }
    assert str(Arbol.todos.get(codigo="S01-A003").dap_cm) == "30.500"
    assert Arbol.todos.get(codigo="S01-A004").observaciones == (
        "Del archivo; DAP (cm) en planilla: muerto"
    )
    assert Arbol.todos.get(codigo="S01-A005").observaciones == TEXTOS_FILA_COMPLETA["observaciones"]
    for codigo in ("S01-A001", "S01-A003", "S01-A006"):
        assert codigo in cuerpo


def test_lo_que_no_se_conserva_no_entra_aunque_se_haya_corregido(lote_mixto, cliente_administrador):
    pk = fila_del_lote(lote_mixto, "S01-A006").pk
    datos = {f"{PREFIJO_CAMPO_CARGA}{pk}-dap_cm": "20"}

    cliente_administrador.post(url("revisar", lote_mixto), datos)

    assert not Arbol.todos.filter(codigo="S01-A006").exists()


def test_de_un_codigo_repetido_se_conserva_como_mucho_uno(lote_mixto, cliente_administrador):
    datos = {
        f"{PREFIJO_CONSERVAR_CARGA}{fila_del_lote(lote_mixto, 'S01-A005', 0).pk}": "on",
        f"{PREFIJO_CONSERVAR_CARGA}{fila_del_lote(lote_mixto, 'S01-A005', 1).pk}": "on",
    }

    respuesta = cliente_administrador.post(url("revisar", lote_mixto), datos)

    assert respuesta.status_code == 200
    assert "Conserva solo un registro del código S01-A005" in texto(respuesta)
    assert not Arbol.todos.filter(codigo="S01-A005").exists()
    lote_mixto.refresh_from_db()
    assert lote_mixto.estado == ESTADO_LOTE_VALIDADO


def test_se_puede_conservar_la_segunda_fila_de_un_codigo_repetido(
    lote_mixto, cliente_administrador
):
    pk = fila_del_lote(lote_mixto, "S01-A005", 1).pk

    cliente_administrador.post(url("revisar", lote_mixto), {f"{PREFIJO_CONSERVAR_CARGA}{pk}": "on"})

    assert Arbol.todos.get(codigo="S01-A005").observaciones == "Otro molle"


def test_solo_se_editan_los_campos_que_la_pantalla_ofrece(lote_mixto, cliente_administrador):
    pk = fila_del_lote(lote_mixto, "S01-A003").pk
    datos = {
        f"{PREFIJO_CONSERVAR_CARGA}{pk}": "on",
        f"{PREFIJO_CAMPO_CARGA}{pk}-dap_cm": "30",
        f"{PREFIJO_CAMPO_CARGA}{pk}-observaciones": "Cambiado a la fuerza",
    }

    cliente_administrador.post(url("revisar", lote_mixto), datos)

    assert Arbol.todos.get(codigo="S01-A003").observaciones == TEXTOS_FILA_COMPLETA["observaciones"]


def test_una_ubicacion_repetida_se_corrige_desde_la_revision(
    cliente_administrador, tmp_path, punto
):
    arbol_evaluado("S01-A009", nombre_comun="Molle", nombre_cientifico="Schinus molle")
    ya_registrado = Arbol.todos.get(codigo="S01-A009").ubicacion
    lote = cargar(
        cliente_administrador,
        tmp_path,
        [fila_buena((ya_registrado.x, ya_registrado.y), "S01-A001")],
    )
    assert lote.duplicados == 1
    pk = fila_del_lote(lote, "S01-A001").pk
    datos = {
        f"{PREFIJO_CONSERVAR_CARGA}{pk}": "on",
        f"{PREFIJO_CAMPO_CARGA}{pk}-utm_este_m": str(punto[0] + 3),
        f"{PREFIJO_CAMPO_CARGA}{pk}-utm_norte_m": str(punto[1]),
    }

    cliente_administrador.post(url("revisar", lote), datos)

    assert Arbol.todos.get(codigo="S01-A001").estado_registro == ESTADO_REGISTRO_PUBLICADO


def test_un_duplicado_de_ubicacion_conservado_sin_corregir_entra_en_revision(
    cliente_administrador, tmp_path, sectores
):
    arbol_evaluado("S01-A009", nombre_comun="Molle", nombre_cientifico="Schinus molle")
    ya_registrado = Arbol.todos.get(codigo="S01-A009").ubicacion
    lote = cargar(
        cliente_administrador,
        tmp_path,
        [fila_buena((ya_registrado.x, ya_registrado.y), "S01-A001")],
    )
    pk = fila_del_lote(lote, "S01-A001").pk

    cliente_administrador.post(url("revisar", lote), {f"{PREFIJO_CONSERVAR_CARGA}{pk}": "on"})

    nuevo = Arbol.todos.get(codigo="S01-A001")
    assert nuevo.estado_registro == ESTADO_REGISTRO_EN_REVISION
    assert "misma ubicación y misma especie que S01-A009" in nuevo.motivos_revision


def test_un_ejemplo_no_se_pisa_con_una_fila_incompleta_y_se_cuenta(
    cliente_administrador, tmp_path, punto
):
    arbol_de_ejemplo("S01-A001", observaciones="Del ejemplo")
    lote = cargar(
        cliente_administrador,
        tmp_path,
        [fila(codigo="S01-A001", observaciones="Incompleto"), fila_buena(punto, "S01-A002", 2)],
    )

    pk = fila_del_lote(lote, "S01-A001").pk

    respuesta = cliente_administrador.post(
        url("revisar", lote), {f"{PREFIJO_CONSERVAR_CARGA}{pk}": "on"}, follow=True
    )

    assert "1 publicados · 0 en revisión · 0 no incorporados · 1 de ejemplo sin cambios" in texto(
        respuesta
    )
    ejemplo = Arbol.todos.get(codigo="S01-A001")
    assert (ejemplo.demo, ejemplo.observaciones) == (True, "Del ejemplo")


def test_una_fila_completa_reemplaza_al_ejemplo(cliente_administrador, tmp_path, punto):
    arbol_de_ejemplo("S01-A001", observaciones="Del ejemplo")
    lote = cargar(cliente_administrador, tmp_path, [fila_buena(punto, "S01-A001")])

    cliente_administrador.post(url("confirmar", lote))

    real = Arbol.todos.get(codigo="S01-A001")
    assert (real.demo, real.observaciones) == (False, TEXTOS_FILA_COMPLETA["observaciones"])


# --- No: segunda alerta y confirmar ------------------------------------------------------------


def test_la_segunda_alerta_dice_que_pasa_con_cada_codigo(lote_mixto, cliente_administrador):
    cuerpo = texto(cliente_administrador.get(url("no", lote_mixto)))

    assert "El árbol S01-A003 no está en el registro y no se incorporará" in cuerpo
    assert "El árbol S01-A006 no está en el registro y no se incorporará" in cuerpo
    assert cuerpo.count("El árbol S01-A005 no está en el registro y no se incorporará") == 1
    assert "S01-A004 no se actualiza; se mantiene lo que había" in cuerpo
    assert "El árbol S01-A004" not in cuerpo
    assert "S01-A001" not in cuerpo
    assert "Confirmar" in cuerpo


def test_confirmar_sin_revisar_incorpora_solo_los_buenos_y_deja_lo_demas_como_estaba(
    lote_mixto, cliente_administrador
):
    respuesta = cliente_administrador.post(url("confirmar", lote_mixto), follow=True)

    assert "1 publicados · 0 en revisión · 6 no incorporados · 0 de ejemplo sin cambios" in texto(
        respuesta
    )
    assert sorted(Arbol.todos.values_list("codigo", flat=True)) == [
        "S01-A001",
        "S01-A004",
    ]
    previo = Arbol.todos.get(codigo="S01-A004")
    assert (previo.observaciones, previo.estado_registro) == (
        "Ya registrado",
        ESTADO_REGISTRO_PUBLICADO,
    )


def test_confirmar_cierra_el_lote_y_borra_sus_filas(lote_mixto, cliente_administrador):
    cliente_administrador.post(url("confirmar", lote_mixto))

    lote_mixto.refresh_from_db()
    assert lote_mixto.estado == ESTADO_LOTE_CONFIRMADO
    assert FilaCarga.objects.filter(lote=lote_mixto).count() == 0
    assert lote_mixto.filas_leidas == 7  # la bitácora conserva las cuentas


def test_guardar_tambien_borra_las_filas_del_lote(lote_mixto, cliente_administrador):
    cliente_administrador.post(url("revisar", lote_mixto), {})

    lote_mixto.refresh_from_db()
    assert lote_mixto.estado == ESTADO_LOTE_CONFIRMADO
    assert not lote_mixto.filas.exists()


def test_un_lote_confirmado_no_se_confirma_dos_veces(lote_mixto, cliente_administrador):
    cliente_administrador.post(url("confirmar", lote_mixto))
    antes = Arbol.todos.count()

    respuesta = cliente_administrador.post(url("confirmar", lote_mixto), follow=True)

    assert "Esa carga ya no está pendiente" in texto(respuesta)
    assert Arbol.todos.count() == antes


def test_cancelar_no_guarda_nada_y_borra_las_filas(lote_mixto, cliente_administrador):
    respuesta = cliente_administrador.post(url("cancelar", lote_mixto), follow=True)

    assert "Carga cancelada: no se guardó nada." in texto(respuesta)
    lote_mixto.refresh_from_db()
    assert lote_mixto.estado == ESTADO_LOTE_CANCELADO
    assert not lote_mixto.filas.exists()
    assert list(Arbol.todos.values_list("codigo", flat=True)) == ["S01-A004"]


# --- vacíos: son un problema y una celda vacía no borra un dato que ya existe -----------------


def foto_de_la_bd():
    """Todos los árboles con todos sus valores, para comprobar que la BD quedó igual."""
    return list(Arbol.todos.order_by("codigo").values())


def fila_vacia_de_altura(punto, codigo, desplazamiento_m=0):
    return fila_buena(punto, codigo, desplazamiento_m, altura_total_m=None)


def test_la_alerta_cuenta_los_vacios_junto_a_inconsistentes_y_duplicados(
    cliente_administrador, tmp_path, punto
):
    lote = cargar(
        cliente_administrador,
        tmp_path,
        [
            fila(codigo="S01-A001"),
            fila_buena(punto, "S01-A002", 1, dap_cm="muerto"),
            fila_buena(punto, "S01-A003", 2),
            fila_buena(punto, "S01-A003", 3),
        ],
    )

    cuerpo = texto(cliente_administrador.get(url("resumen", lote)))

    assert "Se detectaron 4 registros inconsistentes o duplicados. ¿Quieres revisarlos?" in cuerpo


def test_con_no_un_vacio_de_un_codigo_existente_no_cambia_nada(
    cliente_administrador, tmp_path, punto
):
    arbol_evaluado("S01-A001", altura_total_m=Decimal("2.85"))
    lote = cargar(cliente_administrador, tmp_path, [fila_vacia_de_altura(punto, "S01-A001")])
    antes = foto_de_la_bd()

    assert "S01-A001 no se actualiza; se mantiene lo que había" in texto(
        cliente_administrador.get(url("no", lote))
    )
    cliente_administrador.post(url("confirmar", lote))

    assert foto_de_la_bd() == antes
    arbol = Arbol.todos.get(codigo="S01-A001")
    assert (arbol.altura_total_m, arbol.estado_registro) == (
        Decimal("2.85"),
        ESTADO_REGISTRO_PUBLICADO,
    )


def test_con_no_un_vacio_de_un_codigo_nuevo_no_se_incorpora(cliente_administrador, tmp_path, punto):
    lote = cargar(cliente_administrador, tmp_path, [fila_vacia_de_altura(punto, "S01-A001")])

    cuerpo = texto(cliente_administrador.get(url("no", lote)))
    cliente_administrador.post(url("confirmar", lote))

    assert "El árbol S01-A001 no está en el registro y no se incorporará" in cuerpo
    assert not Arbol.todos.filter(codigo="S01-A001").exists()


def test_con_si_el_vacio_aparece_en_la_revision_y_corregido_se_publica(
    cliente_administrador, tmp_path, punto
):
    lote = cargar(cliente_administrador, tmp_path, [fila_vacia_de_altura(punto, "S01-A001")])
    pk = fila_del_lote(lote, "S01-A001").pk

    cuerpo = texto(cliente_administrador.get(url("revisar", lote)))
    assert f'name="{PREFIJO_CAMPO_CARGA}{pk}-altura_total_m"' in cuerpo
    assert f'name="{PREFIJO_CONSERVAR_CARGA}{pk}"' in cuerpo
    assert "checked" not in cuerpo

    datos = {
        f"{PREFIJO_CONSERVAR_CARGA}{pk}": "on",
        f"{PREFIJO_CAMPO_CARGA}{pk}-altura_total_m": "6.2",
    }
    cliente_administrador.post(url("revisar", lote), datos)

    arbol = Arbol.todos.get(codigo="S01-A001")
    assert (arbol.altura_total_m, arbol.estado_registro) == (
        Decimal("6.2"),
        ESTADO_REGISTRO_PUBLICADO,
    )


def test_con_si_un_vacio_sin_corregir_mantiene_el_dato_que_ya_habia_y_publica(
    cliente_administrador, tmp_path, punto
):
    arbol_evaluado("S01-A001", altura_total_m=Decimal("2.85"), observaciones="Ya registrado")
    lote = cargar(cliente_administrador, tmp_path, [fila_vacia_de_altura(punto, "S01-A001")])
    pk = fila_del_lote(lote, "S01-A001").pk

    cliente_administrador.post(url("revisar", lote), {f"{PREFIJO_CONSERVAR_CARGA}{pk}": "on"})

    arbol = Arbol.todos.get(codigo="S01-A001")
    assert arbol.altura_total_m == Decimal("2.85")
    assert (
        arbol.observaciones == TEXTOS_FILA_COMPLETA["observaciones"]
    )  # lo que la fila trae se actualiza
    assert (arbol.estado_registro, arbol.motivos_revision) == (ESTADO_REGISTRO_PUBLICADO, "")


def test_un_vacio_sin_corregir_sobre_un_dato_incompleto_queda_en_revision(
    cliente_administrador, tmp_path, punto
):
    arbol_evaluado("S01-A001", altura_total_m=None)
    lote = cargar(cliente_administrador, tmp_path, [fila_vacia_de_altura(punto, "S01-A001")])
    pk = fila_del_lote(lote, "S01-A001").pk

    cliente_administrador.post(url("revisar", lote), {f"{PREFIJO_CONSERVAR_CARGA}{pk}": "on"})

    arbol = Arbol.todos.get(codigo="S01-A001")
    assert arbol.estado_registro == ESTADO_REGISTRO_EN_REVISION
    assert "Falta el dato «Altura total»" in arbol.motivos_revision


def test_la_planilla_de_tres_filas_danadas_con_no_deja_la_bd_identica(
    cliente_administrador, tmp_path, punto
):
    arbol_evaluado("S01-A001")
    arbol_evaluado("S01-A005", altura_total_m=Decimal("2.85"))
    arbol_evaluado("S01-A006")
    arbol_evaluado("S01-A008")
    lote = cargar(
        cliente_administrador,
        tmp_path,
        [
            fila_buena(punto, "S01-A001", 1),
            fila_vacia_de_altura(punto, "S01-A005", 2),
            fila_buena(punto, "S01-A006", 3, dap_cm="muerto"),
            fila_buena(punto, "S01-A008", 4),
            fila_buena(punto, "S01-A008", 5, dap_cm=69.3),
        ],
    )
    antes = foto_de_la_bd()

    cuerpo = texto(cliente_administrador.get(url("no", lote)))
    cliente_administrador.post(url("confirmar", lote))

    for codigo in ("S01-A005", "S01-A006", "S01-A008"):
        assert f"{codigo} no se actualiza; se mantiene lo que había" in cuerpo
    despues = foto_de_la_bd()
    por_codigo = {a["codigo"]: a for a in despues}
    esperados = {a["codigo"]: a for a in antes}
    for codigo in ("S01-A005", "S01-A006", "S01-A008"):
        assert por_codigo[codigo] == esperados[codigo]
    assert por_codigo["S01-A001"] != esperados["S01-A001"]  # la fila buena sí se actualiza
    assert por_codigo["S01-A001"]["estado_registro"] == ESTADO_REGISTRO_PUBLICADO
    assert len(despues) == len(antes)


# --- archivos que no sirven ------------------------------------------------------------


def rechazada(cliente, contenido, nombre=NOMBRE_ARCHIVO):
    respuesta = subir(cliente, contenido, nombre)
    assert respuesta.status_code == 200
    assert not LoteCarga.objects.exists()
    return texto(respuesta)


def test_un_archivo_que_no_es_xlsx_se_rechaza_con_mensaje(cliente_administrador):
    cuerpo = rechazada(cliente_administrador, b"codigo,sector\n", "planilla.csv")

    assert "El archivo debe ser una planilla de Excel (.xlsx)." in cuerpo


def test_un_xlsx_dañado_se_rechaza_con_mensaje(cliente_administrador):
    cuerpo = rechazada(cliente_administrador, b"no soy un excel")

    assert "No se pudo abrir" in cuerpo


def test_un_archivo_demasiado_grande_se_rechaza_con_mensaje(
    cliente_administrador, tmp_path, punto, monkeypatch
):
    monkeypatch.setattr("apps.censo.admin_carga.TAMANO_MAXIMO_PLANILLA_BYTES", 10)
    contenido = contenido_de(tmp_path, [fila_buena(punto, "S01-A001")])

    cuerpo = rechazada(cliente_administrador, contenido)

    assert "El archivo pesa más de" in cuerpo


def test_una_hoja_con_demasiadas_filas_se_rechaza_con_mensaje(
    cliente_administrador, tmp_path, monkeypatch
):
    monkeypatch.setattr("apps.censo.admin_carga.FILAS_MAXIMAS_PLANILLA", 2)
    contenido = contenido_de(tmp_path, [fila(), fila(), fila()])

    cuerpo = rechazada(cliente_administrador, contenido)

    assert "La hoja declara 3 filas; el máximo es 2." in cuerpo


def test_un_libro_sin_la_hoja_de_la_brigada_se_rechaza_con_mensaje(cliente_administrador):
    libro = Workbook()
    libro.active.title = "Otra"
    memoria = BytesIO()
    libro.save(memoria)

    cuerpo = rechazada(cliente_administrador, memoria.getvalue())

    assert "La planilla no tiene la hoja «Registro_Campo»." in cuerpo


def test_una_planilla_con_latitud_y_longitud_en_vez_de_utm_se_rechaza_nombrando_las_columnas(
    cliente_administrador, tmp_path, sectores
):
    contenido = contenido_de(tmp_path, [fila()], sin_columnas=["UTM Este (m)", "UTM Norte (m)"])

    cuerpo = rechazada(cliente_administrador, contenido)

    assert "Faltan columnas en la planilla: UTM Este (m), UTM Norte (m)" in cuerpo


def test_subir_sin_elegir_archivo_avisa(cliente_administrador):
    respuesta = cliente_administrador.post(reverse(URL_SUBIR), {})

    assert "Elige el archivo .xlsx de la brigada." in texto(respuesta)


# --- seguridad y permisos ------------------------------------------------------------


@pytest.fixture
def cliente_otro_editor(db):
    return cliente_de(usuario_con_rol("otro-editor", NOMBRE_ROL_EDITOR))


@pytest.mark.parametrize("pagina", ["resumen", "revisar", "no"])
def test_otro_usuario_no_ve_el_lote_de_otro(lote_mixto, cliente_otro_editor, pagina):
    assert cliente_otro_editor.get(url(pagina, lote_mixto)).status_code == 403


@pytest.mark.parametrize("accion", ["confirmar", "revisar", "cancelar"])
def test_otro_usuario_no_confirma_ni_cancela_el_lote(lote_mixto, cliente_otro_editor, accion):
    respuesta = cliente_otro_editor.post(url(accion, lote_mixto), {})

    assert respuesta.status_code == 403
    lote_mixto.refresh_from_db()
    assert lote_mixto.estado == ESTADO_LOTE_VALIDADO
    assert lote_mixto.filas.count() == 7
    assert list(Arbol.todos.values_list("codigo", flat=True)) == ["S01-A004"]


@pytest.mark.parametrize("rol", ["cliente_administrador", "cliente_editor"])
def test_administrador_y_editor_cargan_la_planilla(rol, request, tmp_path, punto):
    cliente = request.getfixturevalue(rol)

    assert cliente.get(reverse(URL_SUBIR)).status_code == 200
    assert cargar(cliente, tmp_path, [fila_buena(punto, "S01-A001")]).estado == "validado"


def test_quien_no_tiene_el_permiso_no_ve_ni_sube(db, tmp_path):
    usuario = User.objects.create_user("sin-permiso", password=CLAVE_PRUEBA, is_staff=True)
    cliente = cliente_de(usuario)

    assert cliente.get(reverse(URL_SUBIR)).status_code == 403
    assert subir(cliente, b"x").status_code == 403
    assert not LoteCarga.objects.exists()


def test_el_formulario_exige_el_token_csrf(lote_mixto, usuario_administrador):
    cliente = Client(enforce_csrf_checks=True)
    cliente.force_login(usuario_administrador)

    assert cliente.post(url("confirmar", lote_mixto), {}).status_code == 403
    assert cliente.post(reverse(URL_SUBIR), {}).status_code == 403
    lote_mixto.refresh_from_db()
    assert lote_mixto.estado == ESTADO_LOTE_VALIDADO


# --- lotes abandonados ------------------------------------------------------------


def test_al_entrar_se_purgan_los_lotes_vencidos_y_se_dejan_los_vigentes(
    lote_mixto, cliente_administrador, usuario_administrador
):
    vencido = LoteCarga.objects.create(
        usuario=usuario_administrador,
        nombre_archivo="viejo.xlsx",
        sha256="0" * 64,
        fecha=timezone.now() - timedelta(hours=HORAS_VIDA_LOTE_CARGA + 1),
    )
    FilaCarga.objects.create(lote=vencido, numero_fila=2, codigo="S01-A001", datos={})

    cliente_administrador.get(reverse(URL_SUBIR))

    vencido.refresh_from_db()
    assert vencido.estado == ESTADO_LOTE_CANCELADO
    assert not vencido.filas.exists()
    lote_mixto.refresh_from_db()
    assert lote_mixto.estado == ESTADO_LOTE_VALIDADO
    assert lote_mixto.filas.count() == 7


def test_un_lote_vencido_ya_no_se_puede_confirmar(lote_mixto, cliente_administrador):
    LoteCarga.objects.update(fecha=timezone.now() - timedelta(hours=HORAS_VIDA_LOTE_CARGA + 1))
    cliente_administrador.get(reverse(URL_SUBIR))

    respuesta = cliente_administrador.post(url("confirmar", lote_mixto), follow=True)

    assert "Esa carga ya no está pendiente" in texto(respuesta)
    assert list(Arbol.todos.values_list("codigo", flat=True)) == ["S01-A004"]


# --- el servicio ------------------------------------------------------------


def test_leer_acepta_una_ruta_y_bytes_y_evaluar_no_escribe(tmp_path, punto):
    ruta = crear_planilla(tmp_path / NOMBRE_ARCHIVO, planilla_mixta(punto))

    desde_ruta = leer(ruta)
    desde_bytes = leer(ruta.read_bytes(), nombre_archivo="otro.xlsx")
    evaluacion = evaluar(desde_bytes)

    assert [numero for numero, _ in desde_ruta.filas] == [numero for numero, _ in desde_bytes.filas]
    assert desde_bytes.nombre_archivo == "otro.xlsx"
    assert [f.clasificacion for f in evaluacion.filas] == [
        CLASIFICACION_LISTO,
        CLASIFICACION_CAMPOS_VACIOS,
        CLASIFICACION_INCONSISTENTE,
        CLASIFICACION_INCONSISTENTE,
        CLASIFICACION_DUPLICADO,
        CLASIFICACION_DUPLICADO,
        CLASIFICACION_INCONSISTENTE,
    ]
    assert Arbol.todos.count() == 0


def test_el_selector_de_catalogo_trae_solo_los_valores_activos_por_campo(db):
    ValorCatalogo.objects.create(campo="origen", valor="Nativa", explicacion="x", orden=1)
    ValorCatalogo.objects.create(campo="origen", valor="Introducida", explicacion="x", orden=2)
    ValorCatalogo.objects.create(campo="origen", valor="Vieja", explicacion="x", activo=False)

    activos = valores_activos_del_catalogo()

    assert activos["origen"] == ["Nativa", "Introducida"]
    assert activos["estado_copa"] == []


def test_cancelar_un_lote_ya_confirmado_no_lo_pisa_y_avisa(lote_mixto, cliente_administrador):
    cliente_administrador.post(url("confirmar", lote_mixto))
    resultado = LoteCarga.objects.get(pk=lote_mixto.pk).resultado

    respuesta = cliente_administrador.post(url("cancelar", lote_mixto), follow=True)

    assert "Esa carga ya no está pendiente" in texto(respuesta)
    lote_mixto.refresh_from_db()
    assert lote_mixto.estado == ESTADO_LOTE_CONFIRMADO
    assert lote_mixto.resultado == resultado


def test_confirmar_un_lote_ya_cancelado_no_lo_pisa_y_avisa(lote_mixto, cliente_administrador):
    cliente_administrador.post(url("cancelar", lote_mixto))

    respuesta = cliente_administrador.post(url("confirmar", lote_mixto), follow=True)

    assert "Esa carga ya no está pendiente" in texto(respuesta)
    lote_mixto.refresh_from_db()
    assert lote_mixto.estado == ESTADO_LOTE_CANCELADO
    assert list(Arbol.todos.values_list("codigo", flat=True)) == ["S01-A004"]
