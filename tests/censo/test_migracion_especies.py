"""Migraciones 0010 a 0012: del texto del árbol a especies, catálogo y brigada, y de vuelta.

Se ejerce de verdad: se vuelve al estado 0009 dentro de la transacción del test, se crean datos con
el esquema viejo, se migra hacia adelante y se mira el resultado; después se vuelve atrás y los
textos tienen que quedar como estaban. Todo se deshace al terminar.
"""

from datetime import UTC, datetime

import pytest
from django.contrib.gis.geos import Polygon
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from config.constantes.catalogos import GRUPOS_INICIALES_DE_BRIGADA, NOMBRE_BRIGADA_INICIAL
from config.constantes.general import SRID_UTM_CENSO

ANTES = [("censo", "0009_carga_de_planilla")]
PARCIAL = [("censo", "0010_especies_brigadas_y_catalogo")]
CON_DATOS = [("censo", "0011_datos_de_especies_brigadas_y_catalogo")]
SIN_TEXTOS = [("censo", "0012_quita_textos_y_fichas")]
FUENTE = "Prueba de la migración"
FUENTE_FICHA = "Fuente de la ficha"
ESTADOS = (
    "tipo_individuo",
    "identificacion",
    "condicion_conservacion",
    "estado_general",
    "estado_copa",
    "tronco_danos",
    "raices_base",
    "interferencia_entorno",
)


def _migrar_a(objetivo):
    ejecutor = MigrationExecutor(connection)
    ejecutor.migrate(objetivo)
    return MigrationExecutor(connection).loader.project_state(objetivo).apps


@pytest.fixture
def esquema_viejo(db):
    """Las apps del estado 0009; al terminar, el esquema vuelve al último estado."""
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    apps_viejas = _migrar_a(ANTES)
    yield apps_viejas
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    _migrar_a(MigrationExecutor(connection).loader.graph.leaf_nodes())


def _sembrar_catalogo(apps_viejas):
    Valor = apps_viejas.get_model("censo", "ValorCatalogo")
    for campo, valor in [
        ("origen", "Nativa"),
        ("origen", "Introducida"),
        ("estado_general", "Bueno"),
        ("estado_copa", "Buena"),
    ]:
        Valor.objects.create(campo=campo, valor=valor, explicacion="x")


def _sembrar_ficha(apps_viejas, nombre_cientifico, nombre_comun, publicada=False):
    Ficha = apps_viejas.get_model("censo", "FichaEspecie")
    Historial = apps_viejas.get_model("censo", "HistoricalFichaEspecie")
    campos = {
        "nombre_cientifico": nombre_cientifico,
        "nombre_comun": nombre_comun,
        "alias": "",
        "beneficios": "Da sombra",
        "dato_curioso": None,
        "cuidados": None,
    }
    ficha = Ficha.objects.create(**campos, fuente=FUENTE_FICHA, publicada=publicada)
    Historial.objects.create(
        id=ficha.pk,
        **campos,
        fuente=FUENTE_FICHA,
        publicada=publicada,
        history_date=datetime(2026, 10, 1, tzinfo=UTC),
        history_type="+",
    )
    return ficha


def _sembrar_arbol(apps_viejas, codigo, **textos):
    Sector = apps_viejas.get_model("censo", "Sector")
    Arbol = apps_viejas.get_model("censo", "Arbol")
    cuadrado = Polygon.from_bbox((300000, 8673000, 300100, 8673100))
    cuadrado.srid = SRID_UTM_CENSO
    sector, _ = Sector.objects.get_or_create(
        id=1, defaults={"nombre": "Sector 1", "geom": cuadrado, "fuente": FUENTE}
    )
    return Arbol.objects.create(codigo=codigo, sector=sector, fuente=FUENTE, **textos)


def _sembrar_historial(apps_viejas, arbol, **cambios):
    """Un registro del historial del árbol (copia de sus columnas) con los textos que se den."""
    Historial = apps_viejas.get_model("censo", "HistoricalArbol")
    Arbol = apps_viejas.get_model("censo", "Arbol")
    nombres = {campo.attname for campo in Historial._meta.concrete_fields}
    copia = {
        campo.attname: getattr(arbol, campo.attname)
        for campo in Arbol._meta.concrete_fields
        if campo.attname in nombres
    }
    return Historial.objects.create(
        **{**copia, **cambios},
        history_date=datetime(2026, 10, 2, tzinfo=UTC),
        history_type="~",
    )


