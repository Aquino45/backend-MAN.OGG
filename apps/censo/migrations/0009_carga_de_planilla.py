"""Crea las tablas de las cargas de planilla y da el permiso `cargar_planilla` a los dos roles.

La parte de datos se puede repetir sin duplicar nada: solo agrega el permiso, nunca quita los que
el grupo ya tenía. El permiso del modelo nuevo todavía no existe cuando corre esta migración, así
que se crea aquí antes de asignarlo.
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.contrib.auth.management import create_permissions
from django.db import migrations, models

from config.constantes import PERMISOS_CARGA_POR_ROL


def sumar_permiso_de_carga(apps, schema_editor):
    """Agrega a cada grupo los permisos de `PERMISOS_CARGA_POR_ROL`."""
    app_censo = apps.get_app_config("censo")
    previo = getattr(app_censo, "models_module", None)
    if previo is None:
        # Las apps de una migración no traen `models_module`, y create_permissions lo exige.
        app_censo.models_module = True
    try:
        create_permissions(app_censo, apps=apps, verbosity=0)
    finally:
        if previo is None:
            app_censo.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for nombre_rol, codigos in PERMISOS_CARGA_POR_ROL.items():
        grupo, _ = Group.objects.get_or_create(name=nombre_rol)
        permisos = Permission.objects.filter(content_type__app_label="censo", codename__in=codigos)
        grupo.permissions.add(*permisos)


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("censo", "0008_co2_simulado"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LoteCarga",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("fecha", models.DateTimeField(default=django.utils.timezone.now)),
                ("nombre_archivo", models.CharField(max_length=255)),
                ("sha256", models.CharField(max_length=64)),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("validado", "Validado"),
                            ("confirmado", "Confirmado"),
                            ("cancelado", "Cancelado"),
                        ],
                        default="validado",
                        max_length=255,
                    ),
                ),
                ("filas_leidas", models.PositiveIntegerField(default=0)),
                ("listos", models.PositiveIntegerField(default=0)),
                ("con_campos_vacios", models.PositiveIntegerField(default=0)),
                ("inconsistentes", models.PositiveIntegerField(default=0)),
                ("duplicados", models.PositiveIntegerField(default=0)),
                ("resultado", models.JSONField(blank=True, default=dict)),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="lotes_de_carga",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "carga de planilla",
                "verbose_name_plural": "Cargar planilla",
                "ordering": ["-fecha", "-id"],
                "permissions": [("cargar_planilla", "Puede cargar la planilla de la brigada")],
            },
        ),
        migrations.CreateModel(
            name="FilaCarga",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("numero_fila", models.PositiveIntegerField()),
                ("codigo", models.CharField(max_length=16)),
                (
                    "clasificacion",
                    models.CharField(
                        choices=[
                            ("listo", "Listo"),
                            ("campos_vacios", "Con campos vacíos"),
                            ("inconsistente", "Inconsistente"),
                            ("duplicado", "Duplicado"),
                        ],
                        default="listo",
                        max_length=255,
                    ),
                ),
                ("datos", models.JSONField()),
                ("motivos", models.JSONField(blank=True, default=list)),
                (
                    "decision",
                    models.CharField(
                        choices=[
                            ("conservar", "Conservar"),
                            ("descartar", "Descartar"),
                            ("sin_decidir", "Sin decidir"),
                        ],
                        default="sin_decidir",
                        max_length=255,
                    ),
                ),
                (
                    "lote",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="filas",
                        to="censo.lotecarga",
                    ),
                ),
            ],
            options={
                "ordering": ["numero_fila"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("lote", "numero_fila"), name="filacarga_lote_fila"
                    )
                ],
            },
        ),
        migrations.RunPython(sumar_permiso_de_carga, migrations.RunPython.noop),
    ]
