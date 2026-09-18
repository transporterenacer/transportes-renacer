from django.urls import path

from apps.catalogos import views

app_name = "catalogos"

urlpatterns = [
    path("configuracion/", views.configuracion, name="configuracion"),
    path("configuracion/catalogos/", views.catalogos, name="catalogos"),
    path("configuracion/puertos/nuevo/", views.crear_puerto, name="puerto_nuevo"),
    path("configuracion/generadores/nuevo/", views.crear_generador, name="generador_nuevo"),
    path("configuracion/categorias/nuevo/", views.crear_categoria, name="categoria_nueva"),
    path("configuracion/proveedores/nuevo/", views.crear_proveedor, name="proveedor_nuevo"),
    path("api/proveedores/crear/", views.api_crear_proveedor, name="api_proveedor_crear"),
    path("api/puertos/crear/", views.api_crear_puerto, name="api_puerto_crear"),
    path("api/generadores/crear/", views.api_crear_generador, name="api_generador_crear"),
]
