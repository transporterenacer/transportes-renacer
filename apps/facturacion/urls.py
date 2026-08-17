from django.urls import path

from apps.facturacion import views

app_name = "facturacion"

urlpatterns = [
    path("", views.facturacion_lista, name="lista"),
    path("<int:pk>/", views.facturacion_detail, name="detalle"),
    path("<int:pk>/relaciones/nueva/", views.relacion_nueva, name="relacion_nueva"),
    path(
        "<int:pk>/relaciones/<str:numero>/",
        views.relacion_detalle,
        name="relacion_detalle",
    ),
    path("<int:pk>/abonos/nuevo/", views.abono_nuevo, name="abono"),
    path("<int:pk>/csv/", views.csv_facturacion, name="csv"),
    path("resumen/csv/", views.csv_resumen, name="csv_resumen"),
]
