from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.flota.models import Vehicle
from apps.operaciones.forms import OperationForm, ShiftForm
from apps.operaciones.models import Operation, Shift
from apps.operaciones.services import asignar_mulas, cancelar_turno, registrar_turno


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
    return render(request, "operaciones/operacion_detail.html", {"operation": operation})


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
def turno_nuevo(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    form = ShiftForm(request.POST or None)
    mulas = operation.mulas.filter(activa=True)
    form.fields["vehicle"].queryset = Vehicle.objects.filter(
        pk__in=mulas.values("vehicle")
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
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
        )
        return redirect("operaciones:detalle", pk=operation.pk)
    return render(request, "operaciones/shift_form.html", {"form": form, "operation": operation})


@login_required
def turno_cancelar(request, pk):
    shift = get_object_or_404(Shift, pk=pk)
    if request.method == "POST":
        cancelar_turno(shift, request.POST.get("motivo", ""), usuario=request.user)
    return redirect("operaciones:detalle", pk=shift.operation_id)
