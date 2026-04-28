from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

from routing.ors_client import GeocodingError, RoutingError


def api_exception_handler(exc, context):
    if isinstance(exc, GeocodingError):
        return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    if isinstance(exc, RoutingError):
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    return exception_handler(exc, context)
