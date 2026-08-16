from django.contrib import admin

from apps.nomina.models import Payroll


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ("numero", "periodo_inicio", "periodo_fin", "estado", "total", "fecha_pago")
    list_filter = ("estado",)
    search_fields = ("numero",)
