from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.nomina.models import DriverAdvance, Payroll, PayrollItem
from apps.operaciones.models import Shift


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


def turnos_pendientes_pago(desde, hasta):
    return (
        Shift.objects.filter(
            estado=Shift.REALIZADO,
            fecha_inicio__date__gte=desde,
            fecha_inicio__date__lte=hasta,
            payroll_items__isnull=True,
        )
        .select_related("driver", "vehicle", "operation")
        .order_by("fecha_inicio")
    )


def crear_liquidacion(desde, hasta, usuario=None):
    turnos = list(turnos_pendientes_pago(desde, hasta))
    if not turnos:
        raise ValidationError(
            "No hay turnos pendientes de pago en el periodo seleccionado."
        )
    with transaction.atomic():
        payroll = Payroll.objects.create(
            numero=generar_numero_liquidacion(desde.year),
            periodo_inicio=desde,
            periodo_fin=hasta,
            estado=Payroll.LIQUIDADO,
            created_by=usuario,
            updated_by=usuario,
        )
        total = Decimal(0)
        for shift in turnos:
            total += shift.valor_pagado
            PayrollItem.objects.create(
                payroll=payroll, shift=shift, valor=shift.valor_pagado
            )
        payroll.total = total
        payroll.save(update_fields=["total"])
    return payroll


def resumen_liquidacion(payroll):
    items = (
        payroll.items.select_related("shift__driver")
        .order_by("shift__driver__nombre")
    )
    resumen = {}
    for item in items:
        driver = item.shift.driver
        if driver.pk not in resumen:
            resumen[driver.pk] = {
                "driver": driver,
                "total": Decimal(0),
                "abonos": Decimal(0),
                "neto": Decimal(0),
            }
        resumen[driver.pk]["total"] += item.valor
    abonos = (
        payroll.abonos.select_related("driver")
        .values("driver_id")
        .annotate(total=Sum("valor"))
    )
    for fila in abonos:
        pk = fila["driver_id"]
        if pk in resumen:
            resumen[pk]["abonos"] = fila["total"]
    for fila in resumen.values():
        fila["neto"] = fila["total"] - fila["abonos"]
    return sorted(resumen.values(), key=lambda f: f["driver"].nombre)


def marcar_pagada(payroll, usuario=None):
    payroll.estado = Payroll.PAGADO
    payroll.fecha_pago = timezone.localdate()
    if usuario:
        payroll.updated_by = usuario
    payroll.save()
