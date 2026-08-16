from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port
from apps.conductores.models import Driver
from apps.core.models import AuditMixin
from apps.flota.models import Vehicle


class Operation(AuditMixin):
    PROGRAMADA = "programada"
    ACTIVA = "activa"
    FINALIZADA = "finalizada"
    CANCELADA = "cancelada"

    ESTADOS = [
        (PROGRAMADA, "Programada"),
        (ACTIVA, "Activa"),
        (FINALIZADA, "Finalizada"),
        (CANCELADA, "Cancelada"),
    ]

    codigo = models.CharField(max_length=20, unique=True)
    buque = models.CharField(max_length=200)
    generador_de_carga = models.ForeignKey(
        CargoGenerator, on_delete=models.PROTECT, related_name="operaciones"
    )
    puerto = models.ForeignKey(Port, on_delete=models.PROTECT, related_name="operaciones")
    fecha_inicio = models.DateField()
    fecha_fin_estimada = models.DateField(null=True, blank=True)
    fecha_fin_real = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=PROGRAMADA)
    meta_horas = models.DecimalField(max_digits=4, decimal_places=1, default=11)
    tarifa_hora = models.DecimalField(max_digits=14, decimal_places=0)
    valor_turno_dia = models.DecimalField(max_digits=14, decimal_places=0)
    valor_turno_noche = models.DecimalField(max_digits=14, decimal_places=0)
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Operación"
        verbose_name_plural = "Operaciones"
        ordering = ["fecha_inicio", "codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.buque}"

    @property
    def estado_activa(self):
        return self.estado == self.ACTIVA

    @property
    def total_horas(self):
        total = sum(
            shift.horas_trabajadas
            for shift in self.shifts.filter(estado=Shift.REALIZADO)
        )
        return Decimal(total)


class OperationVehicle(AuditMixin):
    operation = models.ForeignKey(
        Operation, on_delete=models.CASCADE, related_name="mulas"
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="operaciones"
    )
    fecha_asignacion = models.DateField(default=timezone.localdate)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Mula asignada"
        verbose_name_plural = "Mulas asignadas"
        unique_together = (("operation", "vehicle"),)


class Shift(AuditMixin):
    DIA = "dia"
    NOCHE = "noche"

    TIPOS = [
        (DIA, "Día"),
        (NOCHE, "Noche"),
    ]

    PROGRAMADO = "programado"
    REALIZADO = "realizado"
    CANCELADO = "cancelado"
    ANULADO = "anulado"

    ESTADOS = [
        (PROGRAMADO, "Programado"),
        (REALIZADO, "Realizado"),
        (CANCELADO, "Cancelado"),
        (ANULADO, "Anulado"),
    ]

    operation = models.ForeignKey(
        Operation, on_delete=models.PROTECT, related_name="shifts"
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.PROTECT, related_name="shifts"
    )
    driver = models.ForeignKey(
        Driver, on_delete=models.PROTECT, related_name="shifts"
    )
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    horas_trabajadas = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    meta_horas = models.DecimalField(max_digits=4, decimal_places=1)
    cumplimiento_pct = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    valor_estandar = models.DecimalField(max_digits=14, decimal_places=0)
    valor_pagado = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=PROGRAMADO)
    motivo_cancelacion = models.TextField(blank=True, default="")
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Turno"
        verbose_name_plural = "Turnos"
        ordering = ["fecha_inicio"]

    def __str__(self):
        return f"{self.vehicle.placa} {self.fecha_inicio:%d/%m %H:%M}"

    def save(self, *args, **kwargs):
        delta = self.fecha_fin - self.fecha_inicio
        self.horas_trabajadas = round(delta.total_seconds() / 3600, 2)
        if self.meta_horas:
            self.cumplimiento_pct = round(
                float(self.horas_trabajadas) / float(self.meta_horas) * 100, 1
            )
        estado_anterior = None
        if self.pk:
            estado_anterior = (
                Shift.objects.filter(pk=self.pk)
                .values_list("estado", flat=True)
                .first()
            )
        if estado_anterior is None or estado_anterior != self.estado:
            if self.estado == self.REALIZADO:
                self.valor_pagado = self.valor_estandar
            else:
                self.valor_pagado = 0
        super().save(*args, **kwargs)

    @property
    def valor_es_pagable(self):
        return self.estado == self.REALIZADO


class Incident(AuditMixin):
    shift = models.OneToOneField(
        Shift, on_delete=models.CASCADE, related_name="incidente"
    )
    categoria = models.ForeignKey(
        IncidentCategory, on_delete=models.PROTECT, related_name="incidentes"
    )
    descripcion = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Novedad"
        verbose_name_plural = "Novedades"

    def __str__(self):
        return f"{self.categoria.nombre} - {self.shift}"
