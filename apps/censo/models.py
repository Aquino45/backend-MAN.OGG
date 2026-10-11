# ruff: noqa: DJ001
# DJ001 desactivado a propósito: el contrato distingue null («Sin dato») de texto vacío,
# así que los textos opcionales usan null=True y nunca guardan "".
"""Modelos del censo: Sector y Arbol. Los nombres de campo son los del contrato v0."""

from uuid import uuid4

from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, RegexValidator
from django.db.models import Q

from config.constantes import PATRON_CODIGO_ARBOL, SRID_UTM_CENSO, TOPE_DESTACADOS_POR_SECTOR

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
    """Un árbol del censo, con su ubicación UTM y su trazabilidad (`fuente`).

    El `uid` identifica al árbol para siempre, aunque su `codigo` se corrija. La administración
    del censo puede destacar árboles de un sector, con un motivo y hasta un tope por sector.
    """

    codigo = models.CharField(
        max_length=LARGO_CODIGO,
        unique=True,
        validators=[RegexValidator(PATRON_CODIGO_ARBOL)],
    )
    uid = models.UUIDField(default=uuid4, unique=True, editable=False)
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
    destacado = models.BooleanField(default=False)
    motivo_destacado = models.TextField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["codigo"]
        constraints = [
            models.CheckConstraint(condition=~Q(fuente=""), name="arbol_fuente_no_vacia"),
            models.CheckConstraint(
                condition=Q(destacado=False)
                | (Q(motivo_destacado__isnull=False) & ~Q(motivo_destacado="")),
                name="arbol_destacado_con_motivo",
            ),
        ]

    def clean(self):
        """Un destacado lleva motivo y cabe en el tope del sector; los demás no guardan motivo."""
        super().clean()
        if not self.destacado:
            self.motivo_destacado = None
            return
        if not (self.motivo_destacado or "").strip():
            raise ValidationError(
                {"motivo_destacado": "Un árbol destacado necesita un motivo que lo explique."}
            )
        otros_destacados = Arbol.objects.filter(sector_id=self.sector_id, destacado=True).exclude(
            pk=self.pk
        )
        if otros_destacados.count() >= TOPE_DESTACADOS_POR_SECTOR:
            codigos = ", ".join(
                otros_destacados.order_by("codigo").values_list("codigo", flat=True)
            )
            raise ValidationError(
                {
                    "destacado": (
                        f"Cada sector admite hasta {TOPE_DESTACADOS_POR_SECTOR} árboles "
                        f"destacados. Ya están destacados: {codigos}."
                    )
                }
            )

    def __str__(self):
        if self.nombre_comun:
            return f"{self.codigo} · {self.nombre_comun}"
        return self.codigo
