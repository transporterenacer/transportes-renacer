from django.utils import timezone

from apps.documentos.models import Document, content_type_vehicle

ALERT_DAYS = 30
ESTADO_NORMAL = "normal"
ESTADO_PROXIMO = "proximo"
ESTADO_VENCIDO = "vencido"


def documento_estado(doc):
    if not doc.fecha_vencimiento:
        return ESTADO_NORMAL
    dias = (doc.fecha_vencimiento - timezone.localdate()).days
    if dias < 0:
        return ESTADO_VENCIDO
    if dias <= ALERT_DAYS:
        return ESTADO_PROXIMO
    return ESTADO_NORMAL


def alertas_vencimiento():
    alerts = []
    for doc in (
        Document.objects.select_related("tipo", "entity_type")
        .filter(entity_type=content_type_vehicle(), estado=Document.VIGENTE)
        .exclude(fecha_vencimiento__isnull=True)
    ):
        estado = documento_estado(doc)
        if estado in (ESTADO_PROXIMO, ESTADO_VENCIDO):
            alerts.append(
                {
                    "documento": doc,
                    "vehiculo": doc.entity,
                    "tipo": doc.tipo.nombre,
                    "fecha_vencimiento": doc.fecha_vencimiento,
                    "dias": (doc.fecha_vencimiento - timezone.localdate()).days,
                    "estado": estado,
                }
            )
    alerts.sort(key=lambda a: a["dias"])
    return alerts
