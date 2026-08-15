from django.contrib import admin

from apps.catalogos.models import Client, IncidentCategory, Port


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("nombre", "nit", "contacto", "telefono")
    search_fields = ("nombre", "nit")


@admin.register(Port)
class PortAdmin(admin.ModelAdmin):
    list_display = ("nombre", "ciudad")
    search_fields = ("nombre",)


@admin.register(IncidentCategory)
class IncidentCategoryAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa")
    list_filter = ("activa",)
