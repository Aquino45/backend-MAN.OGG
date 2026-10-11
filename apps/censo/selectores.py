"""Lecturas del censo: las consultas que alimentan el mapa y la cartilla de cada árbol.

Los de la API pública solo ven los árboles vigentes y publicados (`publicados()`): lo que está en
la papelera o en revisión no sale. Los del panel (conteos del catálogo) ven todos los vigentes.

Aquí no se sabe de HTTP ni se escribe en la BD. Las coordenadas se guardan en UTM y se
entregan en WGS 84 (`SRID_MAPA`), transformadas por PostGIS; el redondeo lo hace el serializer.
"""

from django.contrib.gis.db.models.functions import Transform
from django.db.models import Count, Q

from apps.censo.models import Arbol, AyudaCampo, FichaEspecie, Sector, ValorCatalogo
from apps.censo.servicios.capsulas import armar_capsulas, buscar_ficha
from config.constantes import CAMPOS_CATALOGADOS, ESTADO_REGISTRO_PUBLICADO, SRID_MAPA


def publicados():
    """Los árboles que salen en la web: vigentes y con el registro publicado.

    Es el único lugar donde se decide qué ve el público; las lecturas de la API parten de aquí.
    """
    return Arbol.objects.filter(estado_registro=ESTADO_REGISTRO_PUBLICADO)


def sectores_con_total():
    """Los sectores del campus por `id`, con su total de árboles y su polígono para el mapa.

    Cuenta solo los árboles publicados, en una sola consulta. Los de la papelera y los que están
    en revisión no cuentan: el conteo por la relación inversa no pasa por `publicados()`, así que
    el mismo criterio se repite aquí.
    """
    return Sector.objects.annotate(
        total_arboles=Count(
            "arboles",
            filter=Q(
                arboles__eliminado_en__isnull=True,
                arboles__estado_registro=ESTADO_REGISTRO_PUBLICADO,
            ),
        ),
        geom_mapa=Transform("geom", SRID_MAPA),
    ).order_by("id")


def arboles_de_sector(sector_id):
    """Los árboles de un sector por `codigo`, con su posición lista para el mapa.

    Devuelve `None` si el sector no existe. Solo salen los publicados.
    """
    if not Sector.objects.filter(id=sector_id).exists():
        return None
    arboles = publicados().filter(sector_id=sector_id)
    return arboles.annotate(**_con_ubicacion_mapa()).order_by("codigo")


def arbol_por_codigo(codigo):
    """La cartilla de un árbol, o `None` si no existe o está en revisión.

    Trae la posición lista para el mapa (`ubicacion_mapa`, en WGS 84) y también la ubicación UTM
    tal como está guardada (`ubicacion`), de donde salen las coordenadas UTM de la cartilla.
    Deja también armadas sus `capsulas` y su `ficha_especie` (null si no hay ficha publicada), con
    3 consultas más: las ayudas activas, los valores activos del catálogo y las fichas publicadas.
    """
    arbol = publicados().annotate(**_con_ubicacion_mapa()).filter(codigo=codigo).first()
    if arbol is None:
        return None
    ayudas = list(AyudaCampo.objects.filter(activo=True))
    valores = list(ValorCatalogo.objects.filter(activo=True))
    fichas = list(FichaEspecie.objects.filter(publicada=True))
    arbol.capsulas = armar_capsulas(arbol, ayudas, valores)
    arbol.ficha_especie = buscar_ficha(arbol, fichas)
    return arbol


def conteo_de_valores_de_arboles():
    """Cuántos árboles vigentes tienen cada valor, como `{(campo, valor): total}`.

    Mira los campos catalogados; el valor se toma exacto («bueno» y «Bueno» van aparte) y se
    omiten los vacíos.
    """
    conteo = {}
    for campo in CAMPOS_CATALOGADOS:
        filas = Arbol.objects.filter(**{f"{campo}__isnull": False}).values(campo)
        for fila in filas.annotate(total=Count("pk")):
            if fila[campo].strip():
                conteo[(campo, fila[campo])] = fila["total"]
    return conteo


def valores_fuera_del_catalogo():
    """Los valores de los árboles vigentes que no están en el catálogo, por campo y valor.

    La comparación es exacta, para que se vean las variantes de escritura. Un valor inactivo
    del catálogo cuenta como parte del catálogo. Cada elemento: `campo`, `valor`, `total_arboles`.
    """
    catalogados = set(ValorCatalogo.objects.values_list("campo", "valor"))
    return [
        {"campo": campo, "valor": valor, "total_arboles": total}
        for (campo, valor), total in sorted(conteo_de_valores_de_arboles().items())
        if (campo, valor) not in catalogados
    ]


def _con_ubicacion_mapa():
    """Anotación común: la ubicación del árbol transformada a WGS 84."""
    return {"ubicacion_mapa": Transform("ubicacion", SRID_MAPA)}
