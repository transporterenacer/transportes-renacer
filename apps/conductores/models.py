from django.db import models

from apps.core.models import AuditMixin


class Driver(AuditMixin):
    DISPONIBLE = "disponible"
    TRABAJANDO = "trabajando"
    INACTIVO = "inactivo"

    ESTADOS = [
        (DISPONIBLE, "Disponible"),
        (TRABAJANDO, "Trabajando"),
        (INACTIVO, "Inactivo"),
    ]

    nombre = models.CharField(max_length=200)
    documento = models.CharField(max_length=30, unique=True)
    telefono = models.CharField(max_length=30, blank=True, default="")
    estado = models.CharField(max_length=20, choices=ESTADOS, default=DISPONIBLE)
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Conductor"
        verbose_name_plural = "Conductores"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
