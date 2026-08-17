from django.contrib import admin
from django.urls import include, path

from apps.core.views import RedirectAuthenticatedLoginView

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        RedirectAuthenticatedLoginView.as_view(
            template_name="registration/login.html"
        ),
        name="login",
    ),
    path("accounts/", include("django.contrib.auth.urls")),
    path("operaciones/", include("apps.operaciones.urls")),
    path("nomina/", include("apps.nomina.urls")),
    path("facturacion/", include("apps.facturacion.urls")),
    path("documentos/", include("apps.documentos.urls")),
    path("flota/", include("apps.flota.urls")),
    path("conductores/", include("apps.conductores.urls")),
    path("catalogos/", include("apps.catalogos.urls")),
    path("", include("apps.dashboard.urls")),
]
