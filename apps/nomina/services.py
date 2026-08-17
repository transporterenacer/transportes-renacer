from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.conductores.models import Driver
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


def semana_para(fecha):
    """Devuelve (lunes, domingo) de la semana de `fecha`."""
    lunes = fecha - timedelta(days=fecha.weekday())
    domingo = lunes + timedelta(days=6)
    return lunes, domingo


def semana_anterior(lunes):
    return lunes - timedelta(days=7)


def semana_siguiente(lunes):
    return lunes + timedelta(days=7)


def turnos_pendientes_pago(desde, hasta):
    desde_dt = timezone.make_aware(datetime.combine(desde, time.min))
    hasta_dt = timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min))
    return (
        Shift.objects.filter(
            estado=Shift.REALIZADO,
            fecha_inicio__gte=desde_dt,
            fecha_inicio__lt=hasta_dt,
            payroll_items__isnull=True,
        )
        .select_related("driver", "vehicle", "operation")
        .order_by("fecha_inicio")
    )


def _items_conductor(driver):
    return PayrollItem.objects.filter(shift__driver=driver).select_related(
        "shift", "payroll"
    ).order_by(
        "payroll__periodo_inicio",
        "payroll__periodo_fin",
        "shift__fecha_inicio",
        "shift__fecha_fin",
        "id",
    )


def recalcular_fifo(driver):
    """Reconciliación FIFO: reparte abonos+pagos sobre los turnos del conductor.

    Orden determinista: turnos por antigüedad (período, fecha) y avances por
    fecha. Escribe `PayrollItem.pagado`. Idempotente.
    """
    advances = list(
        DriverAdvance.objects.filter(driver=driver).order_by("fecha", "id")
    )
    disponible = sum((a.valor for a in advances), start=Decimal(0))
    cambiados = []
    for item in _items_conductor(driver):
        pagado = min(item.valor, disponible) if disponible > 0 else Decimal(0)
        if item.pagado != pagado:
            item.pagado = pagado
            cambiados.append(item)
        disponible -= pagado
    for item in cambiados:
        item.save(update_fields=["pagado"])


def saldo_conductor(driver):
    """Saldo acumulado del conductor: pendiente, saldo a favor y desglose."""
    recalcular_fifo(driver)
    saldo_pendiente = Decimal(0)
    cubiertos = 0
    detalle = []
    for item in _items_conductor(driver).select_related(
        "shift__vehicle", "shift__operation"
    ):
        pendiente = item.valor - item.pagado
        if pendiente > 0:
            saldo_pendiente += pendiente
        else:
            cubiertos += 1
        detalle.append(
            {
                "periodo": item.payroll,
                "shift": item.shift,
                "valor": item.valor,
                "pagado": item.pagado,
                "pendiente": pendiente,
                "estado": "cubierto" if pendiente == 0 else "pendiente",
            }
        )
    abonos = Decimal(0)
    pagos = Decimal(0)
    for adv in DriverAdvance.objects.filter(driver=driver):
        if adv.tipo == DriverAdvance.PAGO:
            pagos += adv.valor
        else:
            abonos += adv.valor
    total_valor = sum((d["valor"] for d in detalle), start=Decimal(0))
    saldo_a_favor = max(Decimal(0), (abonos + pagos) - total_valor)
    estado = "pagado" if saldo_pendiente == 0 else (
        "parcial" if cubiertos > 0 else "pendiente"
    )
    return {
        "saldo_pendiente": saldo_pendiente,
        "saldo_a_favor": saldo_a_favor,
        "total_turnos": len(detalle),
        "turnos_cubiertos": cubiertos,
        "turnos_pendientes": len(detalle) - cubiertos,
        "items": detalle,
        "abonos": abonos,
        "pagos": pagos,
        "estado": estado,
    }


def conductor_pagado(driver):
    return saldo_conductor(driver)["saldo_pendiente"] == 0


def crear_liquidacion(desde, hasta, usuario=None):
    turnos = list(turnos_pendientes_pago(desde, hasta))
    if not turnos:
        raise ValidationError(
            "No hay turnos pendientes de pago en el periodo seleccionado."
        )
    solape = Payroll.objects.filter(
        periodo_inicio__lte=hasta, periodo_fin__gte=desde
    ).exists()
    if solape:
        raise ValidationError(
            "Ya existe una liquidación que se superpone con el período seleccionado."
        )
    conductores = set()
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
            conductores.add(shift.driver_id)
            PayrollItem.objects.create(
                payroll=payroll, shift=shift, valor=shift.valor_pagado
            )
        payroll.total = total
        payroll.save(update_fields=["total"])
    for driver in Driver.objects.filter(pk__in=conductores):
        recalcular_fifo(driver)
    return payroll


def _estado_periodo(total, pagado):
    if pagado >= total:
        return "pagado"
    if pagado > 0:
        return "parcial"
    return "pendiente"


