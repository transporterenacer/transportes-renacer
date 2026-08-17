from django.urls import path

from apps.operaciones import views

app_name = "operaciones"

urlpatterns = [
    path("", views.operacion_list, name="lista"),
    path("nueva/", views.operacion_nueva, name="nuevo"),
    path("turnos/nuevo/", views.turno_operacion, name="turno_operacion"),
    path("<int:pk>/", views.operacion_detail, name="detalle"),
    path("<int:pk>/turnos/nuevo/", views.turno_nuevo, name="turno_nuevo"),
    path("turnos/<int:pk>/cancelar/", views.turno_cancelar, name="turno_cancelar"),
    path("<int:pk>/mulas/<int:vehicle_pk>/liberar/", views.mula_liberar, name="mula_liberar"),
    path("<int:pk>/mulas/<int:vehicle_pk>/agregar/", views.mula_agregar, name="mula_agregar"),
]
