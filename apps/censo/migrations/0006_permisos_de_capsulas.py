"""Suma a los grupos Administrador y Editor los permisos de las ayudas, el catálogo y las fichas.

Se puede repetir sin duplicar nada: solo agrega permisos, nunca quita los que el grupo ya tenía
(los de la migración de roles siguen). Los permisos de los modelos nuevos todavía no existen
cuando corre esta migración, así que se crean aquí antes de asignarlos.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

from config.constantes import PERMISOS_CAPSULAS_POR_ROL


def sumar_permisos_de_capsulas(apps, schema_editor):
    """Agrega a cada grupo los permisos de `PERMISOS_CAPSULAS_POR_ROL`."""
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
    for nombre_rol, codigos in PERMISOS_CAPSULAS_POR_ROL.items():
        grupo, _ = Group.objects.get_or_create(name=nombre_rol)
        permisos = Permission.objects.filter(
            content_type__app_label="censo", codename__in=codigos
        )
        grupo.permissions.add(*permisos)


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("censo", "0005_capsulas_catalogo_y_fichas"),
    ]

    operations = [
        migrations.RunPython(sumar_permisos_de_capsulas, migrations.RunPython.noop),
    ]
