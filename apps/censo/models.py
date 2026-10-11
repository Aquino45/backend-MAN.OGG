# ruff: noqa: DJ001
# DJ001 desactivado a propósito: el contrato distingue null («Sin dato») de texto vacío,
# así que los textos opcionales usan null=True y nunca guardan "".
"""Modelos del censo: Sector y Arbol. Los nombres de campo son los del contrato v0."""

from uuid import uuid4

from django.conf import settings
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, RegexValidator
from django.db.models import Q
from simple_history.models import HistoricalRecords

from config.constantes import (
    MENSAJE_CODIGO_EN_PAPELERA,
    PATRON_CODIGO_ARBOL,
    PERMISO_CAMBIAR_DEMO,
    SRID_UTM_CENSO,
    TOPE_DESTACADOS_POR_SECTOR,
)

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
    history = HistoricalRecords()

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.nombre


class ArbolesVigentes(models.Manager):
    """Solo los árboles que no están en la papelera: es lo que ve la API pública."""

    def get_queryset(self):
        return super().get_queryset().filter(eliminado_en__isnull=True)


class ArbolesEnPapelera(models.Manager):
    """Solo los árboles que están en la papelera."""

    def get_queryset(self):
        return super().get_queryset().filter(eliminado_en__isnull=False)


class Arbol(models.Model):
    """Un árbol del censo, con su ubicación UTM y su trazabilidad (`fuente`).

    Un árbol nunca se borra por error: va a la papelera (`eliminado_en`, `eliminado_por` y
    `motivo_eliminacion`) y puede restaurarse. `objects` trae solo los vigentes; `todos`, también
    los de la papelera. Cada cambio queda en `history`.

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
    eliminado_en = models.DateTimeField(null=True, blank=True)
    eliminado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="arboles_eliminados",
    )
    motivo_eliminacion = models.TextField(null=True, blank=True)

    objects = ArbolesVigentes()  # primero: es el manager por defecto (admin, formularios, API)
    todos = models.Manager()
    history = HistoricalRecords()

    class Meta:
        ordering = ["codigo"]
        permissions = [(PERMISO_CAMBIAR_DEMO, "Puede cambiar la marca demo de un árbol")]
        constraints = [
            models.CheckConstraint(condition=~Q(fuente=""), name="arbol_fuente_no_vacia"),
            models.CheckConstraint(
                condition=Q(destacado=False)
                | (Q(motivo_destacado__isnull=False) & ~Q(motivo_destacado="")),
                name="arbol_destacado_con_motivo",
            ),
        ]

    def clean(self):
        """El código no choca con la papelera; un destacado lleva motivo y cabe en el tope.

        Un árbol que está en la papelera no cuenta para el tope de su sector.
        """
        super().clean()
        self._validar_codigo_fuera_de_la_papelera()
        if not self.destacado:
            self.motivo_destacado = None
            return
        if not (self.motivo_destacado or "").strip():
            raise ValidationError(
                {"motivo_destacado": "Un árbol destacado necesita un motivo que lo explique."}
            )
        if self.eliminado_en is not None:
            return
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

    def _validar_codigo_fuera_de_la_papelera(self):
        """El código es único también contra la papelera (Django solo mira los vigentes)."""
        en_papelera = Arbol.todos.filter(codigo=self.codigo, eliminado_en__isnull=False)
        if self.codigo and en_papelera.exclude(pk=self.pk).exists():
            raise ValidationError({"codigo": MENSAJE_CODIGO_EN_PAPELERA.format(codigo=self.codigo)})

    def __str__(self):
        if self.nombre_comun:
            return f"{self.codigo} · {self.nombre_comun}"
        return self.codigo


class ArbolEnPapelera(Arbol):
    """Vista de la papelera en el panel: los mismos árboles, pero solo los eliminados."""

    objects = ArbolesEnPapelera()

    class Meta:
        proxy = True
        verbose_name = "árbol en la papelera"
        verbose_name_plural = "papelera de árboles"
