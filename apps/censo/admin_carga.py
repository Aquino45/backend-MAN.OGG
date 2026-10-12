"""Panel «Cargar planilla»: subir el .xlsx, ver el resumen, revisar lo dudoso y confirmar.

Nada se guarda hasta confirmar. Solo quien subió el archivo puede revisarlo, confirmarlo o
cancelarlo, y solo con el permiso `cargar_planilla`. La lógica vive en
`servicios/carga_planilla.py`.
"""

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

from apps.censo.models import LoteCarga
from apps.censo.servicios.carga_planilla import evaluar
from apps.censo.servicios.lectura_planilla import leer
from apps.censo.servicios.lote_carga import (
    campos_a_corregir,
    cancelar_lote,
    codigo_con_varias_conservadas,
    confirmar_lote,
    ediciones_del_formulario,
    filas_con_problema,
    mensajes_de_no_incorporacion,
    registrar_lote,
    valores_activos_del_catalogo,
)
from config.constantes import (
    BYTES_POR_MB,
    CAMPO_ARCHIVO_CARGA,
    ESTADO_LOTE_CONFIRMADO,
    ESTADO_LOTE_VALIDADO,
    ESTADO_REGISTRO_EN_REVISION,
    EXTENSION_PLANILLA,
    FILAS_MAXIMAS_PLANILLA,
    FORMATO_ALERTA_PROBLEMAS,
    FORMATO_ALERTA_UN_PROBLEMA,
    FORMATO_FECHA_LOTE_CARGA,
    FORMATO_RESULTADO_CARGA,
    FORMATO_RESUMEN_CARGA,
    FORMATO_SIN_PROBLEMAS,
    HORAS_VIDA_LOTE_CARGA,
    LOTES_RECIENTES_EN_CARGA,
    MENSAJE_CARGA_CANCELADA,
    MENSAJE_CARGA_LOTE_CERRADO,
    MENSAJE_CARGA_MUY_GRANDE,
    MENSAJE_CARGA_NO_ES_XLSX,
    MENSAJE_CARGA_SIN_ARCHIVO,
    MENSAJE_CARGA_UN_SOLO_CODIGO,
    PARAMETRO_FILTRO_ESTADO_REGISTRO,
    PERMISO_CARGAR_PLANILLA,
    PREFIJO_CAMPO_CARGA,
    PREFIJO_CONSERVAR_CARGA,
    TAMANO_MAXIMO_PLANILLA_BYTES,
    TEXTOS_CARGA_PLANILLA,
    TIPO_CAMPO_LISTA,
)

RUTAS = (
    ("resumen", "<int:lote_id>/"),
    ("revisar", "<int:lote_id>/revisar/"),
    ("no", "<int:lote_id>/no/"),
    ("confirmar", "<int:lote_id>/confirmar/"),
    ("cancelar", "<int:lote_id>/cancelar/"),
    ("resultado", "<int:lote_id>/resultado/"),
)
"""Nombre de cada pantalla y su ruta bajo la de «Cargar planilla»."""


