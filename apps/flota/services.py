from apps.flota.models import VehicleDocument

ALERT_DAYS = 30
ESTADO_NORMAL = "normal"
ESTADO_PROXIMO = "proximo"
ESTADO_VENCIDO = "vencido"


def documento_estado(doc):
    dias = doc.dias_restantes()
    if dias < 0:
        return ESTADO_VENCIDO
    if dias <= ALERT_DAYS:
        return ESTADO_PROXIMO
    return ESTADO_NORMAL


def alertas_vencimiento():
    alerts = []
    for doc in VehicleDocument.objects.select_related("vehicle").all():
        estado = documento_estado(doc)
        if estado in (ESTADO_PROXIMO, ESTADO_VENCIDO):
            alerts.append(
                {
                    "documento": doc,
                    "vehiculo": doc.vehicle,
                    "tipo": doc.get_tipo_display(),
                    "fecha_vencimiento": doc.fecha_vencimiento,
                    "dias": doc.dias_restantes(),
                    "estado": estado,
                }
            )
    alerts.sort(key=lambda a: a["dias"])
    return alerts
