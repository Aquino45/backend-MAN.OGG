"""Tests del formato único de errores `{"detail": "..."}` y de los manejadores 404 y 500."""

import json
import logging

import pytest
from django.http import Http404, JsonResponse
from django.test import Client, RequestFactory
from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ParseError, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory

from apps.core import excepciones

MENSAJE_SECRETO = "clave-secreta-no-debe-salir"


def _vista_que_lanza(excepcion):
    """Arma una vista de DRF que lanza `excepcion` en cuanto la llaman."""

    @api_view(["GET"])
    @permission_classes([AllowAny])
    def vista(request):
        raise excepcion

    return vista


def _llamar(excepcion):
    peticion = APIRequestFactory().get("/prueba")
    respuesta = _vista_que_lanza(excepcion)(peticion)
    respuesta.render()
    return respuesta


@pytest.mark.parametrize("excepcion", [NotFound(), Http404()])
def test_no_encontrado_responde_404_con_detail_en_espanol(excepcion):
    respuesta = _llamar(excepcion)

    assert respuesta.status_code == 404
    assert respuesta.data == {"detail": excepciones.DETALLE_NO_ENCONTRADO}


def test_permiso_denegado_responde_403_solo_con_detail():
    respuesta = _llamar(PermissionDenied())

    assert respuesta.status_code == 403
    assert list(respuesta.data) == ["detail"]


def test_solicitud_mal_formada_responde_400_solo_con_detail():
    respuesta = _llamar(ParseError())

    assert respuesta.status_code == 400
    assert list(respuesta.data) == ["detail"]


def test_validacion_por_campos_se_aplana_a_detail():
    respuesta = _llamar(ValidationError({"codigo": ["Obligatorio."]}))

    assert respuesta.status_code == 400
    assert respuesta.data == {"detail": "Obligatorio."}


def test_validacion_en_lista_se_aplana_a_detail():
    respuesta = _llamar(ValidationError(["Uno.", "Dos."]))

    assert respuesta.data == {"detail": "Uno. Dos."}


def test_metodo_no_permitido_responde_405_solo_con_detail():
    peticion = APIRequestFactory().post("/prueba")
    vista = api_view(["GET"])(lambda request: None)
    vista.cls.permission_classes = [AllowAny]

    respuesta = vista(peticion)

    assert respuesta.status_code == 405
    assert list(respuesta.data) == ["detail"]


@pytest.mark.parametrize("modo_debug", [False, True])
def test_error_no_controlado_responde_500_sin_traza_ni_mensaje(settings, modo_debug):
    settings.DEBUG = modo_debug

    respuesta = _llamar(RuntimeError(MENSAJE_SECRETO))

    assert respuesta.status_code == 500
    assert respuesta.data == {"detail": excepciones.DETALLE_ERROR_INTERNO}
    assert MENSAJE_SECRETO not in respuesta.content.decode()
    assert "Traceback" not in respuesta.content.decode()


def test_error_no_controlado_queda_registrado_con_su_traza(caplog):
    with caplog.at_level(logging.ERROR, logger=excepciones.__name__):
        _llamar(RuntimeError(MENSAJE_SECRETO))

    registros = [r for r in caplog.records if r.name == excepciones.__name__]
    assert registros
    assert registros[0].exc_info is not None
    assert MENSAJE_SECRETO in str(registros[0].exc_info[1])


def test_no_encontrado_de_django_responde_json_404():
    respuesta = excepciones.no_encontrado(RequestFactory().get("/nada"), Http404())

    assert isinstance(respuesta, JsonResponse)
    assert respuesta.status_code == 404
    assert json.loads(respuesta.content) == {"detail": excepciones.DETALLE_NO_ENCONTRADO}


def test_error_interno_de_django_responde_json_500():
    respuesta = excepciones.error_interno(RequestFactory().get("/nada"))

    assert isinstance(respuesta, JsonResponse)
    assert respuesta.status_code == 500
    assert json.loads(respuesta.content) == {"detail": excepciones.DETALLE_ERROR_INTERNO}


def test_config_urls_apunta_los_handlers_a_excepciones():
    from config import urls

    assert urls.handler404 == "apps.core.excepciones.no_encontrado"
    assert urls.handler500 == "apps.core.excepciones.error_interno"


def test_ruta_inexistente_responde_json_404_por_el_urlconf_real():
    respuesta = Client().get("/ruta/que/no/existe")

    assert respuesta.status_code == 404
    assert json.loads(respuesta.content) == {"detail": excepciones.DETALLE_NO_ENCONTRADO}


def _vista_de_django_que_revienta(request):
    raise RuntimeError(MENSAJE_SECRETO)


urlpatterns = [path("revienta", _vista_de_django_que_revienta)]
handler500 = "apps.core.excepciones.error_interno"


@pytest.mark.urls(__name__)
def test_error_interno_de_django_llega_como_json_sin_filtrar_el_mensaje(settings):
    settings.DEBUG = False

    respuesta = Client(raise_request_exception=False).get("/revienta")

    assert respuesta.status_code == 500
    assert json.loads(respuesta.content) == {"detail": excepciones.DETALLE_ERROR_INTERNO}
    assert MENSAJE_SECRETO not in respuesta.content.decode()