def _textos_del_historial(apps, columnas):
    Historial = apps.get_model("censo", "HistoricalArbol")
    return {
        registro.history_id: {columna: getattr(registro, columna) for columna in columnas}
        for registro in Historial.objects.order_by("history_id")
    }


def _textos_de(Arbol, columnas):
    return {
        arbol.codigo: {columna: getattr(arbol, columna) for columna in columnas}
        for arbol in Arbol.objects.order_by("codigo")
    }


COLUMNAS_DE_TEXTO = (
    "nombre_comun",
    "nombre_cientifico",
    "origen",
    "brigada",
    *ESTADOS,
)


@pytest.fixture
def datos_viejos(esquema_viejo):
    """Los casos: alias, especie sin ficha, estado fuera del catálogo y textos sueltos."""
    _sembrar_catalogo(esquema_viejo)
    _sembrar_ficha(esquema_viejo, "Schinus molle", "Molle")
    _sembrar_ficha(esquema_viejo, "Roystonea regia", "Palma real", publicada=True)
    _sembrar_arbol(
        esquema_viejo,
        "S01-A001",
        nombre_comun="Molle",
        nombre_cientifico="Schinus molle",
        origen="Nativa",
        estado_general="Bueno",
        brigada="Brigada A",
    )
    _sembrar_arbol(  # por alias: «Schinus Molle» y «Schinus» se siembran como alias
        esquema_viejo,
        "S01-A002",
        nombre_comun="Molle",
        nombre_cientifico="Schinus",
        origen="Nativa",
        estado_general="bueno",
        estado_copa="Buena",
        brigada="Sopita",
    )
    _sembrar_arbol(  # una especie sin ficha: se crea con el nombre tal cual, por revisar
        esquema_viejo,
        "S01-A003",
        nombre_comun="Ficus",
        nombre_cientifico="Ficus benjamina",
        origen="Introducida",
        estado_general="Excelente",  # fuera del catálogo
        tronco_danos="Sin daño aparente",  # el campo no tiene catálogo cargado
    )
    _sembrar_arbol(esquema_viejo, "S01-A004", nombre_comun="Palma real", brigada=None)
    Arbol = esquema_viejo.get_model("censo", "Arbol")
    primero, segundo, tercero = (
        Arbol.objects.get(codigo=c) for c in ("S01-A001", "S01-A002", "S01-A003")
    )
    _sembrar_historial(esquema_viejo, primero)
    _sembrar_historial(esquema_viejo, primero, estado_general="Regular", brigada="Zapato")
    _sembrar_historial(esquema_viejo, segundo, nombre_cientifico="Schinus Molle", origen="Nativa")
    _sembrar_historial(
        esquema_viejo, tercero, estado_general="Mala", nombre_cientifico="Ficus raro"
    )
    return esquema_viejo


def test_las_fichas_pasan_a_especies_con_su_historial(datos_viejos):
    apps_nuevas = _migrar_a(CON_DATOS)

    Especie = apps_nuevas.get_model("censo", "Especie")
    molle = Especie.objects.get(nombre_cientifico="Schinus molle")
    assert (molle.nombre_comun, molle.fuente_ficha, molle.ficha_publicada) == (
        "Molle",
        FUENTE_FICHA,
        False,
    )
    assert molle.beneficios == "Da sombra"
    assert Especie.objects.get(nombre_cientifico="Roystonea regia").ficha_publicada is True
    historial = apps_nuevas.get_model("censo", "HistoricalEspecie").objects.filter(id=molle.pk)
    assert [(h.nombre_cientifico, h.fuente_ficha, h.history_type) for h in historial] == [
        ("Schinus molle", FUENTE_FICHA, "+")
    ]


