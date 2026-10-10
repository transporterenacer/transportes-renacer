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
    # Viajes locales
    path("viajes/", views.viaje_lista, name="viaje_lista"),
    path("viajes/nuevo/", views.viaje_nuevo, name="viaje_nuevo"),
    path("viajes/<int:pk>/", views.viaje_detalle, name="viaje_detalle"),
    path("viajes/<int:pk>/iniciar/", views.viaje_iniciar, name="viaje_iniciar"),
    path("viajes/<int:pk>/finalizar/", views.viaje_finalizar, name="viaje_finalizar"),
    path("viajes/<int:pk>/cancelar/", views.viaje_cancelar, name="viaje_cancelar"),
    path("viajes/<int:pk>/gastos/", views.viaje_gasto_lista, name="viaje_gastos"),
    path("viajes/<int:pk>/gastos/nuevo/", views.viaje_gasto_nuevo, name="viaje_gasto_nuevo"),
    path("viajes/<int:pk>/gastos/<int:gasto_pk>/editar/", views.viaje_gasto_editar, name="viaje_gasto_editar"),
    path("viajes/<int:pk>/gastos/<int:gasto_pk>/eliminar/", views.viaje_gasto_eliminar, name="viaje_gasto_eliminar"),
]
