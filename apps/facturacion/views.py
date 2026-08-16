from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.facturacion.forms import ClientPaymentForm
from apps.facturacion.models import ClientPayment
from apps.facturacion.services import (
    generar_billing_operacion,
    generar_csv_facturacion,
    saldo_operacion,
    total_abonado_operacion,
    total_facturado_operacion,
)
from apps.operaciones.models import Operation


@login_required
def facturacion_detail(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    context = {
        "operation": operation,
        "facturado": total_facturado_operacion(operation),
        "abonado": total_abonado_operacion(operation),
        "saldo": saldo_operacion(operation),
        "abono_form": ClientPaymentForm(),
    }
    return render(request, "facturacion/facturacion_detail.html", context)


@login_required
def generar_billing(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    if request.method == "POST":
        generar_billing_operacion(operation, usuario=request.user)
    return redirect("facturacion:detalle", pk=operation.pk)


@login_required
def abono_nuevo(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    form = ClientPaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        abono = form.save(commit=False)
        abono.operation = operation
        abono.created_by = request.user
        abono.updated_by = request.user
        abono.save()
    return redirect("facturacion:detalle", pk=operation.pk)


@login_required
def csv_facturacion(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    content = generar_csv_facturacion(operation)
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="facturacion_{operation.codigo}.csv"'
    )
    return response
