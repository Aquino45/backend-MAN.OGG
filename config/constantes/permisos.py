"""Roles del panel y permisos de cada rol."""

NOMBRE_ROL_ADMINISTRADOR = "Administrador"
"""Grupo del panel con todo sobre árboles y sectores, la papelera completa y la marca demo."""

NOMBRE_ROL_EDITOR = "Editor"
"""Grupo del panel que crea y edita árboles, los manda a la papelera y los restaura."""

PERMISO_CAMBIAR_DEMO = "cambiar_demo"
"""Permiso propio de Arbol: solo quien lo tiene cambia la marca `demo`."""

PERMISOS_POR_ROL = {
    NOMBRE_ROL_ADMINISTRADOR: (
        "add_arbol",
        "change_arbol",
        "delete_arbol",
        "view_arbol",
        PERMISO_CAMBIAR_DEMO,
        "add_sector",
        "change_sector",
        "view_sector",
        "view_arbolenpapelera",
        "change_arbolenpapelera",
        "delete_arbolenpapelera",
    ),
    NOMBRE_ROL_EDITOR: (
        "add_arbol",
        "change_arbol",
        "delete_arbol",
        "view_arbol",
        "view_sector",
        "view_arbolenpapelera",
        "change_arbolenpapelera",
    ),
}
"""Permisos de cada rol. `delete_arbol` solo manda a la papelera; borrar en definitiva es
`delete_arbolenpapelera`. Los sectores nunca se borran desde el panel."""

_PERMISOS_DE_CAPSULAS = ("ayudacampo", "valorcatalogo")

PERMISOS_CAPSULAS_POR_ROL = {
    NOMBRE_ROL_ADMINISTRADOR: tuple(
        f"{accion}_{modelo}"
        for modelo in _PERMISOS_DE_CAPSULAS
        for accion in ("add", "change", "delete", "view")
    ),
    NOMBRE_ROL_EDITOR: tuple(
        f"{accion}_{modelo}"
        for modelo in _PERMISOS_DE_CAPSULAS
        for accion in ("add", "change", "view")
    ),
}
"""Permisos de las ayudas y el catálogo. Ambos roles agregan, editan y ven; solo el Administrador
borra. La ficha de una especie se edita con la especie (`PERMISOS_CATALOGOS_POR_ROL`)."""

PERMISO_CARGAR_PLANILLA = "cargar_planilla"
"""Permiso propio de LoteCarga: quien lo tiene ve «Cargar planilla» en el panel."""

PERMISOS_CARGA_POR_ROL = {
    NOMBRE_ROL_ADMINISTRADOR: (PERMISO_CARGAR_PLANILLA,),
    NOMBRE_ROL_EDITOR: (PERMISO_CARGAR_PLANILLA,),
}
"""Ambos roles cargan la planilla."""

_PERMISOS_DE_CATALOGOS = ("especie", "brigada", "grupobrigada")

PERMISOS_CATALOGOS_POR_ROL = {
    NOMBRE_ROL_ADMINISTRADOR: tuple(
        f"{accion}_{modelo}"
        for modelo in _PERMISOS_DE_CATALOGOS
        for accion in ("add", "change", "delete", "view")
    ),
    NOMBRE_ROL_EDITOR: tuple(
        f"{accion}_{modelo}"
        for modelo in _PERMISOS_DE_CATALOGOS
        for accion in ("add", "change", "view")
    ),
}
"""Permisos de especies, brigadas y grupos: el Administrador hace todo; el Editor agrega, edita y
ve."""

PERMISO_EDITAR_MARCA_UBICACION = "change_sector"
"""Quien puede quitar o poner a mano la marca de ubicación corregida en el panel: quien edita las
fronteras de los sectores, que hoy es solo el Administrador."""
