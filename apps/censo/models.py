# ruff: noqa: DJ001
# DJ001 desactivado a propósito: el contrato distingue null («Sin dato») de texto vacío,
# así que los textos opcionales usan null=True y nunca guardan "".
"""Modelos del censo: Sector y Arbol. Los nombres de campo son los del contrato v0."""

from django.contrib.gis.db import models
from django.core.validators import MinLengthValidator, RegexValidator
from django.db.models import Q

from config.constantes import PATRON_CODIGO_ARBOL, SRID_UTM_CENSO

LARGO_TEXTO = 255
"""Largo máximo de los textos cortos (nombres, catálogos, archivos de foto)."""

LARGO_CODIGO = 16
"""Largo máximo del código del árbol (el patrón usa 8 caracteres)."""

DIGITOS_MEDIDA = 12
"""Dígitos totales de las medidas decimales."""

DECIMALES_MEDIDA = 3
"""Decimales de las medidas (altura, DAP, copas, CO₂)."""


def _medida():
    """Campo decimal opcional: null significa «Sin dato»."""
    return models.DecimalField(
        max_digits=DIGITOS_MEDIDA, decimal_places=DECIMALES_MEDIDA, null=True, blank=True
    )


def _texto_opcional():
    """Texto corto opcional: null significa «Sin dato»."""
    return models.CharField(max_length=LARGO_TEXTO, null=True, blank=True)


class Sector(models.Model):
    """Zona del campus. Su `id` viene del GeoJSON de sectores."""

    id = models.PositiveSmallIntegerField(primary_key=True)
    nombre = models.CharField(max_length=LARGO_TEXTO)
    geom = models.PolygonField(srid=SRID_UTM_CENSO)
    color = models.CharField(max_length=LARGO_TEXTO, null=True, blank=True)
    provisional = models.BooleanField(default=False)
    fuente = models.TextField()

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.nombre


class Arbol(models.Model):
    """Un árbol del censo, con su ubicación UTM y su trazabilidad (`fuente`)."""

    codigo = models.CharField(
        max_length=LARGO_CODIGO,
        unique=True,
        validators=[RegexValidator(PATRON_CODIGO_ARBOL)],
    )
    sector = models.ForeignKey(Sector, on_delete=models.PROTECT, related_name="arboles")
    fecha_registro = models.DateField(null=True, blank=True)
    brigada = _texto_opcional()
    tipo_individuo = _texto_opcional()
    nombre_comun = _texto_opcional()
    nombre_cientifico = _texto_opcional()
    identificacion = _texto_opcional()
    origen = _texto_opcional()
    condicion_conservacion = _texto_opcional()
    ubicacion = models.PointField(srid=SRID_UTM_CENSO, null=True, blank=True)
    altura_total_m = _medida()
    dap_cm = _medida()
    copa_ns_m = _medida()
    copa_eo_m = _medida()
    co2_almacenado_kg = _medida()
    co2_captura_anual_kg = _medida()
    estado_general = _texto_opcional()
    estado_copa = _texto_opcional()
    tronco_danos = _texto_opcional()
    raices_base = _texto_opcional()
    interferencia_entorno = _texto_opcional()
    foto_archivo = _texto_opcional()
    foto_detalle_archivo = _texto_opcional()
    observaciones = models.TextField(null=True, blank=True)
    fuente = models.TextField(validators=[MinLengthValidator(1)])
    fila_origen = models.PositiveIntegerField(null=True, blank=True)
    demo = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["codigo"]
        constraints = [
            models.CheckConstraint(condition=~Q(fuente=""), name="arbol_fuente_no_vacia"),
        ]

    def __str__(self):
        if self.nombre_comun:
            return f"{self.codigo} · {self.nombre_comun}"
        return self.codigo
