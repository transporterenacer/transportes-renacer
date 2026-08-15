from django.db import models

from apps.core.models import AuditMixin


class Client(AuditMixin):
    nombre = models.CharField(max_length=200)
    nit = models.CharField("NIT", max_length=20, unique=True, blank=True, default="")
    contacto = models.CharField(max_length=200, blank=True, default="")
    telefono = models.CharField(max_length=30, blank=True, default="")

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Port(AuditMixin):
    nombre = models.CharField(max_length=200, unique=True)
    ciudad = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        verbose_name = "Puerto"
        verbose_name_plural = "Puertos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class IncidentCategory(AuditMixin):
    nombre = models.CharField(max_length=100, unique=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Categoría de novedad"
        verbose_name_plural = "Categorías de novedades"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
