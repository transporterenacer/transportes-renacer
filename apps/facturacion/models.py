from django.db import models
from django.utils import timezone

from apps.core.models import AuditMixin
from apps.operaciones.models import Operation, Shift


class BillingRecord(AuditMixin):
    PENDIENTE = "pendiente"
    INCLUIDO = "incluido"
    FACTURADO = "facturado"
    COBRADO = "cobrado"

    ESTADOS = [
        (PENDIENTE, "Pendiente"),
        (INCLUIDO, "Incluido"),
        (FACTURADO, "Facturado"),
        (COBRADO, "Cobrado"),
    ]

    operation = models.ForeignKey(
        Operation, on_delete=models.PROTECT, related_name="billing_records"
    )
    numero_relacion = models.CharField(
        max_length=40, blank=True, null=True
    )
    shift = models.ForeignKey(
        Shift,
        on_delete=models.PROTECT,
        related_name="billing_record",
        null=True,
        blank=True,
        unique=True,
    )
    fecha = models.DateField(default=timezone.localdate)
    horas = models.DecimalField(max_digits=5, decimal_places=2)
    tarifa_hora = models.DecimalField(max_digits=14, decimal_places=0)
    valor = models.DecimalField(max_digits=14, decimal_places=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=PENDIENTE)
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Registro de facturación"
        verbose_name_plural = "Registros de facturación"
        ordering = ["fecha"]

    def __str__(self):
        placa = self.shift.vehicle.placa if self.shift_id else "-"
        return f"{self.operation.codigo} - {placa}"


class ClientPayment(AuditMixin):
    EFECTIVO = "efectivo"
    TRANSFERENCIA = "transferencia"

    METODOS = [
        (EFECTIVO, "Efectivo"),
        (TRANSFERENCIA, "Transferencia"),
    ]

    operation = models.ForeignKey(
        Operation, on_delete=models.PROTECT, related_name="client_payments"
    )
    fecha = models.DateField(default=timezone.localdate)
    valor = models.DecimalField(max_digits=14, decimal_places=0)
    metodo = models.CharField(max_length=20, choices=METODOS, default=EFECTIVO)
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Abono del generador de carga"
        verbose_name_plural = "Abonos del generador de carga"
        ordering = ["fecha"]

    def __str__(self):
        return f"{self.operation.codigo} ${self.valor}"
