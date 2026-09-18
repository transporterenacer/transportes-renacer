from django.contrib import admin

from apps.operaciones.models import Operation, OperationExpense


@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):
    list_display = ("codigo", "buque", "generador_de_carga", "puerto", "fecha_inicio", "estado")
    list_filter = ("estado",)
    search_fields = ("codigo", "buque")


@admin.register(OperationExpense)
class OperationExpenseAdmin(admin.ModelAdmin):
    list_display = ("operation", "vehicle", "categoria", "fecha", "valor", "proveedor")
    list_filter = ("categoria",)
    search_fields = ("operation__codigo", "vehicle__placa")
