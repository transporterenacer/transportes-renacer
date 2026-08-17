from apps.flota.services import alertas_vencimiento


def notificaciones(request):
    if request is None or not request.user.is_authenticated:
        return {"alertas_count": 0, "alertas": []}
    alertas = alertas_vencimiento()
    return {"alertas_count": len(alertas), "alertas": alertas}
