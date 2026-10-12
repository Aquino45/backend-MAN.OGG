# ruff: noqa: DJ001
# DJ001 desactivado a propósito: el contrato distingue null («Sin dato») de texto vacío,
# así que los textos opcionales usan null=True y nunca guardan "".
"""Especies, brigadas y grupos: las tablas de las que el árbol toma sus datos.

`models.py` las importa para que sean parte de la app `censo`.
"""

from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from simple_history.models import HistoricalRecords

from apps.censo.servicios.normalizacion import lineas_de, normalizar
from config.constantes import (
    CAMPO_ORIGEN,
    DECIMALES_DENSIDAD_MADERA,
    DIGITOS_DENSIDAD_MADERA,
    FORMAS_ESPECIE,
    LARGO_TEXTO,
    MENSAJE_ALIAS_REPETIDO,
    MENSAJE_FICHA_PUBLICADA_INCOMPLETA,
)


def _texto_opcional():
    """Texto corto opcional: null significa «Sin dato»."""
    return models.CharField(max_length=LARGO_TEXTO, null=True, blank=True)


class Especie(models.Model):
    """Una especie del censo, con su origen y su ficha de ayuda para la cartilla.

    `alias` son otros nombres con que llega la especie en la planilla (uno por línea) y
    `beneficios`, un beneficio por línea. La ficha sale en la cartilla solo si `ficha_publicada`
    (con el OK del stakeholder) y siempre cita su fuente. `revisada` en falso dice que la especie
    se creó a partir de un nombre que nadie ha confirmado todavía.
    """

    nombre_cientifico = models.CharField(max_length=LARGO_TEXTO, unique=True)
    nombre_comun = _texto_opcional()
    alias = models.TextField(blank=True, help_text="Otros nombres de la especie, uno por línea.")
    familia = _texto_opcional()
    origen = models.ForeignKey(
        "censo.ValorCatalogo",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="especies",
        limit_choices_to={"campo": CAMPO_ORIGEN},
    )
    forma = models.CharField(max_length=LARGO_TEXTO, choices=FORMAS_ESPECIE, null=True, blank=True)
    densidad_madera_g_cm3 = models.DecimalField(
        max_digits=DIGITOS_DENSIDAD_MADERA,
        decimal_places=DECIMALES_DENSIDAD_MADERA,
        null=True,
        blank=True,
    )
    fuente_densidad = models.TextField(null=True, blank=True)
    beneficios = models.TextField(blank=True, default="", help_text="Un beneficio por línea.")
    dato_curioso = models.TextField(null=True, blank=True)
    cuidados = models.TextField(null=True, blank=True)
    fuente_ficha = models.TextField(
        blank=True, default="", help_text="De dónde sale el texto de la ficha."
    )
    ficha_publicada = models.BooleanField(default=False)
    revisada = models.BooleanField(default=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["nombre_cientifico"]
        verbose_name = "especie"
        verbose_name_plural = "especies"
        constraints = [
            models.CheckConstraint(
                condition=Q(ficha_publicada=False)
                | (~Q(beneficios="") & ~Q(fuente_ficha="") & Q(nombre_comun__isnull=False)),
                name="especie_ficha_publicada_completa",
            )
        ]

    def clean(self):
        """Los textos opcionales vacíos van como null; un alias no se repite entre especies."""
        super().clean()
        for campo in ("nombre_comun", "familia", "forma", "fuente_densidad"):
            setattr(self, campo, (getattr(self, campo) or "").strip() or None)
        self.dato_curioso = (self.dato_curioso or "").strip() or None
        self.cuidados = (self.cuidados or "").strip() or None
        completa = self.nombre_comun and self.beneficios.strip() and self.fuente_ficha.strip()
        if self.ficha_publicada and not completa:
            raise ValidationError({"ficha_publicada": MENSAJE_FICHA_PUBLICADA_INCOMPLETA})
        self._validar_alias()

    def _validar_alias(self):
        """Ningún alias (comparado normalizado) lo tiene ya otra especie como nombre o alias."""
        propios = {normalizar(alias) for alias in lineas_de(self.alias)}
        if not propios:
            return
        for otra in Especie.objects.exclude(pk=self.pk):
            ocupados = {normalizar(otra.nombre_cientifico), *map(normalizar, lineas_de(otra.alias))}
            repetidos = propios & ocupados
            if repetidos:
                alias = next(a for a in lineas_de(self.alias) if normalizar(a) in repetidos)
                raise ValidationError(
                    {"alias": MENSAJE_ALIAS_REPETIDO.format(alias=alias, especie=otra)}
                )

    def __str__(self):
        if self.nombre_comun:
            return f"{self.nombre_cientifico} ({self.nombre_comun})"
        return self.nombre_cientifico


class Brigada(models.Model):
    """Una brigada de campo. Sus grupos son los que registran los árboles."""

    nombre = models.CharField(max_length=LARGO_TEXTO, unique=True)
    activa = models.BooleanField(default=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["nombre"]
        verbose_name = "brigada"
        verbose_name_plural = "brigadas"

    def __str__(self):
        return self.nombre


class GrupoBrigada(models.Model):
    """Un grupo de una brigada, con sus integrantes y los otros nombres que trae la planilla.

    `integrantes` y `alias` van uno por línea.
    """

    brigada = models.ForeignKey(Brigada, on_delete=models.PROTECT, related_name="grupos")
    nombre = models.CharField(max_length=LARGO_TEXTO)
    integrantes = models.TextField(blank=True, help_text="Un integrante por línea.")
    alias = models.TextField(
        blank=True, help_text="Otros nombres con que llega el grupo en la planilla, uno por línea."
    )
    activo = models.BooleanField(default=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["brigada__nombre", "nombre"]
        verbose_name = "grupo de la brigada"
        verbose_name_plural = "grupos de la brigada"
        constraints = [
            models.UniqueConstraint(
                fields=["brigada", "nombre"], name="grupobrigada_brigada_nombre"
            )
        ]

    def __str__(self):
        return f"{self.brigada} · {self.nombre}"
