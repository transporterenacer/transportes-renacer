from datetime import datetime

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalogos.models import Proveedor
from apps.core.decorators import role_required
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.flota.models import Vehicle
from apps.nomina.models import PayrollItem
from apps.operaciones.forms import OperationExpenseForm, OperationForm, ShiftForm, ShiftStopFormSet
from apps.operaciones.models import Operation, OperationExpense, Shift
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

    # Financial summary
    total_facturado = operation.billing_records.aggregate(
        total=models.Sum("valor")
    )["total"] or Decimal(0)
    total_cobrado = operation.client_payments.aggregate(
        total=models.Sum("valor")
    )["total"] or Decimal(0)
    total_nomina = PayrollItem.objects.filter(
        shift__operation=operation, shift__estado=Shift.REALIZADO
    ).aggregate(total=models.Sum("valor"))["total"] or Decimal(0)

    gastos = operation.expenses.all()
    total_combustible = gastos.filter(categoria=OperationExpense.COMBUSTIBLE).aggregate(
        total=models.Sum("valor")
    )["total"] or Decimal(0)
    total_repuesto = gastos.filter(categoria=OperationExpense.REPUESTO).aggregate(
        total=models.Sum("valor")
    )["total"] or Decimal(0)
    total_llanta = gastos.filter(categoria=OperationExpense.LLANTA).aggregate(
        total=models.Sum("valor")
    )["total"] or Decimal(0)
    total_mantenimiento = gastos.filter(categoria=OperationExpense.MANTENIMIENTO).aggregate(
        total=models.Sum("valor")
    )["total"] or Decimal(0)
    total_mano_obra = gastos.filter(categoria=OperationExpense.MANO_OBRA).aggregate(
        total=models.Sum("valor")
    )["total"] or Decimal(0)
    total_peaje = gastos.filter(categoria=OperationExpense.PEAJE).aggregate(
        total=models.Sum("valor")
    )["total"] or Decimal(0)
    total_lavado = gastos.filter(categoria=OperationExpense.LAVADO).aggregate(
        total=models.Sum("valor")
    )["total"] or Decimal(0)
    total_otros = gastos.filter(categoria=OperationExpense.OTROS).aggregate(
        total=models.Sum("valor")
    )["total"] or Decimal(0)

    total_costos_gastos = (
        total_combustible + total_repuesto + total_llanta + total_mantenimiento
        + total_mano_obra + total_peaje + total_lavado + total_otros
    )
    total_costos = total_nomina + total_costos_gastos
    saldo = total_facturado - total_cobrado
    resultado = total_facturado - total_costos
    margen = (resultado / total_facturado * 100) if total_facturado else Decimal(0)

    context = {
        "operation": operation,
        "mulas_disponibles": disponibles,
        "total_facturado": total_facturado,
        "total_cobrado": total_cobrado,
        "saldo": saldo,
        "total_nomina": total_nomina,
        "total_combustible": total_combustible,
        "total_repuesto": total_repuesto,
        "total_llanta": total_llanta,
        "total_mantenimiento": total_mantenimiento,
        "total_mano_obra": total_mano_obra,
        "total_peaje": total_peaje,
        "total_lavado": total_lavado,
        "total_otros": total_otros,
        "total_costos": total_costos,
        "resultado": resultado,
        "margen": margen,
    }
    return render(request, "operaciones/operacion_detail.html", context)


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
                    base_date = data["fecha_inicio_date"]
                    stops.append({
                        "inicio": datetime.combine(base_date, datetime.strptime(ini, "%H:%M").time()),
                        "fin": datetime.combine(base_date, datetime.strptime(fin, "%H:%M").time()),
                    })
        inicio = datetime.combine(data["fecha_inicio_date"], datetime.strptime(data["fecha_inicio_time"], "%H:%M").time())
        fin = datetime.combine(data["fecha_fin_date"], datetime.strptime(data["fecha_fin_time"], "%H:%M").time())
        registrar_turno(
            operation=operation,
            vehicle=data["vehicle"],
            driver=data["driver"],
            fecha_inicio=inicio,
            fecha_fin=fin,
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


@login_required
def gasto_lista(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    return render(request, "operaciones/gasto_lista.html", {"operation": operation})


@login_required
def gasto_nuevo(request, op_pk):
    operation = get_object_or_404(Operation, pk=op_pk)
    if request.method == "POST":
        form = OperationExpenseForm(request.POST, operation=operation)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.operation = operation
            gasto.created_by = request.user
            gasto.save()
            messages.success(request, "Gasto registrado.")
            return redirect("operaciones:detalle", pk=operation.pk)
    else:
        form = OperationExpenseForm(operation=operation)
    return render(request, "operaciones/expense_form.html", {
        "form": form, "operation": operation, "editing": False,
    })


@login_required
def gasto_editar(request, op_pk, gasto_pk):
    operation = get_object_or_404(Operation, pk=op_pk)
    gasto = get_object_or_404(OperationExpense, pk=gasto_pk, operation=operation)
    if request.method == "POST":
        form = OperationExpenseForm(request.POST, instance=gasto, operation=operation)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.updated_by = request.user
            gasto.save()
            messages.success(request, "Gasto actualizado.")
            return redirect("operaciones:detalle", pk=operation.pk)
    else:
        form = OperationExpenseForm(instance=gasto, operation=operation)
    return render(request, "operaciones/expense_form.html", {
        "form": form, "operation": operation, "editing": True, "gasto": gasto,
    })


@login_required
def gasto_eliminar(request, op_pk, gasto_pk):
    if request.method != "POST":
        return redirect("operaciones:detalle", pk=op_pk)
    operation = get_object_or_404(Operation, pk=op_pk)
    gasto = get_object_or_404(OperationExpense, pk=gasto_pk, operation=operation)
    gasto.delete()
    messages.success(request, "Gasto eliminado.")
    return redirect("operaciones:detalle", pk=operation.pk)


# ── Jefe Mecánico views ──────────────────────────────────────────────


@role_required("Admin", "Secretaria", "Jefe Mecánico")
def mechanic_operacion_list(request):
    operaciones = Operation.objects.filter(
        estado__in=[Operation.PROGRAMADA, Operation.ACTIVA]
    ).order_by("-fecha_inicio")
    return render(request, "operaciones/mechanic_operation_list.html", {"operaciones": operaciones})


@role_required("Admin", "Secretaria", "Jefe Mecánico")
def mechanic_operacion_detail(request, pk):
    operation = get_object_or_404(
        Operation.objects.prefetch_related("mulas__vehicle"),
        pk=pk,
    )
    mulas_asignadas = operation.mulas.filter(activa=True).select_related("vehicle")
    return render(request, "operaciones/mechanic_operation_detail.html", {
        "operation": operation,
        "mulas_asignadas": mulas_asignadas,
    })


@role_required("Admin", "Secretaria", "Jefe Mecánico")
def mechanic_gasto_nuevo(request, op_pk, vehicle_pk):
    operation = get_object_or_404(Operation, pk=op_pk)
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk)

    if request.method == "POST":
        form = OperationExpenseForm(request.POST, operation=operation)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.operation = operation
            gasto.vehicle = vehicle
            gasto.created_by = request.user
            gasto.save()
            messages.success(request, "Gasto registrado.")
            return redirect("operaciones:mechanic_detail", pk=operation.pk)
    else:
        form = OperationExpenseForm(initial={"vehicle": vehicle}, operation=operation)

    return render(request, "operaciones/mechanic_expense_form.html", {
        "form": form, "operation": operation, "vehicle": vehicle, "editing": False,
    })


@role_required("Admin", "Secretaria", "Jefe Mecánico")
def mechanic_gasto_editar(request, op_pk, vehicle_pk, gasto_pk):
    operation = get_object_or_404(Operation, pk=op_pk)
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk)
    gasto = get_object_or_404(OperationExpense, pk=gasto_pk, operation=operation, vehicle=vehicle)

    if request.method == "POST":
        form = OperationExpenseForm(request.POST, instance=gasto, operation=operation)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.updated_by = request.user
            gasto.save()
            messages.success(request, "Gasto actualizado.")
            return redirect("operaciones:mechanic_detail", pk=operation.pk)
    else:
        form = OperationExpenseForm(instance=gasto, operation=operation)

    return render(request, "operaciones/mechanic_expense_form.html", {
        "form": form, "operation": operation, "vehicle": vehicle, "editing": True, "gasto": gasto,
    })
