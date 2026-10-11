"""Crea los grupos del panel (Administrador y Editor) con sus permisos.

Se puede repetir sin duplicar nada: los grupos se buscan por nombre y sus permisos se vuelven a
fijar. Los permisos de una BD nueva todavía no existen cuando corre esta migración, así que se
crean aquí antes de asignarlos.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

from config.constantes import PERMISOS_POR_ROL


def crear_grupos(apps, schema_editor):
    """Deja los grupos de roles con exactamente los permisos de `PERMISOS_POR_ROL`."""
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
    for nombre_rol, codigos in PERMISOS_POR_ROL.items():
        grupo, _ = Group.objects.get_or_create(name=nombre_rol)
        permisos = Permission.objects.filter(
            content_type__app_label="censo", codename__in=codigos
        )
        grupo.permissions.set(permisos)


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("censo", "0003_papelera_historial_y_permiso_demo"),
    ]

    operations = [
        migrations.RunPython(crear_grupos, migrations.RunPython.noop),
    ]
