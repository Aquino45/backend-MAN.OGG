"""Crea el esquema de la BD antes que cualquier tabla, para que todas caigan en él."""

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    # Corre antes de las primeras tablas de Django y del censo.
    run_before = [
        ("contenttypes", "0001_initial"),
        ("auth", "0001_initial"),
        ("censo", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=f'CREATE SCHEMA IF NOT EXISTS "{settings.DB_ESQUEMA}"',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
