"""Lecturas del censo: las consultas que alimentan el mapa y la cartilla de cada árbol.

Solo ven los árboles vigentes (`Arbol.objects`): lo que está en la papelera no sale en la API.

Aquí no se sabe de HTTP ni se escribe en la BD. Las coordenadas se guardan en UTM y se
entregan en WGS 84 (`SRID_MAPA`), transformadas por PostGIS; el redondeo lo hace el serializer.
"""

from django.contrib.gis.db.models.functions import Transform
from django.db.models import Count, Q

from apps.censo.models import Arbol, AyudaCampo, FichaEspecie, Sector, ValorCatalogo
from apps.censo.servicios.capsulas import armar_capsulas, buscar_ficha
from config.constantes import CAMPOS_CATALOGADOS, SRID_MAPA


def sectores_con_total():
    """Los sectores del campus por `id`, con su total de árboles y su polígono para el mapa.

    Cuenta los árboles vigentes (también los que no tienen datos) y lo hace en una sola consulta.
    Los de la papelera no cuentan: el conteo por la relación inversa no pasa por `Arbol.objects`,
    así que el filtro va aquí.
    """
    return Sector.objects.annotate(
        total_arboles=Count("arboles", filter=Q(arboles__eliminado_en__isnull=True)),
        geom_mapa=Transform("geom", SRID_MAPA),
    ).order_by("id")


def arboles_de_sector(sector_id):
    """Los árboles de un sector por `codigo`, con su posición lista para el mapa.

    Devuelve `None` si el sector no existe. Un árbol sin coordenadas aparece igual, con
    `ubicacion_mapa` en null: está en la lista pero no en el mapa.
    """
    if not Sector.objects.filter(id=sector_id).exists():
        return None
    arboles = Arbol.objects.filter(sector_id=sector_id)
    return arboles.annotate(**_con_ubicacion_mapa()).order_by("codigo")


def arbol_por_codigo(codigo):
    """La cartilla de un árbol, o `None` si no existe.

    Trae la posición lista para el mapa (`ubicacion_mapa`, en WGS 84) y también la ubicación UTM
    tal como está guardada (`ubicacion`), de donde salen las coordenadas UTM de la cartilla.
    Deja también armadas sus `capsulas` y su `ficha_especie` (null si no hay ficha publicada), con
    3 consultas más: las ayudas activas, los valores activos del catálogo y las fichas publicadas.
    """
    arbol = Arbol.objects.annotate(**_con_ubicacion_mapa()).filter(codigo=codigo).first()
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
