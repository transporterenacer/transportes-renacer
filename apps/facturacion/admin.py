from django.contrib import admin

from apps.facturacion.models import BillingRecord, ClientPayment


@admin.register(BillingRecord)
class BillingRecordAdmin(admin.ModelAdmin):
    list_display = ("operation", "shift", "fecha", "horas", "valor", "estado")
    list_filter = ("estado",)
    search_fields = ("operation__codigo",)


@admin.register(ClientPayment)
class ClientPaymentAdmin(admin.ModelAdmin):
    list_display = ("operation", "fecha", "valor")
    search_fields = ("operation__codigo",)
