# ruff: noqa: DJ001
# DJ001 desactivado a propósito: el contrato distingue null («Sin dato») de texto vacío,
# así que los textos opcionales usan null=True y nunca guardan "".
"""Modelos del censo: Sector, Arbol, los textos de ayuda de la cartilla (cápsulas) y las cargas.

Las especies y las brigadas viven en `models_catalogos`. Los nombres de campo son los del
contrato."""

from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, RegexValidator
from django.db.models import Q
from django.utils import timezone
from simple_history.models import HistoricalRecords

from apps.censo.models_catalogos import (  # noqa: F401  (las tablas son parte de la app)
    Brigada,
    Especie,
    GrupoBrigada,
)
from config.constantes.calidad import (
    ESTADO_REGISTRO_EN_REVISION,
    ESTADOS_REGISTRO,
    ETIQUETA_CO2_SIMULADO,
)
from config.constantes.carga import (
    CLASIFICACION_LISTO,
    CLASIFICACIONES_CARGA,
    DECISION_SIN_DECIDIR,
    DECISIONES_FILA_CARGA,
    ESTADO_LOTE_CANCELADO,
    ESTADO_LOTE_VALIDADO,
    ESTADOS_LOTE_CARGA,
)
from config.constantes.catalogos import (
    CAMPOS_CATALOGADOS,
    CAMPOS_CON_AYUDA,
    ETIQUETAS_DE_CAMPOS_CON_AYUDA,
)
from config.constantes.general import (
    LARGO_TEXTO,
    PATRON_CODIGO_ARBOL,
    SRID_UTM_CENSO,
    TOPE_DESTACADOS_POR_SECTOR,
)
from config.constantes.mapa import (
    ETIQUETA_FECHA_UBICACION_EDITADA,
    ETIQUETA_UBICACION_EDITADA_EN_PANEL,
)
from config.constantes.panel import MENSAJE_CODIGO_EN_PAPELERA
from config.constantes.permisos import PERMISO_CAMBIAR_DEMO, PERMISO_CARGAR_PLANILLA

LARGO_CODIGO = 16
"""Largo máximo del código del árbol (el patrón usa 8 caracteres)."""

DIGITOS_MEDIDA = 12
"""Dígitos totales de las medidas decimales."""

DECIMALES_MEDIDA = 3
"""Decimales de las medidas (altura, DAP, copas, CO₂)."""


def _medida(etiqueta):
    """Campo decimal opcional: null significa «Sin dato»."""
    return models.DecimalField(
        max_digits=DIGITOS_MEDIDA,
        decimal_places=DECIMALES_MEDIDA,
        null=True,
        blank=True,
        verbose_name=etiqueta,
    )


def _texto_opcional(etiqueta):
    """Texto corto opcional: null significa «Sin dato»."""
    return models.CharField(max_length=LARGO_TEXTO, null=True, blank=True, verbose_name=etiqueta)


def _valor_del_catalogo(campo, etiqueta):
    """Referencia opcional a un valor del catálogo de ese campo; null significa «Sin dato»."""
    return models.ForeignKey(
        "censo.ValorCatalogo",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        limit_choices_to={"campo": campo},
        verbose_name=etiqueta,
    )


