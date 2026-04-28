from django.urls import path
from .views import TripPlanView, autocomplete_view

urlpatterns = [
    path("trip/plan", TripPlanView.as_view()),
    path("geocode/autocomplete", autocomplete_view),
]
