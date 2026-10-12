"""Tablas de especies y brigadas, y las columnas nuevas del árbol (especie, grupo, estados del
catálogo y `valores_originales`).

Los 8 estados de texto pasan a llamarse `<campo>_texto` mientras la migración de datos
(0011) los traduce a referencias del catálogo; la 0012 quita los textos viejos.
"""

import django.db.models.deletion
import simple_history.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('censo', '0009_carga_de_planilla'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Brigada',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=255, unique=True)),
                ('activa', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'brigada',
                'verbose_name_plural': 'brigadas',
                'ordering': ['nombre'],
            },
        ),
        migrations.CreateModel(
            name='Especie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre_cientifico', models.CharField(max_length=255, unique=True)),
                ('nombre_comun', models.CharField(blank=True, max_length=255, null=True)),
                ('alias', models.TextField(blank=True, help_text='Otros nombres de la especie, uno por línea.')),
                ('familia', models.CharField(blank=True, max_length=255, null=True)),
                ('forma', models.CharField(blank=True, choices=[('arbol', 'Árbol'), ('palma', 'Palma'), ('arbusto', 'Arbusto')], max_length=255, null=True)),
                ('densidad_madera_g_cm3', models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True)),
                ('fuente_densidad', models.TextField(blank=True, null=True)),
                ('beneficios', models.TextField(blank=True, default='', help_text='Un beneficio por línea.')),
                ('dato_curioso', models.TextField(blank=True, null=True)),
                ('cuidados', models.TextField(blank=True, null=True)),
                ('fuente_ficha', models.TextField(blank=True, default='', help_text='De dónde sale el texto de la ficha.')),
                ('ficha_publicada', models.BooleanField(default=False)),
                ('revisada', models.BooleanField(default=True)),
                ('origen', models.ForeignKey(blank=True, limit_choices_to={'campo': 'origen'}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='especies', to='censo.valorcatalogo')),
            ],
            options={
                'verbose_name': 'especie',
                'verbose_name_plural': 'especies',
                'ordering': ['nombre_cientifico'],
            },
        ),
        migrations.CreateModel(
            name='GrupoBrigada',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=255)),
                ('integrantes', models.TextField(blank=True, help_text='Un integrante por línea.')),
                ('alias', models.TextField(blank=True, help_text='Otros nombres con que llega el grupo en la planilla, uno por línea.')),
                ('activo', models.BooleanField(default=True)),
                ('brigada', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='grupos', to='censo.brigada')),
            ],
            options={
                'verbose_name': 'grupo de la brigada',
                'verbose_name_plural': 'grupos de la brigada',
                'ordering': ['brigada__nombre', 'nombre'],
            },
        ),
        migrations.CreateModel(
            name='HistoricalBrigada',
            fields=[
                ('id', models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('nombre', models.CharField(db_index=True, max_length=255)),
                ('activa', models.BooleanField(default=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField(db_index=True)),
                ('history_change_reason', models.TextField(null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historical brigada',
                'verbose_name_plural': 'historical brigadas',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': ('history_date', 'history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='HistoricalEspecie',
            fields=[
                ('id', models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('nombre_cientifico', models.CharField(db_index=True, max_length=255)),
                ('nombre_comun', models.CharField(blank=True, max_length=255, null=True)),
                ('alias', models.TextField(blank=True, help_text='Otros nombres de la especie, uno por línea.')),
                ('familia', models.CharField(blank=True, max_length=255, null=True)),
                ('forma', models.CharField(blank=True, choices=[('arbol', 'Árbol'), ('palma', 'Palma'), ('arbusto', 'Arbusto')], max_length=255, null=True)),
                ('densidad_madera_g_cm3', models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True)),
                ('fuente_densidad', models.TextField(blank=True, null=True)),
                ('beneficios', models.TextField(blank=True, default='', help_text='Un beneficio por línea.')),
                ('dato_curioso', models.TextField(blank=True, null=True)),
                ('cuidados', models.TextField(blank=True, null=True)),
                ('fuente_ficha', models.TextField(blank=True, default='', help_text='De dónde sale el texto de la ficha.')),
                ('ficha_publicada', models.BooleanField(default=False)),
                ('revisada', models.BooleanField(default=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField(db_index=True)),
                ('history_change_reason', models.TextField(null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('origen', models.ForeignKey(blank=True, db_constraint=False, limit_choices_to={'campo': 'origen'}, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='censo.valorcatalogo')),
            ],
            options={
                'verbose_name': 'historical especie',
                'verbose_name_plural': 'historical especies',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': ('history_date', 'history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='HistoricalGrupoBrigada',
            fields=[
                ('id', models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('nombre', models.CharField(max_length=255)),
                ('integrantes', models.TextField(blank=True, help_text='Un integrante por línea.')),
                ('alias', models.TextField(blank=True, help_text='Otros nombres con que llega el grupo en la planilla, uno por línea.')),
                ('activo', models.BooleanField(default=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField(db_index=True)),
                ('history_change_reason', models.TextField(null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('brigada', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='censo.brigada')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historical grupo de la brigada',
                'verbose_name_plural': 'historical grupos de la brigada',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': ('history_date', 'history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.RenameField(
            model_name='arbol',
            old_name='condicion_conservacion',
            new_name='condicion_conservacion_texto',
        ),
        migrations.RenameField(
            model_name='arbol',
            old_name='estado_copa',
            new_name='estado_copa_texto',
        ),
        migrations.RenameField(
            model_name='arbol',
            old_name='estado_general',
            new_name='estado_general_texto',
        ),
        migrations.RenameField(
            model_name='arbol',
            old_name='identificacion',
            new_name='identificacion_texto',
        ),
        migrations.RenameField(
            model_name='arbol',
            old_name='interferencia_entorno',
            new_name='interferencia_entorno_texto',
        ),
        migrations.RenameField(
            model_name='arbol',
            old_name='raices_base',
            new_name='raices_base_texto',
        ),
        migrations.RenameField(
            model_name='arbol',
            old_name='tipo_individuo',
            new_name='tipo_individuo_texto',
        ),
        migrations.RenameField(
            model_name='arbol',
            old_name='tronco_danos',
            new_name='tronco_danos_texto',
        ),
        migrations.RenameField(
            model_name='historicalarbol',
            old_name='condicion_conservacion',
            new_name='condicion_conservacion_texto',
        ),
        migrations.RenameField(
            model_name='historicalarbol',
            old_name='estado_copa',
            new_name='estado_copa_texto',
        ),
        migrations.RenameField(
            model_name='historicalarbol',
            old_name='estado_general',
            new_name='estado_general_texto',
        ),
        migrations.RenameField(
            model_name='historicalarbol',
            old_name='identificacion',
            new_name='identificacion_texto',
        ),
        migrations.RenameField(
            model_name='historicalarbol',
            old_name='interferencia_entorno',
            new_name='interferencia_entorno_texto',
        ),
        migrations.RenameField(
            model_name='historicalarbol',
            old_name='raices_base',
            new_name='raices_base_texto',
        ),
        migrations.RenameField(
            model_name='historicalarbol',
            old_name='tipo_individuo',
            new_name='tipo_individuo_texto',
        ),
        migrations.RenameField(
            model_name='historicalarbol',
            old_name='tronco_danos',
            new_name='tronco_danos_texto',
        ),
        migrations.AddField(
            model_name='arbol',
            name='valores_originales',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='historicalarbol',
            name='valores_originales',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='arbol',
            name='especie',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='arboles', to='censo.especie'),
        ),
        migrations.AddField(
            model_name='historicalarbol',
            name='especie',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='censo.especie'),
        ),
        migrations.AddField(
            model_name='arbol',
            name='grupo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='arboles', to='censo.grupobrigada'),
        ),
        migrations.AddField(
            model_name='historicalarbol',
            name='grupo',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='censo.grupobrigada'),
        ),
        migrations.AddField(
            model_name='arbol',
            name='condicion_conservacion',
            field=models.ForeignKey(blank=True, limit_choices_to={'campo': 'condicion_conservacion'}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='arbol',
            name='estado_copa',
            field=models.ForeignKey(blank=True, limit_choices_to={'campo': 'estado_copa'}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='arbol',
            name='estado_general',
            field=models.ForeignKey(blank=True, limit_choices_to={'campo': 'estado_general'}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='arbol',
            name='identificacion',
            field=models.ForeignKey(blank=True, limit_choices_to={'campo': 'identificacion'}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='arbol',
            name='interferencia_entorno',
            field=models.ForeignKey(blank=True, limit_choices_to={'campo': 'interferencia_entorno'}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='arbol',
            name='raices_base',
            field=models.ForeignKey(blank=True, limit_choices_to={'campo': 'raices_base'}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='arbol',
            name='tipo_individuo',
            field=models.ForeignKey(blank=True, limit_choices_to={'campo': 'tipo_individuo'}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='arbol',
            name='tronco_danos',
            field=models.ForeignKey(blank=True, limit_choices_to={'campo': 'tronco_danos'}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='historicalarbol',
            name='condicion_conservacion',
            field=models.ForeignKey(blank=True, db_constraint=False, limit_choices_to={'campo': 'condicion_conservacion'}, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='historicalarbol',
            name='estado_copa',
            field=models.ForeignKey(blank=True, db_constraint=False, limit_choices_to={'campo': 'estado_copa'}, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='historicalarbol',
            name='estado_general',
            field=models.ForeignKey(blank=True, db_constraint=False, limit_choices_to={'campo': 'estado_general'}, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='historicalarbol',
            name='identificacion',
            field=models.ForeignKey(blank=True, db_constraint=False, limit_choices_to={'campo': 'identificacion'}, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='historicalarbol',
            name='interferencia_entorno',
            field=models.ForeignKey(blank=True, db_constraint=False, limit_choices_to={'campo': 'interferencia_entorno'}, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='historicalarbol',
            name='raices_base',
            field=models.ForeignKey(blank=True, db_constraint=False, limit_choices_to={'campo': 'raices_base'}, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='historicalarbol',
            name='tipo_individuo',
            field=models.ForeignKey(blank=True, db_constraint=False, limit_choices_to={'campo': 'tipo_individuo'}, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddField(
            model_name='historicalarbol',
            name='tronco_danos',
            field=models.ForeignKey(blank=True, db_constraint=False, limit_choices_to={'campo': 'tronco_danos'}, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='censo.valorcatalogo'),
        ),
        migrations.AddConstraint(
            model_name='especie',
            constraint=models.CheckConstraint(condition=models.Q(('ficha_publicada', False), models.Q(models.Q(('beneficios', ''), _negated=True), models.Q(('fuente_ficha', ''), _negated=True), ('nombre_comun__isnull', False)), _connector='OR'), name='especie_ficha_publicada_completa'),
        ),
        migrations.AddConstraint(
            model_name='grupobrigada',
            constraint=models.UniqueConstraint(fields=('brigada', 'nombre'), name='grupobrigada_brigada_nombre'),
        ),
    ]
