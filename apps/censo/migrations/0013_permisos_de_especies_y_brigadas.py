"""Da a Administrador y Editor los permisos de especies, brigadas y grupos.

Solo agrega permisos, nunca quita los que el grupo ya tenía, así que se puede repetir. Los permisos
de los modelos nuevos todavía no existen cuando corre esta migración, así que se crean aquí antes de
asignarlos. También quita el tipo de contenido de la ficha de especie, que ya no existe, y con él
sus permisos.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

from config.constantes import PERMISOS_CATALOGOS_POR_ROL

MODELOS_QUE_YA_NO_EXISTEN = ("fichaespecie", "historicalfichaespecie")


def sumar_permisos(apps, schema_editor):
    """Agrega a cada grupo los permisos de `PERMISOS_CATALOGOS_POR_ROL`."""
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
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(app_label="censo", model__in=MODELOS_QUE_YA_NO_EXISTEN).delete()
    for nombre_rol, codigos in PERMISOS_CATALOGOS_POR_ROL.items():
        grupo, _ = Group.objects.get_or_create(name=nombre_rol)
        permisos = Permission.objects.filter(content_type__app_label="censo", codename__in=codigos)
        grupo.permissions.add(*permisos)


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("censo", "0012_quita_textos_y_fichas"),
    ]

    operations = [
        migrations.RunPython(sumar_permisos, migrations.RunPython.noop),
    ]
