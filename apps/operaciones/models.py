from django.db import models

from apps.catalogos.models import CargoGenerator, Port
from apps.core.models import AuditMixin


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
            for shift in self.shifts.filter(estado="realizado")
        )
        return total
