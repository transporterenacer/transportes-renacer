import csv
from datetime import timedelta
from io import StringIO

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.conductores.models import Driver
from apps.dashboard.services import ultima_actualizacion
from apps.nomina.forms import DriverAdvanceForm, DriverPagoForm, PeriodoForm
from apps.nomina.models import DriverAdvance, Payroll
from apps.nomina.services import (
    alertas_nomina,
    crear_liquidacion,
    estado_nomina,
    nomina_pendiente_actual,
    registrar_abono,
    registrar_pago,
    resumen_liquidacion,
    saldo_conductor,
    semana_anterior,
    semana_para,
    semana_siguiente,
    turnos_pendientes_pago,
)
from apps.operaciones.models import Shift


@login_required
def payroll_list(request):
    lunes_str = request.GET.get("lunes")
    if lunes_str:
        try:
            lunes = timezone.datetime.strptime(lunes_str, "%Y-%m-%d").date()
        except ValueError:
            lunes, _ = semana_para(timezone.localdate())
    else:
        lunes, _ = semana_para(timezone.localdate())
    domingo = lunes + timedelta(days=6)
    payrolls = list(Payroll.objects.prefetch_related("items").all())
    conductores_pendientes = set()
    for p in payrolls:
        p.conductor_count = p.items.values("shift__driver").distinct().count()
        p.estado_derivado = estado_nomina(p)["estado"]
        for fila in resumen_liquidacion(p):
            if fila["pendiente"] > 0:
                conductores_pendientes.add(fila["driver"].pk)
    turnos_periodo = list(turnos_pendientes_pago(lunes, domingo))
    contexto = {
        "payrolls": payrolls,
        "lunes": lunes,
        "domingo": domingo,
        "semana_anterior_ini": semana_anterior(lunes),
        "semana_siguiente_ini": semana_siguiente(lunes),
        "ultima_actualizacion": ultima_actualizacion(Payroll, Shift, DriverAdvance),
        "alertas": alertas_nomina(),
        "pendiente_periodo": sum(t.valor_pagado for t in turnos_periodo) or 0,
        "pendiente_global": nomina_pendiente_actual(),
        "conductores_pendientes": len(conductores_pendientes),
    }
    payroll_actual = next(
        (p for p in payrolls if p.periodo_inicio == lunes and p.periodo_fin == domingo),
        None,
    )
    if payroll_actual:
        contexto["payroll_actual"] = payroll_actual
        contexto["estado_actual"] = estado_nomina(payroll_actual)
    return render(request, "nomina/payroll_list.html", contexto)


@login_required
def payroll_nueva(request):
    if request.method == "POST":
        form = PeriodoForm(request.POST)
        if form.is_valid():
            try:
                payroll = crear_liquidacion(
                    form.cleaned_data["periodo_inicio"],
                    form.cleaned_data["periodo_fin"],
                    usuario=request.user,
                )
                return redirect("nomina:detalle", pk=payroll.pk)
            except ValidationError as exc:
                form.add_error(None, exc.message)
    else:
        form = PeriodoForm()
    return render(request, "nomina/payroll_form.html", {"form": form})


@login_required
def payroll_detail(request, pk):
    payroll = get_object_or_404(Payroll, pk=pk)
    context = {
        "payroll": payroll,
        "resumen": resumen_liquidacion(payroll),
        "estado": estado_nomina(payroll),
        "ultima_actualizacion": ultima_actualizacion(Payroll, Shift, DriverAdvance),
    }
    return render(request, "nomina/payroll_detail.html", context)


def _conductor_context(driver, abono_form=None, pago_form=None, mensaje=None, filtro="todos"):
    saldo = saldo_conductor(driver)
    if filtro == "pendientes":
        saldo["items"] = [i for i in saldo["items"] if i["pendiente"] > 0]
    elif filtro == "cubiertos":
        saldo["items"] = [i for i in saldo["items"] if i["pendiente"] == 0]
    return {
        "driver": driver,
        "saldo": saldo,
        "filtro": filtro,
        "movimientos": DriverAdvance.objects.filter(driver=driver).order_by("-fecha"),
        "ultimo_movimiento": (
            DriverAdvance.objects.filter(driver=driver).order_by("-fecha").first()
        ),
        "abono_form": abono_form or DriverAdvanceForm(initial={"driver": driver.pk}),
        "pago_form": pago_form or DriverPagoForm(
            initial={"valor": saldo["saldo_pendiente"]}
        ),
        "mensaje": mensaje,
    }


@login_required
def conductor_detail(request, driver_pk):
    driver = get_object_or_404(Driver, pk=driver_pk)
    filtro = request.GET.get("filtro", "todos")
    if filtro not in ("todos", "pendientes", "cubiertos"):
        filtro = "todos"
    return render(
        request,
        "nomina/conductor_detail.html",
        _conductor_context(driver, filtro=filtro),
    )


@login_required
def abono_nuevo(request, driver_pk):
    driver = get_object_or_404(Driver, pk=driver_pk)
    form = DriverAdvanceForm(request.POST or None)
    form.fields["driver"].required = False
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            registrar_abono(
                driver,
                data["valor"],
                descripcion=data.get("descripcion", ""),
                fecha=data.get("fecha"),
                metodo=data["metodo"],
                usuario=request.user,
            )
        except ValidationError as exc:
            return render(
                request,
                "nomina/conductor_detail.html",
                _conductor_context(driver, abono_form=form, mensaje=exc.message),
            )
    return redirect("nomina:conductor", driver_pk=driver.pk)


@login_required
def pago_nuevo(request, driver_pk):
    driver = get_object_or_404(Driver, pk=driver_pk)
    form = DriverPagoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            registrar_pago(
                driver,
                data["valor"],
                metodo=data["metodo"],
                usuario=request.user,
            )
        except ValidationError as exc:
            return render(
                request,
                "nomina/conductor_detail.html",
                _conductor_context(driver, pago_form=form, mensaje=exc.message),
            )
    return redirect("nomina:conductor", driver_pk=driver.pk)


@login_required
def exportar_csv(request, pk):
    payroll = get_object_or_404(Payroll, pk=pk)
    resumen = resumen_liquidacion(payroll)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "Conductor", "Cédula", "Período", "Fecha", "Operación", "Mula",
        "Turno", "Hora inicio", "Hora final", "Horas", "Valor turno",
        "Cubierto", "Total", "Estado",
    ])
    for fila in resumen:
        for item in payroll.items.filter(shift__driver=fila["driver"]).select_related(
            "shift__vehicle", "shift__operation"
        ):
            shift = item.shift
            writer.writerow([
                fila["driver"].nombre,
                fila["driver"].documento,
                f"{payroll.periodo_inicio} a {payroll.periodo_fin}",
                shift.fecha_inicio.strftime("%d/%m/%Y"),
                shift.operation.codigo,
                shift.vehicle.placa,
                shift.get_tipo_display(),
                shift.fecha_inicio.strftime("%d/%m/%Y %H:%M"),
                shift.fecha_fin.strftime("%d/%m/%Y %H:%M"),
                float(shift.horas_trabajadas),
                float(item.valor),
                float(item.pagado),
                float(fila["total"]),
                fila["estado"],
            ])
    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="nomina_{payroll.numero}.csv"'
    )
    return response