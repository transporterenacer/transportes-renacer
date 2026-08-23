from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from apps.flota.models import Vehicle
from apps.operaciones.forms import OperationForm, ShiftForm, ShiftStopFormSet
from apps.operaciones.models import Operation, Shift
from apps.operaciones.services import (
    asignar_mulas,
    cancelar_turno,
    liberar_mula,
    registrar_turno,
)


@login_required
def operacion_list(request):
    operaciones = Operation.objects.filter(
        estado__in=[Operation.PROGRAMADA, Operation.ACTIVA]
    ).order_by("-fecha_inicio")
    return render(request, "operaciones/operacion_list.html", {"operaciones": operaciones})


@login_required
def operacion_detail(request, pk):
    operation = get_object_or_404(
        Operation.objects.prefetch_related("shifts__vehicle", "shifts__driver", "mulas__vehicle"),
        pk=pk,
    )
    asignadas = operation.mulas.filter(activa=True).values_list("vehicle_id", flat=True)
    disponibles = Vehicle.objects.filter(estado=Vehicle.DISPONIBLE).exclude(
        pk__in=asignadas
    )
    return render(
        request,
        "operaciones/operacion_detail.html",
        {"operation": operation, "mulas_disponibles": disponibles},
    )


@login_required
def operacion_nueva(request):
    if request.method == "POST":
        form = OperationForm(request.POST)
        if form.is_valid():
            operation = form.save()
            asignar_mulas(operation, form.cleaned_data["mulas"])
            return redirect("operaciones:detalle", pk=operation.pk)
    else:
        form = OperationForm()
    return render(request, "operaciones/operacion_list.html", {"form": form, "creando": True})


@login_required
def turno_operacion(request):
    operaciones = Operation.objects.filter(
        estado__in=[Operation.PROGRAMADA, Operation.ACTIVA]
    ).order_by("-fecha_inicio")
    return render(request, "operaciones/turno_operacion.html", {"operaciones": operaciones})


@login_required
def turno_nuevo(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    form = ShiftForm(request.POST or None)
    has_stops_data = any(k.startswith("stops-") for k in request.POST) if request.method == "POST" else False
    stop_formset = ShiftStopFormSet(request.POST if has_stops_data else None, prefix="stops")
    mulas = operation.mulas.filter(activa=True)
    form.fields["vehicle"].queryset = Vehicle.objects.filter(
        pk__in=mulas.values("vehicle")
    )
    if request.method == "POST" and form.is_valid() and (not has_stops_data or stop_formset.is_valid()):
        data = form.cleaned_data
        stops = []
        if has_stops_data:
            for stop_form in stop_formset:
                if stop_form.cleaned_data and not stop_form.cleaned_data.get("DELETE", False):
                    ini = stop_form.cleaned_data["inicio"]
                    fin = stop_form.cleaned_data["fin"]
                    base_date = data["fecha_inicio"].date()
                    stops.append({
                        "inicio": datetime.combine(base_date, datetime.strptime(ini, "%H:%M").time()),
                        "fin": datetime.combine(base_date, datetime.strptime(fin, "%H:%M").time()),
                    })
        registrar_turno(
            operation=operation,
            vehicle=data["vehicle"],
            driver=data["driver"],
            fecha_inicio=data["fecha_inicio"].replace(tzinfo=None),
            fecha_fin=data["fecha_fin"].replace(tzinfo=None),
            tipo=data["tipo"],
            valor_estandar=operation.valor_turno_dia if data["tipo"] == "dia" else operation.valor_turno_noche,
            meta_horas=operation.meta_horas,
            novedad_categoria=data.get("novedad_categoria"),
            novedad_descripcion=data.get("novedad_descripcion", ""),
            retirar_mula=data.get("liberar_mula", False),
            stops=stops if stops else None,
        )
        return redirect("operaciones:detalle", pk=operation.pk)
    return render(
        request, "operaciones/shift_form.html",
        {"form": form, "stop_formset": stop_formset, "operation": operation},
    )


@login_required
def mula_liberar(request, pk, vehicle_pk):
    operation = get_object_or_404(Operation, pk=pk)
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk)
    if request.method == "POST":
        liberar_mula(operation, vehicle)
    return redirect("operaciones:detalle", pk=operation.pk)


@login_required
def mula_agregar(request, pk, vehicle_pk):
    operation = get_object_or_404(Operation, pk=pk)
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk)
    if request.method == "POST":
        if vehicle.estado == Vehicle.DISPONIBLE:
            asignar_mulas(operation, [vehicle])
    return redirect("operaciones:detalle", pk=operation.pk)


@login_required
def turno_cancelar(request, pk):
    shift = get_object_or_404(Shift, pk=pk)
    if request.method == "POST":
        try:
            cancelar_turno(shift, request.POST.get("motivo", ""), usuario=request.user)
        except ValidationError as exc:
            return render(
                request,
                "operaciones/error.html",
                {"mensaje": exc.message, "volver": "operaciones:detalle",
                 "volver_pk": shift.operation_id, "codigo": 409},
                status=409,
            )
    return redirect("operaciones:detalle", pk=shift.operation_id)
