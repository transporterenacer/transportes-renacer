from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

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


class Document(AuditMixin):
    VIGENTE = "vigente"
    REEMPLAZADO = "reemplazado"

    ESTADOS = [
        (VIGENTE, "Vigente"),
        (REEMPLAZADO, "Reemplazado"),
    ]

    entity_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, related_name="documentos_doc"
    )
    entity_id = models.PositiveIntegerField()
    entity = GenericForeignKey("entity_type", "entity_id")

    tipo = models.ForeignKey(
        DocumentType, on_delete=models.PROTECT, related_name="documentos"
    )
    nombre_archivo = models.CharField(max_length=255)
    storage_path = models.CharField(max_length=500, unique=True)
    extension = models.CharField(max_length=10)
    mime_type = models.CharField(max_length=100)
    tamano = models.PositiveBigIntegerField(default=0)
    fecha_expedicion = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=VIGENTE)
    cargado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documentos_cargados",
    )
    cargado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ["-cargado_en"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
        ]

    def __str__(self):
        return self.nombre_archivo

    @property
    def es_personal(self):
        return self.entity_type_id == content_type_driver().id


class DocumentAudit(AuditMixin):
    CARGA = "carga"
    REEMPLAZO = "reemplazo"
    BORRADO = "borrado"

    ACCIONES = [
        (CARGA, "Carga"),
        (REEMPLAZO, "Reemplazo"),
        (BORRADO, "Borrado"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documentos_audit",
    )
    accion = models.CharField(max_length=20, choices=ACCIONES)
    entity_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL
    )
    entity_id = models.PositiveIntegerField(null=True, blank=True)
    tipo = models.CharField(max_length=100)
    archivo_anterior = models.CharField(max_length=500, blank=True, default="")
    archivo_nuevo = models.CharField(max_length=500, blank=True, default="")
    detalle = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Auditoría documental"
        verbose_name_plural = "Auditorías documentales"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.accion} {self.tipo}"
