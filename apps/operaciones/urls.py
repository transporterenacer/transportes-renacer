from django.urls import path

from apps.operaciones import views

app_name = "operaciones"

urlpatterns = [
    path("", views.operacion_list, name="lista"),
    path("nueva/", views.operacion_nueva, name="nuevo"),
    path("<int:pk>/", views.operacion_detail, name="detalle"),
    path("<int:pk>/turnos/nuevo/", views.turno_nuevo, name="turno_nuevo"),
    path("turnos/<int:pk>/cancelar/", views.turno_cancelar, name="turno_cancelar"),
]
