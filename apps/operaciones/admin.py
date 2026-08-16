from django.contrib import admin

from apps.operaciones.models import Operation


@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):
    list_display = ("codigo", "buque", "generador_de_carga", "puerto", "fecha_inicio", "estado")
    list_filter = ("estado",)
    search_fields = ("codigo", "buque")
