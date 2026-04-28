from django.urls import include, path
from django.http import JsonResponse


def health(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("api/health", health),
    path("api/", include("trips.urls")),
]
