"""Calidad del registro: estado y motivos de revisión, y el motivo de un destacado opcional.

Solo de esquema: un árbol existente queda «en revisión» (a prueba de fallos) hasta que se corra
`recalcular_calidad`, que aplica la regla a todos.
"""

from django.db import migrations, models

ESTADOS = [("publicado", "Publicado"), ("en_revision", "En revisión")]


class Migration(migrations.Migration):

    dependencies = [
        ("censo", "0006_permisos_de_capsulas"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="arbol",
            name="arbol_destacado_con_motivo",
        ),
        migrations.AddField(
            model_name="arbol",
            name="estado_registro",
            field=models.CharField(
                choices=ESTADOS, default="en_revision", editable=False, max_length=255
            ),
        ),
        migrations.AddField(
            model_name="arbol",
            name="motivos_revision",
            field=models.TextField(blank=True, default="", editable=False),
        ),
        migrations.AddField(
            model_name="historicalarbol",
            name="estado_registro",
            field=models.CharField(
                choices=ESTADOS, default="en_revision", editable=False, max_length=255
            ),
        ),
        migrations.AddField(
            model_name="historicalarbol",
            name="motivos_revision",
            field=models.TextField(blank=True, default="", editable=False),
        ),
    ]
