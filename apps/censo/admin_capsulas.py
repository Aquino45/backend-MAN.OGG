"""Panel de las cápsulas de ayuda: ayudas por dato, catálogo de valores y fichas de especie.

Cada guardado pasa por `full_clean()` y queda en el historial. El catálogo muestra cuántos
árboles vigentes usan cada valor y tiene una vista de solo lectura con los valores que los
árboles usan y el catálogo no tiene. El panel avisa; nunca cambia ni rechaza árboles.
"""

from urllib.parse import urlencode

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.urls import path, reverse
from simple_history.admin import SimpleHistoryAdmin

from apps.censo.models import AyudaCampo, FichaEspecie, ValorCatalogo
from apps.censo.selectores import conteo_de_valores_de_arboles, valores_fuera_del_catalogo
from config.constantes import AYUDA_VALORES_FUERA_DEL_CATALOGO, TITULO_VALORES_FUERA_DEL_CATALOGO


class _AdminDeCapsulas(SimpleHistoryAdmin):
    """Base: valida el modelo entero al guardar, además del formulario."""

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(AyudaCampo)
class AyudaCampoAdmin(_AdminDeCapsulas):
    list_display = ("campo", "titulo", "orden", "activo")
    list_filter = ("activo",)
    search_fields = ("campo", "titulo", "que_es")


@admin.register(ValorCatalogo)
class ValorCatalogoAdmin(_AdminDeCapsulas):
    list_display = ("campo", "valor", "orden", "activo")
    list_filter = ("campo", "activo")
    search_fields = ("valor", "explicacion")
    change_list_template = "admin/censo/valorcatalogo/change_list.html"

    def get_list_display(self, request):
        """Suma la columna con los árboles vigentes que tienen exactamente cada valor."""
        if not hasattr(request, "conteo_de_arboles"):
            request.conteo_de_arboles = conteo_de_valores_de_arboles()

        @admin.display(description="Árboles vigentes")
        def arboles_vigentes(valor_catalogo):
            return request.conteo_de_arboles.get((valor_catalogo.campo, valor_catalogo.valor), 0)

        return (*super().get_list_display(request), arboles_vigentes)

    def get_urls(self):
        """La vista de valores fuera del catálogo va antes de las rutas por id."""
        nombre = f"{self.opts.app_label}_{self.opts.model_name}_fuera"
        propia = path(
            "fuera-del-catalogo/",
            self.admin_site.admin_view(self.fuera_del_catalogo),
            name=nombre,
        )
        return [propia, *super().get_urls()]

    def fuera_del_catalogo(self, request):
        """Solo lectura: valores que usan los árboles vigentes y el catálogo no tiene."""
        if not self.has_view_permission(request):
            raise PermissionDenied
        url_de_alta = reverse(f"admin:{self.opts.app_label}_{self.opts.model_name}_add")
        filas = [
            {**fila, "enlace_de_alta": f"{url_de_alta}?{urlencode(_datos_de_alta(fila))}"}
            for fila in valores_fuera_del_catalogo()
        ]
        contexto = {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "title": TITULO_VALORES_FUERA_DEL_CATALOGO,
            "ayuda": AYUDA_VALORES_FUERA_DEL_CATALOGO,
            "filas": filas,
            "puede_agregar": self.has_add_permission(request),
        }
        return TemplateResponse(
            request, "admin/censo/valorcatalogo/fuera_del_catalogo.html", contexto
        )


def _datos_de_alta(fila):
    """Campo y valor que el formulario de alta trae ya puestos."""
    return {"campo": fila["campo"], "valor": fila["valor"]}


@admin.register(FichaEspecie)
class FichaEspecieAdmin(_AdminDeCapsulas):
    list_display = ("nombre_cientifico", "nombre_comun", "publicada")
    list_filter = ("publicada",)
    search_fields = ("nombre_cientifico", "nombre_comun", "alias")
