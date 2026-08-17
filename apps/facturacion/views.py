from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.dashboard.services import ultima_actualizacion
from apps.facturacion.forms import ClientPaymentForm
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.facturacion.services import (
    alertas_facturacion,
    aplicacion_fifo,
    crear_relacion,
    generar_csv_facturacion,
    generar_csv_resumen,
    info_facturacion_operacion,
    kpis_facturacion,
    lista_operaciones,
    turnos_realizados,
)
from apps.operaciones.models import Operation


@login_required
def facturacion_lista(request):
    estado = request.GET.get("estado", "todas")
    context = {
        "operaciones": lista_operaciones(estado),
        "filtro": estado,
        "kpis": kpis_facturacion(),
        "alertas": alertas_facturacion(),
        "ultima_actualizacion": ultima_actualizacion(
            BillingRecord, ClientPayment, Operation
        ),
    }
    return render(request, "facturacion/facturacion_list.html", context)


@login_required
def facturacion_detail(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    turnos = turnos_realizados(operation).select_related("vehicle", "billing_record").order_by(
        "fecha_inicio"
    )
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")
    if desde:
        turnos = turnos.filter(fecha_inicio__date__gte=desde)
    if hasta:
        turnos = turnos.filter(fecha_inicio__date__lte=hasta)
    disponibles = turnos.filter(billing_record__isnull=True)
    relacionados_count = turnos.count() - disponibles.count()
    context = {
        "operation": operation,
        "info": info_facturacion_operacion(operation),
        "turnos": turnos,
        "disponibles": disponibles,
        "relacionados_count": relacionados_count,
        "desde": desde,
        "hasta": hasta,
        "fifo": aplicacion_fifo(operation),
        "abonos": operation.client_payments.order_by("-fecha"),
        "abono_form": ClientPaymentForm(),
        "ultima_actualizacion": ultima_actualizacion(BillingRecord, ClientPayment),
    }
    return render(request, "facturacion/facturacion_detail.html", context)


@login_required
def relacion_nueva(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    if request.method == "POST":
        shift_ids = request.POST.getlist("shift_ids")
        try:
            creados = crear_relacion(operation, shift_ids, usuario=request.user)
            messages.success(
                request,
                f"Relación creada: {creados[0].numero_relacion} con "
                f"{len(creados)} turno(s).",
            )
        except Exception as e:
            messages.error(request, str(e))
    return redirect("facturacion:detalle", pk=operation.pk)


@login_required
def relacion_detalle(request, pk, numero):
    operation = get_object_or_404(Operation, pk=pk)
    records = list(
        operation.billing_records.filter(numero_relacion=numero)
        .select_related("shift__vehicle")
        .order_by("fecha")
    )
    if not records:
        raise Http404("Relación no encontrada.")
    horas = sum(br.horas for br in records)
    valor = sum(br.valor for br in records)
    fifo = aplicacion_fifo(operation)
    paquete = next((p for p in fifo["paquetes"] if p["numero"] == numero), None)
    context = {
        "operation": operation,
        "numero": numero,
        "records": records,
        "horas": horas,
        "valor": valor,
        "paquete": paquete,
        "anticipo": fifo["anticipo"],
        "info": info_facturacion_operacion(operation),
        "abonos": operation.client_payments.order_by("-fecha"),
        "ultima_actualizacion": ultima_actualizacion(BillingRecord, ClientPayment),
    }
    return render(request, "facturacion/facturacion_relacion.html", context)


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
        messages.success(request, "Abono registrado correctamente.")
    else:
        for errores in form.errors.values():
            for error in errores:
                messages.error(request, error)
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


@login_required
def csv_resumen(request):
    content = generar_csv_resumen()
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="facturacion_resumen.csv"'
    return response