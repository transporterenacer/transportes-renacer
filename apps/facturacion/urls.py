from django.urls import path

from apps.facturacion import views

app_name = "facturacion"

urlpatterns = [
    path("<int:pk>/", views.facturacion_detail, name="detalle"),
    path("<int:pk>/generar/", views.generar_billing, name="generar"),
    path("<int:pk>/abonos/nuevo/", views.abono_nuevo, name="abono"),
    path("<int:pk>/csv/", views.csv_facturacion, name="csv"),
]
