from django.urls import path

from apps.flota import views

app_name = "flota"

urlpatterns = [
    path("", views.flota_lista, name="lista"),
    path("nuevo/", views.vehiculo_nuevo, name="nuevo"),
    path("<int:pk>/editar/", views.vehiculo_editar, name="editar"),
]