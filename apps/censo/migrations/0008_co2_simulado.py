"""CO₂ simulado: la marca por árbol, su dato inicial y la regla de la BD.

Todo árbol que ya tiene algún CO₂ queda marcado como simulado (decisión del stakeholder: hasta que
llegue el dato real). Después se agrega la restricción: un árbol de ejemplo con CO₂ va marcado.
"""

from django.db import migrations, models
from django.db.models import Q


def marcar_co2_existente_como_simulado(apps, schema_editor):
    """`co2_simulado = true` en todo árbol (también en la papelera) con algún CO₂."""
    Arbol = apps.get_model("censo", "Arbol")
    con_co2 = Q(co2_almacenado_kg__isnull=False) | Q(co2_captura_anual_kg__isnull=False)
    Arbol._base_manager.filter(con_co2).update(co2_simulado=True)


class Migration(migrations.Migration):

    dependencies = [
        ("censo", "0007_calidad_del_registro"),
    ]

    operations = [
        migrations.AddField(
            model_name="arbol",
            name="co2_simulado",
            field=models.BooleanField(default=False, verbose_name="CO₂ simulado"),
        ),
        migrations.AddField(
            model_name="historicalarbol",
            name="co2_simulado",
            field=models.BooleanField(default=False, verbose_name="CO₂ simulado"),
        ),
        migrations.RunPython(marcar_co2_existente_como_simulado, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="arbol",
            constraint=models.CheckConstraint(
                condition=Q(("demo", False))
                | Q(("co2_simulado", True))
                | Q(("co2_almacenado_kg__isnull", True), ("co2_captura_anual_kg__isnull", True)),
                name="arbol_demo_con_co2_es_simulado",
            ),
        ),
    ]
