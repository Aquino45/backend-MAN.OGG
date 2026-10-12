"""DTO de salida del censo: la forma exacta de los schemas del contrato.

Solo leen campos ya cargados por los selectores; no consultan la BD ni llaman servicios. Los datos
de texto que viven en otra tabla (especie, catálogo) se aplanan aquí.
Las coordenadas salen en GeoJSON, `[longitud, latitud]`, con `DECIMALES_COORDENADAS`. La cartilla
suma las coordenadas UTM tal como están guardadas, en metros, con `DECIMALES_UTM`.
"""

from rest_framework import serializers

from config.constantes import CAMPO_ORIGEN, CAMPOS_DE_ESPECIE, DECIMALES_COORDENADAS, DECIMALES_UTM


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


class _TextoDelArbol(serializers.Field):
    """Un dato de texto del árbol que vive en otra tabla (especie, catálogo): sin dato es `null`."""

    def __init__(self, **kwargs):
        kwargs.update(source="*", read_only=True)
        super().__init__(**kwargs)

    def to_representation(self, arbol):
        """El texto de las tablas ya traídas con el árbol y, si falta, el que trajo la planilla."""
        campo = self.field_name
        texto = self._de_las_tablas(arbol, campo)
        if not (texto or "").strip():
            texto = (arbol.valores_originales or {}).get(campo)
        return texto or None

    @staticmethod
    def _de_las_tablas(arbol, campo):
        if campo in CAMPOS_DE_ESPECIE:
            especie = arbol.especie
            if especie is None:
                return None
            if campo == CAMPO_ORIGEN:
                return None if especie.origen is None else especie.origen.valor
            return getattr(especie, campo)
        catalogado = getattr(arbol, campo)
        return None if catalogado is None else catalogado.valor


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
    uid = serializers.UUIDField()
    sector = serializers.IntegerField(source="sector_id")
    nombre_comun = _TextoDelArbol()
    nombre_cientifico = _TextoDelArbol()
    estado_general = _TextoDelArbol()
    foto_miniatura_url = serializers.SerializerMethodField()
    co2_almacenado_kg = serializers.FloatField(allow_null=True)
    co2_captura_anual_kg = serializers.FloatField(allow_null=True)
    co2_simulado = serializers.BooleanField()
    demo = serializers.BooleanField()
    destacado = serializers.BooleanField()
    motivo_destacado = _TextoOpcional()

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
    También dice si el árbol está destacado en su sector y por qué (`motivo_destacado`, `null`
    si no lo está), y trae el `uid` que lo identifica aunque cambie su código.
    """

    codigo = serializers.CharField()
    uid = serializers.UUIDField()
    sector = serializers.IntegerField(source="sector_id")
    nombre_comun = _TextoDelArbol()
    nombre_cientifico = _TextoDelArbol()
    identificacion = _TextoDelArbol()
    origen = _TextoDelArbol()
    condicion_conservacion = _TextoDelArbol()
    lat = serializers.SerializerMethodField()
    lon = serializers.SerializerMethodField()
    utm_este_m = serializers.SerializerMethodField()
    utm_norte_m = serializers.SerializerMethodField()
    altura_total_m = serializers.FloatField(allow_null=True)
    dap_cm = serializers.FloatField(allow_null=True)
    copa_ns_m = serializers.FloatField(allow_null=True)
    copa_eo_m = serializers.FloatField(allow_null=True)
    estado_general = _TextoDelArbol()
    estado_copa = _TextoDelArbol()
    tronco_danos = _TextoDelArbol()
    raices_base = _TextoDelArbol()
    interferencia_entorno = _TextoDelArbol()
    observaciones = _TextoOpcional()
    foto_url = serializers.SerializerMethodField()
    foto_miniatura_url = serializers.SerializerMethodField()
    co2_almacenado_kg = serializers.FloatField(allow_null=True)
    co2_captura_anual_kg = serializers.FloatField(allow_null=True)
    co2_simulado = serializers.BooleanField()
    fuente = serializers.CharField()
    fecha_registro = serializers.DateField(allow_null=True)
    demo = serializers.BooleanField()
    destacado = serializers.BooleanField()
    motivo_destacado = _TextoOpcional()
    capsulas = serializers.SerializerMethodField()
    ficha_especie = serializers.SerializerMethodField()

    def get_capsulas(self, arbol):
        """Las ayudas del «?» de cada dato, ya armadas por el selector (vacía sin ayudas)."""
        return arbol.capsulas

    def get_ficha_especie(self, arbol):
        """La ficha de la especie, ya armada por el selector (null sin ficha publicada)."""
        return arbol.ficha_especie

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