def resumen_liquidacion(payroll):
    items = (
        payroll.items.select_related("shift__driver", "shift__vehicle")
        .order_by("shift__driver__nombre", "shift__fecha_inicio")
    )
    resumen = {}
    for item in items:
        driver = item.shift.driver
        if driver.pk not in resumen:
            resumen[driver.pk] = {
                "driver": driver,
                "turnos": 0,
                "horas": Decimal(0),
                "total": Decimal(0),
                "cubierto": Decimal(0),
                "pendiente": Decimal(0),
                "estado": "pendiente",
            }
        fila = resumen[driver.pk]
        fila["turnos"] += 1
        fila["horas"] += item.shift.horas_trabajadas
        fila["total"] += item.valor
        fila["cubierto"] += item.pagado
    for fila in resumen.values():
        fila["pendiente"] = fila["total"] - fila["cubierto"]
        fila["estado"] = _estado_periodo(fila["total"], fila["cubierto"])
    return sorted(resumen.values(), key=lambda f: f["driver"].nombre)


def estado_nomina(payroll):
    resumen = resumen_liquidacion(payroll)
    total = sum((fila["total"] for fila in resumen), start=Decimal(0))
    cubierto = sum((fila["cubierto"] for fila in resumen), start=Decimal(0))
    pendiente = total - cubierto
    if not resumen:
        estado = "pendiente"
    elif all(fila["estado"] == "pagado" for fila in resumen):
        estado = "pagado"
    elif any(fila["estado"] == "pagado" for fila in resumen):
        estado = "parcial"
    else:
        estado = "pendiente"
    return {
        "total": total,
        "cubierto": cubierto,
        "pendiente": pendiente,
        "estado": estado,
        "porcentaje": cubierto / total * 100 if total else 0,
        "conductores_pagados": sum(
            1 for fila in resumen if fila["estado"] == "pagado"
        ),
        "conductores_total": len(resumen),
    }


def nomina_pendiente_actual():
    """Cuánto se les debe hoy a todos los conductores (acumulado global)."""
    agg = PayrollItem.objects.aggregate(total=Sum("valor"), pagado=Sum("pagado"))
    return (agg["total"] or Decimal(0)) - (agg["pagado"] or Decimal(0))


def registrar_abono(
    driver,
    valor,
    descripcion="",
    fecha=None,
    usuario=None,
    metodo=DriverAdvance.EFECTIVO,
):
    if valor <= 0:
        raise ValidationError("El valor del abono debe ser mayor a cero.")
    with transaction.atomic():
        abono = DriverAdvance.objects.create(
            driver=driver,
            fecha=fecha or timezone.localdate(),
            valor=valor,
            descripcion=descripcion,
            tipo=DriverAdvance.ADELANTO,
            metodo=metodo,
            created_by=usuario,
            updated_by=usuario,
        )
        recalcular_fifo(driver)
    return abono


def registrar_pago(driver, valor, metodo=DriverAdvance.EFECTIVO, usuario=None):
    if valor <= 0:
        raise ValidationError("El valor del pago debe ser mayor a cero.")
    saldo = saldo_conductor(driver)["saldo_pendiente"]
    if valor > saldo:
        raise ValidationError(
            f"El pago ($ {valor:,.0f}) supera el saldo pendiente del conductor "
            f"($ {saldo:,.0f})."
        )
    with transaction.atomic():
        pago = DriverAdvance.objects.create(
            driver=driver,
            fecha=timezone.localdate(),
            valor=valor,
            descripcion="Pago de nómina",
            tipo=DriverAdvance.PAGO,
            metodo=metodo,
            created_by=usuario,
            updated_by=usuario,
        )
        recalcular_fifo(driver)
    return pago


def turno_en_payroll(shift):
    return shift.payroll_items.exists()


def alertas_nomina():
    alertas = []
    valores_modificados = (
        Shift.objects.filter(
            estado=Shift.REALIZADO,
            payroll_items__isnull=False,
        )
        .exclude(valor_pagado=F("valor_estandar"))
        .select_related("driver")
    )[:10]
    for shift in valores_modificados:
        alertas.append(
            {
                "tipo": "valor_modificado",
                "texto": (
                    f"{shift.driver.nombre} tiene un turno del "
                    f"{shift.fecha_inicio:%d/%m} con valor modificado "
                    f"(${shift.valor_estandar:,.0f} → ${shift.valor_pagado:,.0f})."
                ),
            }
        )
    anulados_liquidados = (
        Shift.objects.filter(
            estado__in=[Shift.CANCELADO, Shift.ANULADO],
            payroll_items__isnull=False,
        ).select_related("driver")
    )[:10]
    for shift in anulados_liquidados:
        alertas.append(
            {
                "tipo": "anulado_liquidado",
                "texto": (
                    f"El turno del {shift.fecha_inicio:%d/%m} de "
                    f"{shift.driver.nombre} fue anulado después de incluirse en una nómina."
                ),
            }
        )
    return alertas