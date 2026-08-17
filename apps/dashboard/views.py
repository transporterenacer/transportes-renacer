from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.dashboard.services import (
    bloques_gantt,
    bloques_gantt_rango,
    kpis_financiero,
    kpis_inicio,
    kpis_nomina,
    kpis_operativo,
    ultima_actualizacion,
)
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.flota.models import Vehicle, VehicleDocument
from apps.flota.services import alertas_vencimiento
from apps.nomina.models import DriverAdvance, Payroll
from apps.operaciones.models import Incident, Operation, Shift


@login_required
def dashboard_inicio(request):
    context = {
        "kpis": kpis_inicio(),
        "operaciones_activas": Operation.objects.filter(estado=Operation.ACTIVA),
        "alertas": alertas_vencimiento(),
        "hoy": timezone.localdate(),
        "ultima_actualizacion": ultima_actualizacion(
            Operation, Shift, BillingRecord, ClientPayment, Payroll
        ),
    }
    context["flota"] = {
        "total": Vehicle.objects.count(),
        "en_operacion": Vehicle.objects.filter(estado=Vehicle.EN_OPERACION).count(),
        "disponibles": Vehicle.objects.filter(estado=Vehicle.DISPONIBLE).count(),
        "en_taller": Vehicle.objects.filter(estado=Vehicle.EN_TALLER).count(),
        "fuera_de_servicio": Vehicle.objects.filter(
            estado=Vehicle.FUERA_DE_SERVICIO
        ).count(),
    }
    context["horas_por_operacion"] = (
        Shift.objects.filter(estado=Shift.REALIZADO)
        .values("operation__codigo", "operation__buque")
        .annotate(horas=Sum("horas_trabajadas"))
        .order_by("-horas")[:6]
    )
    return render(request, "dashboard/inicio.html", context)


@login_required
def dashboard_vencimientos(request):
    context = {
        "alertas": alertas_vencimiento(),
        "flota": {
            "total": Vehicle.objects.count(),
            "en_operacion": Vehicle.objects.filter(estado=Vehicle.EN_OPERACION).count(),
            "disponibles": Vehicle.objects.filter(estado=Vehicle.DISPONIBLE).count(),
            "en_taller": Vehicle.objects.filter(estado=Vehicle.EN_TALLER).count(),
            "fuera_de_servicio": Vehicle.objects.filter(estado=Vehicle.FUERA_DE_SERVICIO).count(),
        },
        "ultima_actualizacion": ultima_actualizacion(Vehicle, VehicleDocument),
    }
    return render(request, "dashboard/vencimientos.html", context)


@login_required
def dashboard_nomina(request):
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")
    try:
        desde = timezone.datetime.strptime(desde, "%Y-%m-%d").date()
        hasta = timezone.datetime.strptime(hasta, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        desde = timezone.localdate() - timezone.timedelta(days=6)
        hasta = timezone.localdate()
    context = {
        "kpis": kpis_nomina(desde, hasta),
        "desde": desde,
        "hasta": hasta,
        "ultima_actualizacion": ultima_actualizacion(Payroll, Shift, DriverAdvance),
    }
    return render(request, "dashboard/nomina.html", context)


@login_required
def dashboard_operativo(request):
    context = {
        "kpis": kpis_operativo(),
        "ultima_actualizacion": ultima_actualizacion(Operation, Shift, Incident),
    }
    return render(request, "dashboard/operativo.html", context)


@login_required
def dashboard_financiero(request):
    context = {
        "kpis": kpis_financiero(),
        "ultima_actualizacion": ultima_actualizacion(BillingRecord, ClientPayment),
    }
    return render(request, "dashboard/financiero.html", context)


@login_required
def dashboard_historial(request):
    operaciones = (
        Operation.objects.filter(
            estado__in=[Operation.FINALIZADA, Operation.CANCELADA]
        )
        .annotate(
            num_turnos=Count("shifts", filter=Q(shifts__estado=Shift.REALIZADO)),
            horas_totales=Sum(
                "shifts__horas_trabajadas",
                filter=Q(shifts__estado=Shift.REALIZADO),
            ),
        )
        .order_by("-fecha_inicio")
    )
    context = {"operaciones": operaciones}
    return render(request, "dashboard/historial.html", context)


@login_required
def dashboard_gantt(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    context = {
        "operation": operation,
        "ultima_actualizacion": ultima_actualizacion(Operation, Shift, Incident),
    }
    return render(request, "dashboard/gantt.html", context)


@login_required
def gantt_datos(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    data = {
        "operation": {
            "codigo": operation.codigo,
            "buque": operation.buque,
            "meta_horas": float(operation.meta_horas),
            "fecha_inicio": operation.fecha_inicio.isoformat(),
            "fecha_fin_estimada": (
                operation.fecha_fin_estimada.isoformat()
                if operation.fecha_fin_estimada
                else None
            ),
        },
        "filas": bloques_gantt(operation),
    }
    return JsonResponse(data)


def _rango_semana(request):
    hoy = timezone.localdate()
    desde = hoy - timezone.timedelta(days=hoy.weekday())
    hasta = desde + timezone.timedelta(days=6)
    try:
        desde = timezone.datetime.strptime(request.GET.get("desde", ""), "%Y-%m-%d").date()
        hasta = desde + timezone.timedelta(days=6)
    except ValueError:
        pass
    return desde, hasta


@login_required
def dashboard_gantt_semana(request):
    desde, hasta = _rango_semana(request)
    solo_activas = request.GET.get("solo_activas") == "1"
    context = {
        "desde": desde,
        "hasta": hasta,
        "desde_prev": desde - timezone.timedelta(days=7),
        "desde_next": desde + timezone.timedelta(days=7),
        "solo_activas": solo_activas,
        "ultima_actualizacion": ultima_actualizacion(Operation, Shift, Incident),
    }
    return render(request, "dashboard/gantt_semana.html", context)


@login_required
def gantt_datos_semana(request):
    desde, hasta = _rango_semana(request)
    solo_activas = request.GET.get("solo_activas") == "1"
    data = {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "solo_activas": solo_activas,
        "filas": bloques_gantt_rango(
            desde=desde, hasta=hasta, solo_activas=solo_activas
        ),
    }
    return JsonResponse(data)
