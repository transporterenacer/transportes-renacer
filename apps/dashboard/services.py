from decimal import Decimal

from django.db.models import Avg, Count, Max, Sum

from apps.conductores.models import Driver
from apps.facturacion.services import (
    info_facturacion_operacion,
    resumen_global,
)
from apps.flota.models import Vehicle
from apps.nomina.models import DriverAdvance
from apps.nomina.services import nomina_pendiente_actual
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
    globales = resumen_global()
    nomina_pendiente = nomina_pendiente_actual()
    return {
        "operaciones_activas": activas.count(),
        "mulas_en_operacion": Vehicle.objects.filter(estado=Vehicle.EN_OPERACION).count(),
        "mulas_disponibles": Vehicle.objects.filter(estado=Vehicle.DISPONIBLE).count(),
        "mulas_en_taller": Vehicle.objects.filter(estado=Vehicle.EN_TALLER).count(),
        "horas_trabajadas": globales["horas_trabajadas"],
        "horas_relacionadas": globales["horas_relacionadas"],
        "horas_pendientes": globales["horas_pendientes"],
        "valor_generado": globales["valor_generado"],
        "abonos": globales["abonos"],
        "saldo_pendiente": globales["saldo"],
        "nomina_pendiente": nomina_pendiente,
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
        DriverAdvance.objects.filter(
            fecha__gte=desde, fecha__lte=hasta, payroll__isnull=True
        )
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
    globales = resumen_global()

    por_operacion = []
    for op in Operation.objects.select_related("generador_de_carga").exclude(
        estado=Operation.CANCELADA
    ):
        info = info_facturacion_operacion(op)
        if (
            info["horas_trabajadas"] <= 0
            and info["saldo"] <= 0
            and not op.client_payments.exists()
        ):
            continue
        por_operacion.append(
            {
                "codigo": op.codigo,
                "pk": op.pk,
                "buque": op.buque,
                "valor_generado": info["valor_generado"],
                "horas_pendientes": info["horas_pendientes"],
                "abonado": info["abonado"],
                "saldo": info["saldo"],
            }
        )
    por_operacion.sort(key=lambda x: x["saldo"], reverse=True)
    mayor_saldo = por_operacion[:5]

    tarifas = dict(Operation.objects.values_list("id", "tarifa_hora"))
    por_fecha = {}
    for fecha, op_id, horas in (
        Shift.objects.filter(estado=Shift.REALIZADO)
        .values_list("fecha_inicio__date", "operation", "horas_trabajadas")
    ):
        por_fecha[fecha] = por_fecha.get(fecha, Decimal(0)) + Decimal(
            horas
        ) * tarifas.get(op_id, Decimal(0))
    evolucion = [{"fecha": f, "total": t} for f, t in sorted(por_fecha.items())]

    return {
        "valor_generado": globales["valor_generado"],
        "abonos": globales["abonos"],
        "saldo": globales["saldo"],
        "horas_pendientes": globales["horas_pendientes"],
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
        "cumplimiento_promedio": round(float(cumplimiento), 1) if cumplimiento is not None else None,
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


def bloques_gantt_rango(desde=None, hasta=None, solo_activas=False):
    shifts = Shift.objects.select_related(
        "vehicle", "operation", "incidente__categoria"
    ).order_by("fecha_inicio")
    if desde is not None:
        shifts = shifts.filter(fecha_inicio__date__gte=desde)
    if hasta is not None:
        shifts = shifts.filter(fecha_inicio__date__lte=hasta)
    if solo_activas:
        shifts = shifts.filter(operation__estado=Operation.ACTIVA)

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
                "operacion": shift.operation.codigo,
            }
        )
    return [
        {"placa": placa, "bloques": sorted(f["bloques"], key=lambda b: b["inicio"])}
        for placa, f in sorted(filas.items())
    ]
