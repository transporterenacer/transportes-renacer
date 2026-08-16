from apps.nomina.models import Payroll


def generar_numero_liquidacion(anio):
    prefix = f"NOM-{anio}-"
    ultimo = (
        Payroll.objects.filter(numero__startswith=prefix)
        .order_by("-numero")
        .first()
    )
    if ultimo is None:
        return f"{prefix}001"
    secuencia = int(ultimo.numero.rsplit("-", 1)[1]) + 1
    return f"{prefix}{secuencia:03d}"
