from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="inicio.html"), name="inicio"),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("operaciones/", include("apps.operaciones.urls")),
    path("nomina/", include("apps.nomina.urls")),
    path("facturacion/", include("apps.facturacion.urls")),
]
