from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("apps.dashboard.urls")),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("operaciones/", include("apps.operaciones.urls")),
    path("nomina/", include("apps.nomina.urls")),
    path("facturacion/", include("apps.facturacion.urls")),
    path("documentos/", include("apps.documentos.urls")),
]
