from django.urls import path

from apps.documentos import views

app_name = "documentos"

urlpatterns = [
    path("", views.panel, name="panel"),
    path("vehicle/<int:pk>/", views.ficha_vehicle, name="vehicle"),
    path("driver/<int:pk>/", views.ficha_driver, name="driver"),
    path("subir/", views.subir, name="subir"),
    path("<int:pk>/ver/", views.ver, name="ver"),
    path("<int:pk>/descargar/", views.descargar, name="descargar"),
    path("<int:pk>/reemplazar/", views.reemplazar, name="reemplazar"),
    path("driver/<int:pk>/desactivar/", views.desactivar_conductor, name="desactivar_conductor"),
    path("vehicle/<int:pk>/desactivar/", views.desactivar_vehiculo, name="desactivar_vehiculo"),
    path("media/<path:storage_path>", views.media, name="media"),
    path("api/tipos/crear/", views.api_crear_documento_tipo, name="api_documento_tipo_crear"),
]
