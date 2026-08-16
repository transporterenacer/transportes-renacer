from django.urls import path

from apps.nomina import views

app_name = "nomina"

urlpatterns = [
    path("", views.payroll_list, name="lista"),
    path("nueva/", views.payroll_nueva, name="nueva"),
    path("<int:pk>/", views.payroll_detail, name="detalle"),
    path("<int:pk>/abonos/nuevo/", views.abono_nuevo, name="abono_nuevo"),
    path("<int:pk>/marcar-pagada/", views.marcar_pagada, name="marcar_pagada"),
]
