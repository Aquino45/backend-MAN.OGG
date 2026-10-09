"""DTO de salida del censo: la forma exacta de los schemas del contrato.

Solo leen campos ya cargados por los selectores; no consultan la BD ni llaman servicios.
Las coordenadas salen en GeoJSON, `[longitud, latitud]`, con `DECIMALES_COORDENADAS`. La cartilla
suma las coordenadas UTM tal como están guardadas, en metros, con `DECIMALES_UTM`.
"""

from rest_framework import serializers

from config.constantes import DECIMALES_COORDENADAS, DECIMALES_UTM


def _posicion(longitud, latitud):
    """Un par `[longitud, latitud]` redondeado a los decimales que entrega la API."""
    return [round(longitud, DECIMALES_COORDENADAS), round(latitud, DECIMALES_COORDENADAS)]


def _punto(ubicacion):
    """GeoJSON Point de una ubicación en WGS 84, o `None` si el árbol no tiene coordenadas."""
    if ubicacion is None:
        return None
    return {"type": "Point", "coordinates": _posicion(ubicacion.x, ubicacion.y)}


def _poligono(poligono):
    """GeoJSON Polygon con cada vértice redondeado."""
    anillos = [[_posicion(x, y) for x, y, *_ in anillo] for anillo in poligono.coords]
    return {"type": "Polygon", "coordinates": anillos}


class _ColeccionSerializer(serializers.BaseSerializer):
    """FeatureCollection a partir de una lista de objetos; cada hija dice cómo es su feature."""

    serializador_de_feature = None

    def to_representation(self, instances):
        return {
            "type": "FeatureCollection",
            "features": [self.serializador_de_feature(item).data for item in instances],
        }


class _TextoOpcional(serializers.CharField):
    """Texto que puede faltar: el texto vacío se entrega como `null`."""

    def __init__(self, **kwargs):
        kwargs.setdefault("allow_null", True)
        super().__init__(**kwargs)

    def to_representation(self, value):
        texto = super().to_representation(value)
        return texto or None


class SectorPropiedadesSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    color = serializers.CharField(allow_null=True)
    provisional = serializers.BooleanField()
    total_arboles = serializers.IntegerField()


class SectorFeatureSerializer(serializers.BaseSerializer):
    """Un sector como Feature con su polígono en WGS 84."""

    def to_representation(self, sector):
        return {
            "type": "Feature",
            "id": sector.id,
            "geometry": _poligono(sector.geom_mapa),
            "properties": SectorPropiedadesSerializer(sector).data,
        }


class SectorColeccionSerializer(_ColeccionSerializer):
    serializador_de_feature = SectorFeatureSerializer


class ArbolResumenPropiedadesSerializer(serializers.Serializer):
    codigo = serializers.CharField()
    sector = serializers.IntegerField(source="sector_id")
    nombre_comun = serializers.CharField(allow_null=True)
    nombre_cientifico = serializers.CharField(allow_null=True)
    estado_general = serializers.CharField(allow_null=True)
    foto_miniatura_url = serializers.SerializerMethodField()
    demo = serializers.BooleanField()

    def get_foto_miniatura_url(self, arbol):
        """Aún no hay fotos del árbol: la URL viene en null."""
        return None


class ArbolResumenFeatureSerializer(serializers.BaseSerializer):
    """Un árbol como Feature: punto en WGS 84 (o `null`) y lo mínimo para listarlo."""

    def to_representation(self, arbol):
        return {
            "type": "Feature",
            "id": arbol.codigo,
            "geometry": _punto(arbol.ubicacion_mapa),
            "properties": ArbolResumenPropiedadesSerializer(arbol).data,
        }


class ArbolResumenColeccionSerializer(_ColeccionSerializer):
    serializador_de_feature = ArbolResumenFeatureSerializer


class ArbolSerializer(serializers.Serializer):
    """La cartilla del árbol: los campos del schema `Arbol`, en su orden. Sin dato, `null`.

    Además de las medidas y los estados, trae el contexto de campo (origen, identificación y
    observaciones) y la ubicación UTM tal como se guardó, sin recalcularla desde `lat` y `lon`.
    """

    codigo = serializers.CharField()
    sector = serializers.IntegerField(source="sector_id")
    nombre_comun = serializers.CharField(allow_null=True)
    nombre_cientifico = serializers.CharField(allow_null=True)
    identificacion = _TextoOpcional()
    origen = _TextoOpcional()
    condicion_conservacion = serializers.CharField(allow_null=True)
    lat = serializers.SerializerMethodField()
    lon = serializers.SerializerMethodField()
    utm_este_m = serializers.SerializerMethodField()
    utm_norte_m = serializers.SerializerMethodField()
    altura_total_m = serializers.FloatField(allow_null=True)
    dap_cm = serializers.FloatField(allow_null=True)
    copa_ns_m = serializers.FloatField(allow_null=True)
    copa_eo_m = serializers.FloatField(allow_null=True)
    estado_general = serializers.CharField(allow_null=True)
    estado_copa = serializers.CharField(allow_null=True)
    tronco_danos = serializers.CharField(allow_null=True)
    raices_base = serializers.CharField(allow_null=True)
    interferencia_entorno = serializers.CharField(allow_null=True)
    observaciones = _TextoOpcional()
    foto_url = serializers.SerializerMethodField()
    foto_miniatura_url = serializers.SerializerMethodField()
    co2_almacenado_kg = serializers.FloatField(allow_null=True)
    co2_captura_anual_kg = serializers.FloatField(allow_null=True)
    fuente = serializers.CharField()
    fecha_registro = serializers.DateField(allow_null=True)
    demo = serializers.BooleanField()

    def get_lat(self, arbol):
        ubicacion = arbol.ubicacion_mapa
        return None if ubicacion is None else _posicion(ubicacion.x, ubicacion.y)[1]

    def get_lon(self, arbol):
        ubicacion = arbol.ubicacion_mapa
        return None if ubicacion is None else _posicion(ubicacion.x, ubicacion.y)[0]

    def get_utm_este_m(self, arbol):
        """Metros este de la ubicación guardada, o `None` si el árbol no tiene ubicación."""
        ubicacion = arbol.ubicacion
        return None if ubicacion is None else round(ubicacion.x, DECIMALES_UTM)

    def get_utm_norte_m(self, arbol):
        """Metros norte de la ubicación guardada, o `None` si el árbol no tiene ubicación."""
        ubicacion = arbol.ubicacion
        return None if ubicacion is None else round(ubicacion.y, DECIMALES_UTM)

    def get_foto_url(self, arbol):
        """Aún no hay fotos del árbol: la URL viene en null."""
        return None

    def get_foto_miniatura_url(self, arbol):
        """Aún no hay fotos del árbol: la URL viene en null."""
        return None
