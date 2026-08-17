from django.urls import path

from apps.conductores import views

app_name = "conductores"

urlpatterns = [
    path("", views.conductores_lista, name="lista"),
    path("nuevo/", views.conductor_nuevo, name="nuevo"),
    path("<int:pk>/editar/", views.conductor_editar, name="editar"),
]