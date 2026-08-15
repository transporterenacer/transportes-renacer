from django.contrib import admin

from apps.flota.models import Vehicle, VehicleDocument


class VehicleDocumentInline(admin.TabularInline):
    model = VehicleDocument
    extra = 0


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("placa", "marca", "modelo", "anio", "estado")
    list_filter = ("estado",)
    search_fields = ("placa", "marca")
    inlines = [VehicleDocumentInline]


@admin.register(VehicleDocument)
class VehicleDocumentAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "tipo", "fecha_vencimiento", "dias_restantes")
    list_filter = ("tipo",)
