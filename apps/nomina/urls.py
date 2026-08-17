from django.urls import path

from apps.nomina import views

app_name = "nomina"

urlpatterns = [
    path("", views.payroll_list, name="lista"),
    path("nueva/", views.payroll_nueva, name="nueva"),
    path("<int:pk>/", views.payroll_detail, name="detalle"),
    path(
        "conductores/<int:driver_pk>/",
        views.conductor_detail,
        name="conductor",
    ),
    path(
        "conductores/<int:driver_pk>/abonos/nuevo/",
        views.abono_nuevo,
        name="abono_conductor_nuevo",
    ),
    path(
        "conductores/<int:driver_pk>/pagos/nuevo/",
        views.pago_nuevo,
        name="pago_nuevo",
    ),
    path("<int:pk>/exportar/", views.exportar_csv, name="exportar"),
]