class Sector(models.Model):
    """Zona del campus. Su `id` viene del GeoJSON de sectores."""

    id = models.PositiveSmallIntegerField(primary_key=True, verbose_name="número")
    nombre = models.CharField(max_length=LARGO_TEXTO, verbose_name="nombre")
    geom = models.PolygonField(srid=SRID_UTM_CENSO, verbose_name="fronteras del sector")
    color = models.CharField(max_length=LARGO_TEXTO, null=True, blank=True, verbose_name="color")
    provisional = models.BooleanField(default=False, verbose_name="límites provisionales")
    fuente = models.TextField(verbose_name="fuente")
    history = HistoricalRecords()

    class Meta:
        ordering = ["id"]
        verbose_name = "sector"
        verbose_name_plural = "sectores"

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

    `ubicacion_editada_en_panel` dice que alguien corrigió la ubicación a mano en el panel (y
    `fecha_ubicacion_editada` cuándo): mientras esté activa, la planilla no la pisa.

    El nombre, el origen y la ficha salen de su `especie`; la brigada, de su `grupo`. Los estados
    son valores del catálogo. Lo que la planilla trajo y no se pudo resolver (o llegó con otro
    nombre) queda en `valores_originales`, por campo.

    El `uid` identifica al árbol para siempre, aunque su `codigo` se corrija. La administración
    del censo puede destacar árboles de un sector, con un motivo y hasta un tope por sector.
    """

    codigo = models.CharField(
        max_length=LARGO_CODIGO,
        unique=True,
        validators=[RegexValidator(PATRON_CODIGO_ARBOL)],
        verbose_name="código",
    )
    uid = models.UUIDField(
        default=uuid4, unique=True, editable=False, verbose_name="identificador único"
    )
    sector = models.ForeignKey(
        Sector, on_delete=models.PROTECT, related_name="arboles", verbose_name="sector"
    )
    fecha_registro = models.DateField(null=True, blank=True, verbose_name="fecha de registro")
    especie = models.ForeignKey(
        Especie,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="arboles",
        verbose_name="especie",
    )
    grupo = models.ForeignKey(
        GrupoBrigada,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="arboles",
        verbose_name="grupo de la brigada",
    )
    tipo_individuo = _valor_del_catalogo("tipo_individuo", "tipo de individuo")
    identificacion = _valor_del_catalogo("identificacion", "identificación")
    condicion_conservacion = _valor_del_catalogo(
        "condicion_conservacion", "condición de conservación"
    )
    ubicacion = models.PointField(
        srid=SRID_UTM_CENSO, null=True, blank=True, verbose_name="ubicación"
    )
    ubicacion_editada_en_panel = models.BooleanField(
        default=False, verbose_name=ETIQUETA_UBICACION_EDITADA_EN_PANEL
    )
    fecha_ubicacion_editada = models.DateTimeField(
        null=True, blank=True, verbose_name=ETIQUETA_FECHA_UBICACION_EDITADA
    )
    altura_total_m = _medida("altura total (m)")
    dap_cm = _medida("DAP (cm)")
    copa_ns_m = _medida("copa norte-sur (m)")
    copa_eo_m = _medida("copa este-oeste (m)")
    co2_almacenado_kg = _medida("CO₂ almacenado (kg)")
    co2_captura_anual_kg = _medida("CO₂ capturado por año (kg)")
    co2_simulado = models.BooleanField(default=False, verbose_name=ETIQUETA_CO2_SIMULADO)
    estado_general = _valor_del_catalogo("estado_general", "estado general")
    estado_copa = _valor_del_catalogo("estado_copa", "estado de la copa")
    tronco_danos = _valor_del_catalogo("tronco_danos", "daños del tronco")
    raices_base = _valor_del_catalogo("raices_base", "raíces y base")
    interferencia_entorno = _valor_del_catalogo(
        "interferencia_entorno", "interferencia del entorno"
    )
    foto_archivo = _texto_opcional("archivo de la foto")
    foto_detalle_archivo = _texto_opcional("archivo de la foto de detalle")
    observaciones = models.TextField(null=True, blank=True, verbose_name="observaciones")
    valores_originales = models.JSONField(
        default=dict, blank=True, verbose_name="valores originales de la planilla"
    )
    fuente = models.TextField(validators=[MinLengthValidator(1)], verbose_name="fuente")
    fila_origen = models.PositiveIntegerField(null=True, blank=True, verbose_name="fila de origen")
    demo = models.BooleanField(default=False, verbose_name="de ejemplo")
    destacado = models.BooleanField(default=False, verbose_name="destacado")
    motivo_destacado = models.TextField(null=True, blank=True, verbose_name="motivo del destacado")
    estado_registro = models.CharField(
        max_length=LARGO_TEXTO,
        choices=ESTADOS_REGISTRO,
        default=ESTADO_REGISTRO_EN_REVISION,
        editable=False,
        verbose_name="estado del registro",
    )
    motivos_revision = models.TextField(
        blank=True, default="", editable=False, verbose_name="motivos de la revisión"
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="creado el")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="actualizado el")
    eliminado_en = models.DateTimeField(null=True, blank=True, verbose_name="eliminado el")
    eliminado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="arboles_eliminados",
        verbose_name="eliminado por",
    )
    motivo_eliminacion = models.TextField(
        null=True, blank=True, verbose_name="motivo de la eliminación"
    )

    objects = ArbolesVigentes()  # primero: es el manager por defecto (admin, formularios, API)
    todos = models.Manager()
    history = HistoricalRecords()

    class Meta:
        ordering = ["codigo"]
        verbose_name = "árbol"
        verbose_name_plural = "árboles"
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
        nombre_comun = self.especie.nombre_comun if self.especie else None
        return f"{self.codigo} · {nombre_comun}" if nombre_comun else self.codigo


class ArbolEnPapelera(Arbol):
    """Vista de la papelera en el panel: los mismos árboles, pero solo los eliminados."""

    objects = ArbolesEnPapelera()

    class Meta:
        proxy = True
        verbose_name = "árbol en la papelera"
        verbose_name_plural = "papelera de árboles"


def _opciones(campos):
    """Opciones de un campo de texto limitado a una lista de nombres de las constantes."""
    return [(campo, ETIQUETAS_DE_CAMPOS_CON_AYUDA.get(campo, campo)) for campo in campos]


class AyudaCampo(models.Model):
    """Qué es un dato de la cartilla, en lenguaje simple: el texto del «?» de ese dato."""

    campo = models.CharField(
        max_length=LARGO_TEXTO,
        unique=True,
        choices=_opciones(CAMPOS_CON_AYUDA),
        verbose_name="dato",
    )
    titulo = models.CharField(max_length=LARGO_TEXTO, verbose_name="título")
    que_es = models.TextField(verbose_name="qué es")
    orden = models.PositiveSmallIntegerField(default=0, verbose_name="orden")
    activo = models.BooleanField(default=True, verbose_name="activa")
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

    campo = models.CharField(
        max_length=LARGO_TEXTO, choices=_opciones(CAMPOS_CATALOGADOS), verbose_name="dato"
    )
    valor = models.CharField(max_length=LARGO_TEXTO, verbose_name="valor")
    explicacion = models.TextField(
        verbose_name="explicación",
        help_text="Qué significa este valor para un árbol, en lenguaje simple.",
    )
    orden = models.PositiveSmallIntegerField(default=0, verbose_name="orden")
    activo = models.BooleanField(default=True, verbose_name="activo")
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


class LoteCargas(models.Manager):
    """Consultas de la bitácora de cargas."""

    def purgar_vencidos(self, horas):
        """Cierra como cancelados los lotes validados hace más de `horas` y borra sus filas."""
        limite = timezone.now() - timedelta(hours=horas)
        vencidos = self.filter(estado=ESTADO_LOTE_VALIDADO, fecha__lt=limite)
        FilaCarga.objects.filter(lote__in=vencidos).delete()
        return vencidos.update(estado=ESTADO_LOTE_CANCELADO)


class LoteCarga(models.Model):
    """Una planilla subida desde el panel: queda de bitácora con sus totales.

    El archivo no se guarda en el servidor, solo su `sha256` y las filas que se leyeron
    (`FilaCarga`), que se borran al confirmar o cancelar. `resultado` lleva los códigos de cada
    grupo cuando la carga se confirma.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lotes_de_carga",
        verbose_name="usuario",
    )
    fecha = models.DateTimeField(default=timezone.now, verbose_name="fecha")
    nombre_archivo = models.CharField(max_length=LARGO_TEXTO, verbose_name="nombre del archivo")
    sha256 = models.CharField(max_length=64, verbose_name="huella SHA-256 del archivo")
    estado = models.CharField(
        max_length=LARGO_TEXTO,
        choices=ESTADOS_LOTE_CARGA,
        default=ESTADO_LOTE_VALIDADO,
        verbose_name="estado",
    )
    filas_leidas = models.PositiveIntegerField(default=0, verbose_name="filas leídas")
    listos = models.PositiveIntegerField(default=0, verbose_name="listos")
    con_campos_vacios = models.PositiveIntegerField(default=0, verbose_name="con campos vacíos")
    inconsistentes = models.PositiveIntegerField(default=0, verbose_name="inconsistentes")
    duplicados = models.PositiveIntegerField(default=0, verbose_name="duplicados")
    resultado = models.JSONField(default=dict, blank=True, verbose_name="resultado")
    objects = LoteCargas()

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "carga de planilla"
        verbose_name_plural = "Cargar planilla"
        permissions = [(PERMISO_CARGAR_PLANILLA, "Puede cargar la planilla de la brigada")]

    def cerrar(self, estado, resultado=None):
        """Pasa el lote a `estado`, guarda el resultado y borra las filas que quedaban."""
        self.filas.all().delete()
        self.estado = estado
        self.resultado = resultado or {}
        self.save(update_fields=["estado", "resultado"])

    def __str__(self):
        return f"{self.nombre_archivo} ({self.get_estado_display()})"


