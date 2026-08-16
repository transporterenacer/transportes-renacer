from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.models import AuditMixin
from apps.conductores.models import Driver
from apps.flota.models import Vehicle


def content_type_vehicle():
    return ContentType.objects.get_for_model(Vehicle)


def content_type_driver():
    return ContentType.objects.get_for_model(Driver)


class DocumentType(AuditMixin):
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, unique=True)
    entity_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, related_name="document_types"
    )
    requires_expiration = models.BooleanField(default=False)
    requires_issue_date = models.BooleanField(default=False)
    allow_multiple = models.BooleanField(default=False)
    replace_previous = models.BooleanField(default=False)
    keep_history = models.BooleanField(default=True)
    is_required = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tipo de documento"
        verbose_name_plural = "Tipos de documento"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
