import csv
import io
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.facturacion.models import BillingRecord, ClientPayment
from apps.operaciones.models import Shift


def generar_billing_operacion(operation, usuario=None):
    turnos = operation.shifts.filter(
        estado=Shift.REALIZADO, billing_record__isnull=True
    )
    creados = []
    with transaction.atomic():
        for shift in turnos.select_related("vehicle"):
            valor = Decimal(shift.horas_trabajadas) * operation.tarifa_hora
            br = BillingRecord.objects.create(
                operation=operation,
                shift=shift,
                fecha=shift.fecha_inicio.date(),
                horas=shift.horas_trabajadas,
                tarifa_hora=operation.tarifa_hora,
                valor=valor,
                created_by=usuario,
                updated_by=usuario,
            )
            creados.append(br)
    return creados


def total_facturado_operacion(operation):
    return (
        operation.billing_records.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )


def total_abonado_operacion(operation):
    return (
        operation.client_payments.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )


def saldo_operacion(operation):
    return total_facturado_operacion(operation) - total_abonado_operacion(operation)


def generar_csv_facturacion(operation):
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")

    writer.writerow(
        [
            "Fecha",
            "Operación",
            "Mula",
            "Turno",
            "Hora inicio",
            "Hora final",
            "Horas trabajadas",
        ]
    )
    for br in operation.billing_records.select_related("shift__vehicle").order_by(
        "fecha", "shift__fecha_inicio"
    ):
        if br.shift_id is None:
            continue
        shift = br.shift
        writer.writerow(
            [
                br.fecha.strftime("%d/%m/%Y"),
                operation.codigo,
                shift.vehicle.placa,
                shift.get_tipo_display(),
                shift.fecha_inicio.strftime("%H:%M"),
                shift.fecha_fin.strftime("%H:%M"),
                f"{br.horas:.2f}",
            ]
        )

    writer.writerow([])
    writer.writerow(["Mula", "Horas totales"])
    totales = {}
    for br in operation.billing_records.select_related("shift__vehicle").filter(
        shift__isnull=False
    ):
        placa = br.shift.vehicle.placa
        totales[placa] = totales.get(placa, Decimal(0)) + br.horas
    for placa in sorted(totales):
        writer.writerow([placa, f"{totales[placa]:.2f}"])

    return buffer.getvalue()
