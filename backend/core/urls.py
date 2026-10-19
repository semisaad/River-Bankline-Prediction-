from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("years/", views.years),
    path("banklines/", views.banklines),
    path("erosion/", views.erosion),
    path("erosion/pairs/", views.erosion_years),
    path("predictions/", views.predictions),
    path("risk/", views.risk),
    path("risk/summary/", views.risk_summary),
    path("status/", views.status),
]