@admin.register(LoteCarga)
class CargaPlanillaAdmin(admin.ModelAdmin):
    """«Cargar planilla» en el índice del panel; la lista de lotes es la pantalla de subida."""

    def has_module_permission(self, request):
        return self._puede_cargar(request)

    def has_view_permission(self, request, obj=None):
        return self._puede_cargar(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        prefijo = f"{self.opts.app_label}_{self.opts.model_name}"
        propias = [
            path(
                ruta, self.admin_site.admin_view(getattr(self, nombre)), name=f"{prefijo}_{nombre}"
            )
            for nombre, ruta in RUTAS
        ]
        return [*propias, *super().get_urls()]

    def changelist_view(self, request, extra_context=None):
        return self.subir(request)

    # --- pantallas -------------------------------------------------------------------------------

    def subir(self, request):
        """Formulario de subida; al subir un archivo válido, sigue el resumen del lote."""
        self._exigir_permiso(request)
        LoteCarga.objects.purgar_vencidos(HORAS_VIDA_LOTE_CARGA)
        if request.method == "POST":
            lote = self._registrar_subida(request)
            if lote is not None:
                return redirect(self._url("resumen", lote))
        recientes = LoteCarga.objects.filter(usuario=request.user)[:LOTES_RECIENTES_EN_CARGA]
        return self._pantalla(
            request,
            "subir",
            campo_archivo=CAMPO_ARCHIVO_CARGA,
            extension=EXTENSION_PLANILLA,
            lotes=recientes,
            estado_validado=ESTADO_LOTE_VALIDADO,
            formato_fecha=FORMATO_FECHA_LOTE_CARGA,
            es_subida=True,
        )

    def resumen(self, request, lote_id):
        """Cuántas filas hay de cada clase y, si hay problemas, la alerta con Sí y No."""
        lote = self._lote_propio(request, lote_id)
        if lote.estado != ESTADO_LOTE_VALIDADO:
            return self._lote_cerrado(request)
        problemas = lote.con_campos_vacios + lote.inconsistentes + lote.duplicados
        formato = FORMATO_ALERTA_UN_PROBLEMA if problemas == 1 else FORMATO_ALERTA_PROBLEMAS
        return self._pantalla(
            request,
            "resumen",
            lote=lote,
            problemas=problemas,
            resumen=FORMATO_RESUMEN_CARGA.format(
                listos=lote.listos,
                vacios=lote.con_campos_vacios,
                inconsistentes=lote.inconsistentes,
                duplicados=lote.duplicados,
            ),
            alerta=formato.format(total=problemas),
            sin_problemas=FORMATO_SIN_PROBLEMAS,
        )

    def revisar(self, request, lote_id):
        """Una fila por registro con problemas: campos a corregir y la casilla «Conservar»."""
        lote = self._lote_propio(request, lote_id)
        if lote.estado != ESTADO_LOTE_VALIDADO:
            return self._lote_cerrado(request)
        filas = list(filas_con_problema(lote))
        activos = valores_activos_del_catalogo()
        if request.method != "POST":
            return self._pantalla_de_revision(request, lote, filas, activos, None)
        conservadas = {f.pk for f in filas if request.POST.get(f"{PREFIJO_CONSERVAR_CARGA}{f.pk}")}
        repetido = codigo_con_varias_conservadas(filas, conservadas)
        if repetido is not None:
            messages.error(request, MENSAJE_CARGA_UN_SOLO_CODIGO.format(codigo=repetido))
            return self._pantalla_de_revision(request, lote, filas, activos, request.POST)
        ediciones = ediciones_del_formulario(
            filas,
            activos,
            lambda pk, campo: request.POST.get(f"{PREFIJO_CAMPO_CARGA}{pk}-{campo}"),
        )
        return self._confirmar(request, lote, conservadas, ediciones)

    def no(self, request, lote_id):
        """Segunda alerta: qué pasa con cada código con problemas si no se revisa."""
        lote = self._lote_propio(request, lote_id)
        if lote.estado != ESTADO_LOTE_VALIDADO:
            return self._lote_cerrado(request)
        return self._pantalla(
            request, "no_incorporar", lote=lote, avisos=mensajes_de_no_incorporacion(lote)
        )

    @method_decorator(require_POST)
    def confirmar(self, request, lote_id):
        """Incorpora solo los registros buenos; lo que tiene problemas no entra."""
        lote = self._lote_propio(request, lote_id)
        return self._confirmar(request, lote, None, None)

    @method_decorator(require_POST)
    def cancelar(self, request, lote_id):
        """Descarta el lote sin guardar nada."""
        lote = self._lote_propio(request, lote_id)
        try:
            cancelar_lote(lote)
        except ValueError as error:
            messages.error(request, str(error))
        else:
            messages.info(request, MENSAJE_CARGA_CANCELADA)
        return redirect(self._url_de_subida())

    def resultado(self, request, lote_id):
        """Cuántos registros se publicaron, quedaron en revisión o no se incorporaron."""
        lote = self._lote_propio(request, lote_id)
        if lote.estado != ESTADO_LOTE_CONFIRMADO:
            return self._lote_cerrado(request)
        textos = TEXTOS_CARGA_PLANILLA
        grupos = [
            (textos["etiqueta_codigos_publicados"], lote.resultado["publicados"]),
            (textos["etiqueta_codigos_en_revision"], lote.resultado["en_revision"]),
            (textos["etiqueta_codigos_no_incorporados"], lote.resultado["no_incorporados"]),
            (textos["etiqueta_codigos_ejemplo"], lote.resultado["ejemplo_sin_cambios"]),
        ]
        enlace = f"{reverse('admin:censo_arbol_changelist')}?"
        enlace += f"{PARAMETRO_FILTRO_ESTADO_REGISTRO}={ESTADO_REGISTRO_EN_REVISION}"
        return self._pantalla(
            request,
            "resultado",
            lote=lote,
            grupos=grupos,
            enlace_en_revision=enlace,
            resumen=FORMATO_RESULTADO_CARGA.format(
                **{clave: len(codigos) for clave, codigos in lote.resultado.items()}
            ),
        )

    # --- apoyo -----------------------------------------------------------------

    def _puede_cargar(self, request):
        return request.user.has_perm(f"{self.opts.app_label}.{PERMISO_CARGAR_PLANILLA}")

    def _exigir_permiso(self, request):
        if not self._puede_cargar(request):
            raise PermissionDenied

    def _lote_propio(self, request, lote_id):
        """El lote, si quien pregunta tiene el permiso y es quien lo subió."""
        self._exigir_permiso(request)
        lote = get_object_or_404(LoteCarga, pk=lote_id)
        if lote.usuario_id != request.user.pk:
            raise PermissionDenied
        return lote

    def _url(self, nombre, lote):
        return reverse(
            f"admin:{self.opts.app_label}_{self.opts.model_name}_{nombre}", args=[lote.pk]
        )

    def _url_de_subida(self):
        return reverse(f"admin:{self.opts.app_label}_{self.opts.model_name}_changelist")

    def _lote_cerrado(self, request):
        messages.error(request, MENSAJE_CARGA_LOTE_CERRADO)
        return redirect(self._url_de_subida())

    def _confirmar(self, request, lote, conservadas, ediciones):
        try:
            confirmar_lote(lote, conservadas, ediciones)
        except ValueError as error:
            messages.error(request, str(error))
            lote.refresh_from_db()
            if lote.estado == ESTADO_LOTE_VALIDADO:
                return redirect(self._url("resumen", lote))
            return redirect(self._url_de_subida())
        return redirect(self._url("resultado", lote))

    def _registrar_subida(self, request):
        """Valida el archivo subido y crea el lote; con un problema avisa y devuelve None."""
        archivo = request.FILES.get(CAMPO_ARCHIVO_CARGA)
        if archivo is None:
            error = MENSAJE_CARGA_SIN_ARCHIVO
        elif not archivo.name.lower().endswith(EXTENSION_PLANILLA):
            error = MENSAJE_CARGA_NO_ES_XLSX
        elif archivo.size > TAMANO_MAXIMO_PLANILLA_BYTES:
            maximo_mb = TAMANO_MAXIMO_PLANILLA_BYTES / BYTES_POR_MB
            error = MENSAJE_CARGA_MUY_GRANDE.format(maximo_mb=maximo_mb)
        else:
            error = None
        if error is None:
            contenido = archivo.read()
            try:
                planilla = leer(
                    contenido, nombre_archivo=archivo.name, filas_maximas=FILAS_MAXIMAS_PLANILLA
                )
                return registrar_lote(request.user, archivo.name, contenido, evaluar(planilla))
            except ValueError as problema:
                error = str(problema)
        messages.error(request, error)
        return None

    def _pantalla_de_revision(self, request, lote, filas, activos, enviado):
        """Las filas con problemas; con `enviado` (el POST) se conserva lo que el usuario puso."""
        revisadas = []
        for fila in filas:
            campos = campos_a_corregir(fila, activos)
            for campo in campos:
                nombre = f"{PREFIJO_CAMPO_CARGA}{fila.pk}-{campo['campo']}"
                if enviado is not None:
                    campo["valor"] = enviado.get(nombre, campo["valor"])
                campo["nombre"] = nombre
                campo["en_planilla"] = (
                    TEXTOS_CARGA_PLANILLA["texto_en_planilla"].format(
                        valor=campo["valor_en_planilla"]
                    )
                    if campo["valor_en_planilla"]
                    else ""
                )
                campo["fuera_de_la_lista"] = (
                    campo["tipo"] == TIPO_CAMPO_LISTA
                    and campo["valor"] != ""
                    and campo["valor"] not in campo["opciones"]
                )
            revisadas.append(
                {
                    "fila": fila,
                    "motivos": [motivo["porque"] for motivo in fila.motivos],
                    "campos": campos,
                    "nombre_conservar": f"{PREFIJO_CONSERVAR_CARGA}{fila.pk}",
                    "conservar": enviado is not None
                    and bool(enviado.get(f"{PREFIJO_CONSERVAR_CARGA}{fila.pk}")),
                }
            )
        return self._pantalla(request, "revisar", lote=lote, revisadas=revisadas)

    def _pantalla(self, request, plantilla, **contexto):
        textos = TEXTOS_CARGA_PLANILLA
        contexto = {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "title": textos["titulo"],
            "textos": textos,
            "url_de_subida": self._url_de_subida(),
            **contexto,
        }
        return TemplateResponse(request, f"admin/censo/carga/{plantilla}.html", contexto)
