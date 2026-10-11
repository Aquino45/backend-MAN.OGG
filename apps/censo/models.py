# ruff: noqa: DJ001
# DJ001 desactivado a propósito: el contrato distingue null («Sin dato») de texto vacío,
# así que los textos opcionales usan null=True y nunca guardan "".
"""Modelos del censo: Sector, Arbol y los textos de ayuda de la cartilla (cápsulas).

Los nombres de campo son los del contrato."""

from uuid import uuid4

from django.conf import settings
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, RegexValidator
from django.db.models import Q
from simple_history.models import HistoricalRecords

from config.constantes import (
    CAMPOS_CATALOGADOS,
    CAMPOS_CON_AYUDA,
    ESTADO_REGISTRO_EN_REVISION,
    ESTADOS_REGISTRO,
    ETIQUETA_CO2_SIMULADO,
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

    `estado_registro` y `motivos_revision` los pone la regla de calidad (nunca se editan a mano):
    un árbol nuevo nace «en revisión» y solo sale en la API cuando la regla lo publica.

    `co2_simulado` dice que el CO₂ es una estimación que se reemplazará por el dato real. Un árbol
    de ejemplo con algún CO₂ siempre lo lleva marcado (lo aseguran la regla de calidad y la BD).

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
    co2_simulado = models.BooleanField(default=False, verbose_name=ETIQUETA_CO2_SIMULADO)
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
    estado_registro = models.CharField(
        max_length=LARGO_TEXTO,
        choices=ESTADOS_REGISTRO,
        default=ESTADO_REGISTRO_EN_REVISION,
        editable=False,
    )
    motivos_revision = models.TextField(blank=True, default="", editable=False)
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
                condition=Q(demo=False)
                | Q(co2_simulado=True)
                | (Q(co2_almacenado_kg__isnull=True) & Q(co2_captura_anual_kg__isnull=True)),
                name="arbol_demo_con_co2_es_simulado",
            ),
        ]

    def clean(self):
        """El código no choca con la papelera y un destacado cabe en el tope.

        El motivo de un destacado es opcional: vacío se guarda como null. Un árbol que está en la
        papelera no cuenta para el tope de su sector.
        """
        super().clean()
        self._validar_codigo_fuera_de_la_papelera()
        motivo = (self.motivo_destacado or "").strip() or None
        self.motivo_destacado = motivo if self.destacado else None
        if not self.destacado or self.eliminado_en is not None:
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


def _opciones(campos):
    """Opciones de un campo de texto limitado a una lista de nombres de las constantes."""
    return [(campo, campo) for campo in campos]


class AyudaCampo(models.Model):
    """Qué es un dato de la cartilla, en lenguaje simple: el texto del «?» de ese dato."""

    campo = models.CharField(
        max_length=LARGO_TEXTO, unique=True, choices=_opciones(CAMPOS_CON_AYUDA)
    )
    titulo = models.CharField(max_length=LARGO_TEXTO)
    que_es = models.TextField()
    orden = models.PositiveSmallIntegerField(default=0)
    activo = models.BooleanField(default=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["orden", "campo"]
        verbose_name = "ayuda de un dato"
        verbose_name_plural = "ayudas de los datos"

    def __str__(self):
        return f"{self.titulo} ({self.campo})"


class ValorCatalogo(models.Model):
    """Un valor de las listas desplegables de la planilla y lo que significa para un árbol.

    `valor` se guarda tal como viene de la planilla; al armar la cartilla se compara normalizado.
    """

    campo = models.CharField(max_length=LARGO_TEXTO, choices=_opciones(CAMPOS_CATALOGADOS))
    valor = models.CharField(max_length=LARGO_TEXTO)
    explicacion = models.TextField()
    orden = models.PositiveSmallIntegerField(default=0)
    activo = models.BooleanField(default=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["campo", "orden", "valor"]
        verbose_name = "valor del catálogo"
        verbose_name_plural = "valores del catálogo"
        constraints = [
            models.UniqueConstraint(fields=["campo", "valor"], name="valorcatalogo_campo_valor")
        ]

    def __str__(self):
        return f"{self.campo}: {self.valor}"


class FichaEspecie(models.Model):
    """Qué aporta una especie, en lenguaje simple. Siempre cita su fuente y sale solo publicada.

    `alias` son otros nombres con que llega la especie en la planilla, y `beneficios`, un texto
    con un beneficio por línea. `dato_curioso` y `cuidados` son opcionales: null, nunca "".
    """

    nombre_cientifico = models.CharField(max_length=LARGO_TEXTO, unique=True)
    nombre_comun = models.CharField(max_length=LARGO_TEXTO)
    alias = models.TextField(blank=True, help_text="Otros nombres de la especie, uno por línea.")
    beneficios = models.TextField(help_text="Un beneficio por línea.")
    dato_curioso = models.TextField(null=True, blank=True)
    cuidados = models.TextField(null=True, blank=True)
    fuente = models.TextField(help_text="De dónde sale el texto de la ficha. No puede ir vacía.")
    publicada = models.BooleanField(default=False)
    history = HistoricalRecords()

    class Meta:
        ordering = ["nombre_cientifico"]
        verbose_name = "ficha de especie"
        verbose_name_plural = "fichas de especie"
        constraints = [
            models.CheckConstraint(condition=~Q(fuente=""), name="ficha_especie_fuente_no_vacia")
        ]

    def clean(self):
        """Los textos opcionales vacíos se guardan como null («Sin dato»)."""
        super().clean()
        self.dato_curioso = (self.dato_curioso or "").strip() or None
        self.cuidados = (self.cuidados or "").strip() or None

    def __str__(self):
        return f"{self.nombre_cientifico} ({self.nombre_comun})"
