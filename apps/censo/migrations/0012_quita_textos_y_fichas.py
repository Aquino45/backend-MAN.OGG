"""Quita los textos viejos del árbol (nombres, origen, brigada y estados) y la ficha de especie.

Todo lo que tenían ya pasó a las tablas nuevas en la 0011.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('censo', '0011_datos_de_especies_brigadas_y_catalogo'),
    ]

    operations = [
        migrations.DeleteModel(
            name='FichaEspecie',
        ),
        migrations.DeleteModel(
            name='HistoricalFichaEspecie',
        ),
        migrations.RemoveField(
            model_name='arbol',
            name='brigada',
        ),
        migrations.RemoveField(
            model_name='arbol',
            name='nombre_cientifico',
        ),
        migrations.RemoveField(
            model_name='arbol',
            name='nombre_comun',
        ),
        migrations.RemoveField(
            model_name='arbol',
            name='origen',
        ),
        migrations.RemoveField(
            model_name='arbol',
            name='condicion_conservacion_texto',
        ),
        migrations.RemoveField(
            model_name='arbol',
            name='estado_copa_texto',
        ),
        migrations.RemoveField(
            model_name='arbol',
            name='estado_general_texto',
        ),
        migrations.RemoveField(
            model_name='arbol',
            name='identificacion_texto',
        ),
        migrations.RemoveField(
            model_name='arbol',
            name='interferencia_entorno_texto',
        ),
        migrations.RemoveField(
            model_name='arbol',
            name='raices_base_texto',
        ),
        migrations.RemoveField(
            model_name='arbol',
            name='tipo_individuo_texto',
        ),
        migrations.RemoveField(
            model_name='arbol',
            name='tronco_danos_texto',
        ),
        migrations.RemoveField(
            model_name='historicalarbol',
            name='brigada',
        ),
        migrations.RemoveField(
            model_name='historicalarbol',
            name='nombre_cientifico',
        ),
        migrations.RemoveField(
            model_name='historicalarbol',
            name='nombre_comun',
        ),
        migrations.RemoveField(
            model_name='historicalarbol',
            name='origen',
        ),
        migrations.RemoveField(
            model_name='historicalarbol',
            name='condicion_conservacion_texto',
        ),
        migrations.RemoveField(
            model_name='historicalarbol',
            name='estado_copa_texto',
        ),
        migrations.RemoveField(
            model_name='historicalarbol',
            name='estado_general_texto',
        ),
        migrations.RemoveField(
            model_name='historicalarbol',
            name='identificacion_texto',
        ),
        migrations.RemoveField(
            model_name='historicalarbol',
            name='interferencia_entorno_texto',
        ),
        migrations.RemoveField(
            model_name='historicalarbol',
            name='raices_base_texto',
        ),
        migrations.RemoveField(
            model_name='historicalarbol',
            name='tipo_individuo_texto',
        ),
        migrations.RemoveField(
            model_name='historicalarbol',
            name='tronco_danos_texto',
        ),
    ]
