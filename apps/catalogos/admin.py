from django.contrib import admin

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port, Proveedor


@admin.register(CargoGenerator)
class CargoGeneratorAdmin(admin.ModelAdmin):
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


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("nombre", "nit", "contacto", "telefono", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "nit")
