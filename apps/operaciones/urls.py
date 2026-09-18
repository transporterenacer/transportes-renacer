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
    path("<int:pk>/gastos/", views.gasto_lista, name="gastos"),
    path("<int:pk>/gastos/nuevo/", views.gasto_nuevo, name="gasto_nuevo"),
    path("<int:pk>/gastos/<int:gasto_pk>/editar/", views.gasto_editar, name="gasto_editar"),
    path("<int:pk>/gastos/<int:gasto_pk>/eliminar/", views.gasto_eliminar, name="gasto_eliminar"),
    # Jefe Mecánico routes
    path("mecanico/", views.mechanic_operacion_list, name="mechanic_lista"),
    path("mecanico/<int:pk>/", views.mechanic_operacion_detail, name="mechanic_detail"),
    path("mecanico/<int:op_pk>/mula/<int:vehicle_pk>/gasto/nuevo/", views.mechanic_gasto_nuevo, name="mechanic_gasto_nuevo"),
    path("mecanico/<int:op_pk>/mula/<int:vehicle_pk>/gasto/<int:gasto_pk>/editar/", views.mechanic_gasto_editar, name="mechanic_gasto_editar"),
]
