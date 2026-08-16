from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from apps.dashboard.services import kpis_inicio, ultima_actualizacion
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.flota.models import Vehicle, VehicleDocument
from apps.flota.services import alertas_vencimiento
from apps.nomina.models import Payroll
from apps.operaciones.models import Operation, Shift


@login_required
def dashboard_inicio(request):
    context = {
        "kpis": kpis_inicio(),
        "operaciones_activas": Operation.objects.filter(estado=Operation.ACTIVA),
        "ultima_actualizacion": ultima_actualizacion(
            Operation, Shift, BillingRecord, ClientPayment, Payroll
        ),
    }
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
    context = {
        "ultima_actualizacion": ultima_actualizacion(Payroll),
    }
    return render(request, "dashboard/nomina.html", context)


@login_required
def dashboard_operativo(request):
    context = {
        "ultima_actualizacion": ultima_actualizacion(Operation, Shift),
    }
    return render(request, "dashboard/operativo.html", context)


@login_required
def dashboard_financiero(request):
    context = {
        "ultima_actualizacion": ultima_actualizacion(BillingRecord, ClientPayment),
    }
    return render(request, "dashboard/financiero.html", context)


@login_required
def dashboard_historial(request):
    context = {
        "operaciones": Operation.objects.filter(
            estado__in=[Operation.FINALIZADA, Operation.CANCELADA]
        ).order_by("-fecha_inicio"),
    }
    return render(request, "dashboard/historial.html", context)


@login_required
def dashboard_gantt(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    return render(request, "dashboard/gantt.html", {"operation": operation})


@login_required
def gantt_datos(request, pk):
    return JsonResponse({})
