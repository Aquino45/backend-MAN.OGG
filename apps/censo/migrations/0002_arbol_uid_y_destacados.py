"""Suma el `uid` estable de cada árbol y la marca de árbol destacado con su motivo.

El `uid` se agrega primero nullable, se llena con un UUID distinto por árbol y recién entonces
pasa a ser único y obligatorio. Los árboles existentes quedan con `destacado = false`.
"""

import uuid

from django.db import migrations, models


def asignar_uid_distinto(apps, schema_editor):
    """Da a cada árbol existente su propio UUID."""
    Arbol = apps.get_model("censo", "Arbol")
    for arbol in Arbol.objects.filter(uid__isnull=True).iterator():
        arbol.uid = uuid.uuid4()
        arbol.save(update_fields=["uid"])


class Migration(migrations.Migration):

    dependencies = [
        ("censo", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="arbol",
            name="uid",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(asignar_uid_distinto, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="arbol",
            name="uid",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name="arbol",
            name="destacado",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="arbol",
            name="motivo_destacado",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="arbol",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("destacado", False),
                    models.Q(
                        ("motivo_destacado__isnull", False),
                        models.Q(("motivo_destacado", ""), _negated=True),
                    ),
                    _connector="OR",
                ),
                name="arbol_destacado_con_motivo",
            ),
        ),
    ]