class FilaCarga(models.Model):
    """Una fila leída de la planilla de un lote, con lo que se decidió sobre ella.

    `datos` son los valores tal como se leyeron (en JSON) y `motivos`, lo que la regla de calidad
    y la detección de duplicados encontraron: `[{"campo": …, "porque": …}]`.
    """

    lote = models.ForeignKey(
        LoteCarga, on_delete=models.CASCADE, related_name="filas", verbose_name="carga"
    )
    numero_fila = models.PositiveIntegerField(verbose_name="número de fila")
    codigo = models.CharField(max_length=LARGO_CODIGO, verbose_name="código")
    clasificacion = models.CharField(
        max_length=LARGO_TEXTO,
        choices=CLASIFICACIONES_CARGA,
        default=CLASIFICACION_LISTO,
        verbose_name="clasificación",
    )
    datos = models.JSONField(verbose_name="datos")
    motivos = models.JSONField(default=list, blank=True, verbose_name="motivos")
    decision = models.CharField(
        max_length=LARGO_TEXTO,
        choices=DECISIONES_FILA_CARGA,
        default=DECISION_SIN_DECIDIR,
        verbose_name="decisión",
    )

    class Meta:
        ordering = ["numero_fila"]
        verbose_name = "fila de la carga"
        verbose_name_plural = "filas de la carga"
        constraints = [
            models.UniqueConstraint(fields=["lote", "numero_fila"], name="filacarga_lote_fila")
        ]

    def __str__(self):
        return f"{self.codigo} (fila {self.numero_fila})"