def test_los_alias_iniciales_resuelven_la_especie_de_cada_arbol(datos_viejos):
    apps_nuevas = _migrar_a(CON_DATOS)

    Arbol = apps_nuevas.get_model("censo", "Arbol")
    Especie = apps_nuevas.get_model("censo", "Especie")
    molle = Especie.objects.get(nombre_cientifico="Schinus molle")
    assert "Schinus" in molle.alias.split("\n")
    por_alias = Arbol.objects.get(codigo="S01-A002")
    assert por_alias.especie_id == molle.pk
    assert por_alias.valores_originales["nombre_cientifico"] == "Schinus"
    assert "nombre_cientifico" not in Arbol.objects.get(codigo="S01-A001").valores_originales


def test_un_nombre_sin_especie_crea_la_especie_por_revisar_y_nada_mas(datos_viejos):
    apps_nuevas = _migrar_a(CON_DATOS)

    Especie = apps_nuevas.get_model("censo", "Especie")
    ficus = Especie.objects.get(nombre_cientifico="Ficus benjamina")
    assert (ficus.nombre_comun, ficus.revisada, ficus.fuente_ficha) == ("Ficus", False, "")
    assert ficus.origen.valor == "Introducida"
    assert apps_nuevas.get_model("censo", "Arbol").objects.get(codigo="S01-A003").especie == ficus
    assert Especie.objects.filter(revisada=False).count() == 1
    assert Especie.objects.count() == 3  # 2 fichas + 1 por revisar; nada inventado


def test_un_arbol_sin_nombre_cientifico_toma_la_especie_por_su_nombre_comun(datos_viejos):
    apps_nuevas = _migrar_a(CON_DATOS)

    arbol = apps_nuevas.get_model("censo", "Arbol").objects.get(codigo="S01-A004")
    assert arbol.especie.nombre_cientifico == "Roystonea regia"
    assert arbol.valores_originales == {"nombre_cientifico": None}


def test_el_origen_pasa_a_la_especie(datos_viejos):
    apps_nuevas = _migrar_a(CON_DATOS)

    Especie = apps_nuevas.get_model("censo", "Especie")
    assert Especie.objects.get(nombre_cientifico="Schinus molle").origen.valor == "Nativa"
    assert Especie.objects.get(nombre_cientifico="Roystonea regia").origen is None


def test_los_estados_pasan_al_catalogo_y_el_que_no_esta_queda_en_los_originales(datos_viejos):
    apps_nuevas = _migrar_a(CON_DATOS)

    Arbol = apps_nuevas.get_model("censo", "Arbol")
    bueno = Arbol.objects.get(codigo="S01-A001")
    assert bueno.estado_general.valor == "Bueno"
    normalizado = Arbol.objects.get(codigo="S01-A002")
    assert normalizado.estado_general.valor == "Bueno"
    assert normalizado.valores_originales["estado_general"] == "bueno"
    fuera = Arbol.objects.get(codigo="S01-A003")
    assert fuera.estado_general is None
    assert fuera.valores_originales["estado_general"] == "Excelente"
    assert fuera.valores_originales["tronco_danos"] == "Sin daño aparente"


def test_la_brigada_inicial_con_sus_grupos_y_los_arboles_sin_grupo(datos_viejos):
    apps_nuevas = _migrar_a(CON_DATOS)

    Grupo = apps_nuevas.get_model("censo", "GrupoBrigada")
    Arbol = apps_nuevas.get_model("censo", "Arbol")
    assert apps_nuevas.get_model("censo", "Brigada").objects.get().nombre == NOMBRE_BRIGADA_INICIAL
    assert set(Grupo.objects.values_list("nombre", flat=True)) == set(GRUPOS_INICIALES_DE_BRIGADA)
    assert Arbol.objects.get(codigo="S01-A001").grupo is None
    assert Arbol.objects.get(codigo="S01-A001").valores_originales["brigada"] == "Brigada A"
    assert Arbol.objects.get(codigo="S01-A002").grupo.nombre == "Sopita"


