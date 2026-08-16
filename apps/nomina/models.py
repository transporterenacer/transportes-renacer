from django.db import models
from django.utils import timezone

from apps.conductores.models import Driver
from apps.core.models import AuditMixin
from apps.operaciones.models import Shift


class Payroll(AuditMixin):
    PENDIENTE = "pendiente"
    LIQUIDADO = "liquidado"
    PAGADO = "pagado"

    ESTADOS = [
        (PENDIENTE, "Pendiente"),
        (LIQUIDADO, "Liquidado"),
        (PAGADO, "Pagado"),
    ]

    numero = models.CharField(max_length=20, unique=True)
    periodo_inicio = models.DateField()
    periodo_fin = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default=PENDIENTE)
    total = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    fecha_pago = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Liquidación de nómina"
        verbose_name_plural = "Liquidaciones de nómina"
        ordering = ["-periodo_inicio"]

    def __str__(self):
        return self.numero


class PayrollItem(AuditMixin):
    payroll = models.ForeignKey(
        Payroll, on_delete=models.CASCADE, related_name="items"
    )
    shift = models.ForeignKey(
        Shift, on_delete=models.PROTECT, related_name="payroll_items", unique=True
    )
    valor = models.DecimalField(max_digits=14, decimal_places=0)

    class Meta:
        verbose_name = "Item de liquidación"
        verbose_name_plural = "Items de liquidación"

    def __str__(self):
        return f"{self.payroll.numero} - {self.shift}"


class DriverAdvance(AuditMixin):
    driver = models.ForeignKey(
        Driver, on_delete=models.PROTECT, related_name="abonos"
    )
    fecha = models.DateField(default=timezone.localdate)
    valor = models.DecimalField(max_digits=14, decimal_places=0)
    descripcion = models.CharField(max_length=200, blank=True, default="")
    payroll = models.ForeignKey(
        Payroll, null=True, blank=True, on_delete=models.SET_NULL, related_name="abonos"
    )

    class Meta:
        verbose_name = "Abono a conductor"
        verbose_name_plural = "Abonos a conductores"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.driver.nombre} ${self.valor}"
