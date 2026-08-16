from decimal import Decimal

from django.db.models import Avg, Count, Max, Sum

from apps.conductores.models import Driver
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.flota.models import Vehicle
from apps.nomina.models import DriverAdvance, Payroll
from apps.operaciones.models import Incident, Operation, Shift
from apps.operaciones.services import detectar_dobles_turnos


def ultima_actualizacion(*modelos):
    actual = None
    for modelo in modelos:
        ts = modelo.objects.aggregate(max_ts=Max("updated_at"))["max_ts"]
        if ts and (actual is None or ts > actual):
            actual = ts
    return actual


def kpis_inicio():
    activas = Operation.objects.filter(estado=Operation.ACTIVA)
    horas_trabajadas = (
        Shift.objects.filter(estado=Shift.REALIZADO)
        .aggregate(total=Sum("horas_trabajadas"))["total"]
        or Decimal(0)
    )
    horas_facturables = (
        BillingRecord.objects.aggregate(total=Sum("horas"))["total"] or Decimal(0)
    )
    valor_generado = (
        BillingRecord.objects.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )
    abonos = (
        ClientPayment.objects.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )
    nomina_pendiente = (
        Payroll.objects.exclude(estado=Payroll.PAGADO)
        .aggregate(total=Sum("total"))["total"]
        or Decimal(0)
    )
    return {
        "operaciones_activas": activas.count(),
        "mulas_en_operacion": Vehicle.objects.filter(estado=Vehicle.EN_OPERACION).count(),
        "mulas_disponibles": Vehicle.objects.filter(estado=Vehicle.DISPONIBLE).count(),
        "mulas_en_taller": Vehicle.objects.filter(estado=Vehicle.EN_TALLER).count(),
        "horas_trabajadas": horas_trabajadas,
        "horas_facturables": horas_facturables,
        "valor_generado": valor_generado,
        "abonos": abonos,
        "saldo_pendiente": valor_generado - abonos,
        "nomina_semanal_pendiente": nomina_pendiente,
    }


def kpis_nomina(desde, hasta):
    turnos = Shift.objects.filter(
        estado=Shift.REALIZADO,
        fecha_inicio__date__gte=desde,
        fecha_inicio__date__lte=hasta,
    )
    pendientes = turnos.filter(payroll_items__isnull=True)
    total = (
        pendientes.aggregate(total=Sum("valor_pagado"))["total"] or Decimal(0)
    )
    horas = turnos.aggregate(total=Sum("horas_trabajadas"))["total"] or Decimal(0)
    abonos = (
        DriverAdvance.objects.filter(fecha__gte=desde, fecha__lte=hasta)
        .aggregate(total=Sum("valor"))["total"]
        or Decimal(0)
    )

    ranking_horas = list(
        turnos.values("driver__nombre", "driver__documento")
        .annotate(horas=Sum("horas_trabajadas"))
        .order_by("-horas")[:5]
    )
    ranking_turnos = list(
        turnos.values("driver__nombre", "driver__documento")
        .annotate(turnos=Count("id"))
        .order_by("-turnos")[:5]
    )

    return {
        "total": total,
        "horas": horas,
        "abonos": abonos,
        "neto": total - abonos,
        "conductores": turnos.values("driver").distinct().count(),
        "turnos": turnos.count(),
        "ranking_horas": ranking_horas,
        "ranking_turnos": ranking_turnos,
        "dobles_turnos": detectar_dobles_turnos(desde=desde, hasta=hasta),
    }


def kpis_financiero():
    valor_generado = (
        BillingRecord.objects.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )
    abonos = (
        ClientPayment.objects.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )

    por_operacion = []
    for op in Operation.objects.filter(
        billing_records__isnull=False
    ).distinct().prefetch_related("billing_records", "client_payments"):
        facturado = (
            op.billing_records.aggregate(total=Sum("valor"))["total"] or Decimal(0)
        )
        abonado = (
            op.client_payments.aggregate(total=Sum("valor"))["total"] or Decimal(0)
        )
        por_operacion.append(
            {
                "codigo": op.codigo,
                "pk": op.pk,
                "facturado": facturado,
                "abonado": abonado,
                "saldo": facturado - abonado,
            }
        )
    por_operacion.sort(key=lambda x: x["saldo"], reverse=True)
    mayor_saldo = por_operacion[:5]

    evolucion = list(
        BillingRecord.objects.values("fecha")
        .annotate(total=Sum("valor"))
        .order_by("fecha")
    )

    return {
        "valor_generado": valor_generado,
        "abonos": abonos,
        "saldo": valor_generado - abonos,
        "por_operacion": por_operacion,
        "mayor_saldo": mayor_saldo,
        "evolucion": evolucion,
    }


def kpis_operativo():
    realizados = Shift.objects.filter(estado=Shift.REALIZADO)

    horas_por_operacion = list(
        realizados.values("operation__codigo")
        .annotate(horas=Sum("horas_trabajadas"))
        .order_by("-horas")
    )
    horas_por_mula = list(
        realizados.values("vehicle__placa")
        .annotate(horas=Sum("horas_trabajadas"))
        .order_by("-horas")
    )

    cumplimiento = realizados.aggregate(avg=Avg("cumplimiento_pct"))["avg"]

    horas_perdidas = Decimal(0)
    for shift in realizados.only("meta_horas", "horas_trabajadas"):
        perdidas = float(shift.meta_horas) - float(shift.horas_trabajadas)
        if perdidas > 0:
            horas_perdidas += Decimal(perdidas)

    principales_novedades = list(
        Incident.objects.values("categoria__nombre")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    operaciones_menor_cumplimiento = list(
        realizados.values("operation__codigo", "operation__id")
        .annotate(avg_cumpl=Avg("cumplimiento_pct"))
        .order_by("avg_cumpl")[:5]
    )

    return {
        "horas_por_operacion": horas_por_operacion,
        "horas_por_mula": horas_por_mula,
        "cumplimiento_promedio": round(float(cumplimiento), 1) if cumplimiento else None,
        "horas_perdidas": horas_perdidas,
        "principales_novedades": principales_novedades,
        "operaciones_menor_cumplimiento": operaciones_menor_cumplimiento,
    }


def bloques_gantt(operation):
    shifts = operation.shifts.select_related("vehicle", "incidente__categoria").order_by(
        "fecha_inicio"
    )
    filas = {}
    for shift in shifts:
        filas.setdefault(shift.vehicle.placa, {"placa": shift.vehicle.placa, "bloques": []})
        novedad = ""
        if hasattr(shift, "incidente"):
            novedad = shift.incidente.categoria.nombre
        filas[shift.vehicle.placa]["bloques"].append(
            {
                "id": shift.pk,
                "inicio": shift.fecha_inicio.isoformat(),
                "fin": shift.fecha_fin.isoformat(),
                "horas": float(shift.horas_trabajadas),
                "cumplimiento": float(shift.cumplimiento_pct),
                "tipo": shift.get_tipo_display(),
                "estado": shift.estado,
                "novedad": novedad,
                "mula": shift.vehicle.placa,
            }
        )
    return [
        {"placa": placa, "bloques": sorted(f["bloques"], key=lambda b: b["inicio"])}
        for placa, f in sorted(filas.items())
    ]