def test_una_especie_con_origenes_distintos_detiene_la_migracion_y_los_lista(esquema_viejo):
    _sembrar_catalogo(esquema_viejo)
    _sembrar_ficha(esquema_viejo, "Roystonea regia", "Palma real")
    _sembrar_arbol(esquema_viejo, "S01-A001", nombre_cientifico="Roystonea regia", origen="Nativa")
    _sembrar_arbol(
        esquema_viejo, "S01-A002", nombre_cientifico="Roystonea regia", origen="Introducida"
    )

    with pytest.raises(RuntimeError) as error:
        _migrar_a(CON_DATOS)

    mensaje = str(error.value)
    assert "Roystonea regia" in mensaje
    assert "S01-A001 (Nativa)" in mensaje and "S01-A002 (Introducida)" in mensaje
    # La 0010 quedó aplicada y la 0011 no: se quitan los árboles en conflicto para que el esquema
    # pueda volver al último estado al terminar la prueba.
    ejecutor = MigrationExecutor(connection)
    apps_0010 = ejecutor.loader.project_state(PARCIAL).apps
    apps_0010.get_model("censo", "Arbol").objects.all().delete()


def test_el_historial_del_arbol_pasa_a_las_tablas_igual_que_el_arbol(datos_viejos):
    apps_nuevas = _migrar_a(CON_DATOS)

    registros = list(
        apps_nuevas.get_model("censo", "HistoricalArbol").objects.order_by("history_id")
    )
    assert len(registros) == 4
    molle = apps_nuevas.get_model("censo", "Especie").objects.get(nombre_cientifico="Schinus molle")
    primero, cambiado, por_alias, sin_especie = registros
    assert (primero.especie_id, primero.estado_general.valor) == (molle.pk, "Bueno")
    assert primero.valores_originales == {"brigada": "Brigada A"}
    assert cambiado.estado_general is None
    assert cambiado.valores_originales == {"brigada": "Zapato", "estado_general": "Regular"}
    assert cambiado.grupo.nombre == "zapato"
    assert por_alias.especie_id == molle.pk
    assert por_alias.valores_originales["nombre_cientifico"] == "Schinus Molle"
    assert sin_especie.especie is None
    assert sin_especie.valores_originales["nombre_cientifico"] == "Ficus raro"
    assert sin_especie.valores_originales["estado_general"] == "Mala"


def test_la_reversa_reescribe_los_textos_del_historial_tal_como_estaban(datos_viejos):
    columnas = ("history_type", *COLUMNAS_DE_TEXTO)
    antes = _textos_del_historial(datos_viejos, columnas)
    _migrar_a(SIN_TEXTOS)

    apps_viejas = _migrar_a(ANTES)

    assert _textos_del_historial(apps_viejas, columnas) == antes


def test_la_reversa_reescribe_los_textos_y_las_fichas_tal_como_estaban(datos_viejos):
    Arbol = datos_viejos.get_model("censo", "Arbol")
    antes = _textos_de(Arbol, COLUMNAS_DE_TEXTO)
    _migrar_a(SIN_TEXTOS)

    apps_viejas = _migrar_a(ANTES)

    despues = _textos_de(apps_viejas.get_model("censo", "Arbol"), COLUMNAS_DE_TEXTO)
    assert despues == antes
    Ficha = apps_viejas.get_model("censo", "FichaEspecie")
    assert {(f.nombre_cientifico, f.publicada) for f in Ficha.objects.all()} == {
        ("Schinus molle", False),
        ("Roystonea regia", True),
    }
    historial = apps_viejas.get_model("censo", "HistoricalFichaEspecie").objects
    assert historial.count() == 2


def test_la_migracion_hacia_adelante_deja_el_esquema_final_sin_textos_viejos(datos_viejos):
    apps_finales = _migrar_a(SIN_TEXTOS)

    nombres = {campo.name for campo in apps_finales.get_model("censo", "Arbol")._meta.fields}
    assert not {"nombre_comun", "nombre_cientifico", "origen", "brigada"} & nombres
    assert not {f"{campo}_texto" for campo in ESTADOS} & nombres
    assert {"especie", "grupo", "valores_originales", *ESTADOS} <= nombres
    with pytest.raises(LookupError):
        apps_finales.get_model("censo", "FichaEspecie")
