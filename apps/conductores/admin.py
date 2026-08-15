from django.contrib import admin

from apps.conductores.models import Driver


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("nombre", "documento", "telefono", "estado")
    list_filter = ("estado",)
    search_fields = ("nombre", "documento")
