"""Seguridad por defecto de la API: solo lectura y límite de peticiones para anónimos."""

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.throttling import AnonRateThrottle


class SoloLectura(BasePermission):
    """Deja pasar solo GET, HEAD y OPTIONS, aunque una vista se olvide de declararlo."""

    message = "La API es de solo lectura."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


class LimiteAnonimo(AnonRateThrottle):
    """Limita las peticiones por IP; la tasa sale de `API_LIMITE_ANONIMO` en el `.env`."""

    scope = "anonimo"
