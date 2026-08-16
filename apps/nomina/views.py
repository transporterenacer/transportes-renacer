from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.nomina.forms import DriverAdvanceForm, PeriodoForm
from apps.nomina.models import Payroll
from apps.nomina.services import (
    crear_liquidacion,
    marcar_pagada as marcar_pagada_service,
    resumen_liquidacion,
)


@login_required
def payroll_list(request):
    payrolls = Payroll.objects.prefetch_related("items").all()
    return render(request, "nomina/payroll_list.html", {"payrolls": payrolls})


@login_required
def payroll_nueva(request):
    if request.method == "POST":
        form = PeriodoForm(request.POST)
        if form.is_valid():
            payroll = crear_liquidacion(
                form.cleaned_data["periodo_inicio"],
                form.cleaned_data["periodo_fin"],
                usuario=request.user,
            )
            return redirect("nomina:detalle", pk=payroll.pk)
    else:
        form = PeriodoForm()
    return render(request, "nomina/payroll_form.html", {"form": form})


@login_required
def payroll_detail(request, pk):
    payroll = get_object_or_404(Payroll, pk=pk)
    context = {
        "payroll": payroll,
        "resumen": resumen_liquidacion(payroll),
        "abono_form": DriverAdvanceForm(),
    }
    return render(request, "nomina/payroll_detail.html", context)


@login_required
def abono_nuevo(request, pk):
    payroll = get_object_or_404(Payroll, pk=pk)
    form = DriverAdvanceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        abono = form.save(commit=False)
        abono.payroll = payroll
        abono.created_by = request.user
        abono.updated_by = request.user
        abono.save()
        return redirect("nomina:detalle", pk=payroll.pk)
    return redirect("nomina:detalle", pk=payroll.pk)


@login_required
def marcar_pagada(request, pk):
    payroll = get_object_or_404(Payroll, pk=pk)
    if request.method == "POST":
        marcar_pagada_service(payroll, usuario=request.user)
    return redirect("nomina:detalle", pk=payroll.pk)
