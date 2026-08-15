from django.db import models
from django.utils import timezone

from apps.core.models import AuditMixin


class Vehicle(AuditMixin):
    DISPONIBLE = "disponible"
    EN_OPERACION = "en_operacion"
    EN_TALLER = "en_taller"
    FUERA_DE_SERVICIO = "fuera_de_servicio"

    ESTADOS = [
        (DISPONIBLE, "Disponible"),
        (EN_OPERACION, "En operación"),
        (EN_TALLER, "En taller"),
        (FUERA_DE_SERVICIO, "Fuera de servicio"),
    ]

    placa = models.CharField(max_length=10, unique=True)
    marca = models.CharField(max_length=100, blank=True, default="")
    modelo = models.CharField(max_length=100, blank=True, default="")
    anio = models.PositiveIntegerField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=DISPONIBLE)
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Vehículo"
        verbose_name_plural = "Vehículos"
        ordering = ["placa"]

    def __str__(self):
        return self.placa

    def save(self, *args, **kwargs):
        self.placa = self.placa.upper()
        super().save(*args, **kwargs)


class VehicleDocument(AuditMixin):
    SOAT = "soat"
    TECNOMECANICA = "tecnomecanica"

    TIPOS = [
        (SOAT, "SOAT"),
        (TECNOMECANICA, "Técnico-mecánica"),
    ]

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="documentos"
    )
    tipo = models.CharField(max_length=20, choices=TIPOS)
    fecha_vencimiento = models.DateField()

    class Meta:
        verbose_name = "Documento de vehículo"
        verbose_name_plural = "Documentos de vehículos"
        ordering = ["fecha_vencimiento"]
        unique_together = (("vehicle", "tipo"),)

    def __str__(self):
        return f"{self.get_tipo_display()} {self.vehicle.placa}"

    def dias_restantes(self):
        return (self.fecha_vencimiento - timezone.localdate()).days
