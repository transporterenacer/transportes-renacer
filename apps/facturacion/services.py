import csv
import io
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.facturacion.models import BillingRecord, ClientPayment
from apps.operaciones.models import Operation, Shift


def turnos_realizados(operation):
    return operation.shifts.filter(estado=Shift.REALIZADO)


def horas_trabajadas_operacion(operation):
    return (
        turnos_realizados(operation).aggregate(total=Sum("horas_trabajadas"))["total"]
        or Decimal(0)
    )


def horas_relacionadas_operacion(operation):
    return (
        operation.billing_records.aggregate(total=Sum("horas"))["total"] or Decimal(0)
    )


def horas_pendientes_operacion(operation):
    return horas_trabajadas_operacion(operation) - horas_relacionadas_operacion(
        operation
    )


def valor_generado_operacion(operation):
    return horas_trabajadas_operacion(operation) * operation.tarifa_hora


def valor_relacionado_operacion(operation):
    return (
        operation.billing_records.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )


def total_abonado_operacion(operation):
    return (
        operation.client_payments.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )


def saldo_operacion(operation):
    return valor_generado_operacion(operation) - total_abonado_operacion(operation)


def info_facturacion_operacion(operation):
    horas_trabajadas = horas_trabajadas_operacion(operation)
    horas_relacionadas = horas_relacionadas_operacion(operation)
    valor_generado = horas_trabajadas * operation.tarifa_hora
    abonado = total_abonado_operacion(operation)
    return {
        "horas_trabajadas": horas_trabajadas,
        "horas_relacionadas": horas_relacionadas,
        "horas_pendientes": horas_trabajadas - horas_relacionadas,
        "pct_relacionado": (
            round(float(horas_relacionadas) / float(horas_trabajadas) * 100, 1)
            if horas_trabajadas
            else 0
        ),
        "valor_generado": valor_generado,
        "valor_relacionado": valor_relacionado_operacion(operation),
        "abonado": abonado,
        "saldo": valor_generado - abonado,
    }


def generar_numero_relacion(operation):
    prefix = f"REL-{operation.codigo}-"
    ultimo = (
        BillingRecord.objects.filter(
            operation=operation, numero_relacion__startswith=prefix
        )
        .order_by("-numero_relacion")
        .first()
    )
    if ultimo is None:
        return f"{prefix}001"
    secuencia = int(ultimo.numero_relacion.rsplit("-", 1)[1]) + 1
    return f"{prefix}{secuencia:03d}"


def crear_relacion(operation, shift_ids, usuario=None):
    turnos = list(
        operation.shifts.filter(
            pk__in=shift_ids,
            estado=Shift.REALIZADO,
            billing_record__isnull=True,
        )
        .select_related("vehicle")
        .order_by("fecha_inicio")
    )
    if not turnos:
        raise ValidationError(
            "Seleccione al menos un turno realizado y que no esté ya relacionado."
        )
    creados = []
    with transaction.atomic():
        Operation.objects.select_for_update().get(pk=operation.pk)
        numero = generar_numero_relacion(operation)
        for shift in turnos:
            valor = Decimal(shift.horas_trabajadas) * operation.tarifa_hora
            br = BillingRecord.objects.create(
                operation=operation,
                numero_relacion=numero,
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


def resumen_global():
    turnos = dict(
        Shift.objects.filter(estado=Shift.REALIZADO)
        .values_list("operation")
        .annotate(horas=Sum("horas_trabajadas"))
    )
    tarifas = dict(Operation.objects.values_list("id", "tarifa_hora"))
    horas_trabajadas = Decimal(0)
    valor_generado = Decimal(0)
    for op_id, horas in turnos.items():
        horas = Decimal(horas or 0)
        horas_trabajadas += horas
        valor_generado += horas * tarifas.get(op_id, Decimal(0))
    horas_relacionadas = (
        BillingRecord.objects.aggregate(total=Sum("horas"))["total"] or Decimal(0)
    )
    abonos = ClientPayment.objects.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    return {
        "horas_trabajadas": horas_trabajadas,
        "horas_relacionadas": horas_relacionadas,
        "horas_pendientes": horas_trabajadas - horas_relacionadas,
        "valor_generado": valor_generado,
        "abonos": abonos,
        "saldo": valor_generado - abonos,
    }


def kpis_facturacion():
    data = resumen_global()
    data["operaciones"] = (
        Operation.objects.exclude(estado=Operation.CANCELADA).count()
    )
    return data


def lista_operaciones(filtro="todas"):
    operaciones = []
    for operation in Operation.objects.select_related("generador_de_carga").exclude(
        estado=Operation.CANCELADA
    ).order_by("-fecha_inicio"):
        info = info_facturacion_operacion(operation)
        info.update(
            {
                "pk": operation.pk,
                "codigo": operation.codigo,
                "buque": operation.buque,
                "estado": operation.estado,
                "get_estado_display": operation.get_estado_display(),
                "generador": operation.generador_de_carga.nombre,
            }
        )
        if filtro == "activas" and operation.estado != Operation.ACTIVA:
            continue
        if filtro == "pendientes" and info["horas_pendientes"] <= 0:
            continue
        if filtro == "con_saldo" and info["saldo"] <= 0:
            continue
        operaciones.append(info)
    return operaciones


def alertas_facturacion():
    alertas = []
    for operation in Operation.objects.exclude(estado=Operation.CANCELADA):
        info = info_facturacion_operacion(operation)
        if info["horas_pendientes"] > 0 or info["saldo"] > 0:
            alertas.append(
                {
                    "pk": operation.pk,
                    "codigo": operation.codigo,
                    "buque": operation.buque,
                    "horas_pendientes": info["horas_pendientes"],
                    "saldo": info["saldo"],
                }
            )
    alertas.sort(key=lambda a: a["saldo"], reverse=True)
    return alertas


def agrupar_relaciones(operation):
    grupos = {}
    for br in operation.billing_records.select_related("shift__vehicle").order_by(
        "created_at", "numero_relacion", "fecha"
    ):
        if not br.numero_relacion:
            continue
        g = grupos.setdefault(
            br.numero_relacion,
            {
                "horas": Decimal(0),
                "valor": Decimal(0),
                "turnos": 0,
                "fecha": None,
            },
        )
        g["horas"] += br.horas
        g["valor"] += br.valor
        g["turnos"] += 1
        fecha = br.created_at.date() if br.created_at else br.fecha
        if g["fecha"] is None or fecha < g["fecha"]:
            g["fecha"] = fecha
    return [
        {"numero": numero, **datos}
        for numero, datos in sorted(grupos.items())
    ]


def aplicacion_fifo(operation):
    paquetes = sorted(
        agrupar_relaciones(operation),
        key=lambda p: (p["fecha"] or date.max, p["numero"]),
    )
    for p in paquetes:
        p["cobrado"] = Decimal(0)
        p["pendiente"] = p["valor"]
        p["estado"] = "pendiente"
        p["estado_display"] = "Pendiente"
        p["abonos"] = []

    anticipo = Decimal(0)
    abonos = list(
        operation.client_payments.order_by("fecha", "created_at", "pk")
    )
    for abono in abonos:
        monto = Decimal(abono.valor)
        for p in paquetes:
            if monto <= 0:
                break
            pendiente = p["valor"] - p["cobrado"]
            if pendiente <= 0:
                continue
            toma = min(monto, pendiente)
            p["cobrado"] += toma
            monto -= toma
            p["abonos"].append({"abono": abono, "monto": toma})
        if monto > 0:
            anticipo += monto

    for p in paquetes:
        p["pendiente"] = p["valor"] - p["cobrado"]
        if p["pendiente"] <= 0:
            p["estado"] = "pagada"
            p["estado_display"] = "Pagada"
        elif p["cobrado"] > 0:
            p["estado"] = "parcial"
            p["estado_display"] = "Parcial"

    return {
        "paquetes": paquetes,
        "anticipo": anticipo,
        "valor_relacionado": valor_relacionado_operacion(operation),
    }


def generar_csv_facturacion(operation):
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")

    writer.writerow(
        [
            "Fecha",
            "Operación",
            "Relación",
            "Mula",
            "Turno",
            "Hora inicio",
            "Hora final",
            "Horas trabajadas",
            "Valor hora",
            "Total",
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
                br.numero_relacion or "",
                shift.vehicle.placa,
                shift.get_tipo_display(),
                shift.fecha_inicio.strftime("%H:%M"),
                shift.fecha_fin.strftime("%H:%M"),
                f"{br.horas:.2f}",
                f"{br.tarifa_hora}",
                f"{br.valor}",
            ]
        )

    writer.writerow([])
    writer.writerow(["Mula", "Horas relacionadas", "Horas pendientes"])
    totales = {}
    pendientes = {}
    for br in operation.billing_records.select_related("shift__vehicle").filter(
        shift__isnull=False
    ):
        placa = br.shift.vehicle.placa
        totales[placa] = totales.get(placa, Decimal(0)) + br.horas
    for shift in turnos_realizados(operation).filter(
        billing_record__isnull=True
    ).select_related("vehicle"):
        placa = shift.vehicle.placa
        pendientes[placa] = pendientes.get(placa, Decimal(0)) + shift.horas_trabajadas
    for placa in sorted(set(totales) | set(pendientes)):
        writer.writerow(
            [
                placa,
                f"{totales.get(placa, Decimal(0)):.2f}",
                f"{pendientes.get(placa, Decimal(0)):.2f}",
            ]
        )

    return buffer.getvalue()


def generar_csv_resumen():
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")

    writer.writerow(
        [
            "Operación",
            "Buque",
            "Generador de carga",
            "Horas trabajadas",
            "Horas relacionadas",
            "Horas pendientes",
            "Valor generado",
            "Abonado",
            "Saldo por recibir",
        ]
    )
    for operation in Operation.objects.select_related("generador_de_carga").exclude(
        estado=Operation.CANCELADA
    ).order_by("codigo"):
        info = info_facturacion_operacion(operation)
        if info["horas_trabajadas"] <= 0 and info["saldo"] <= 0:
            continue
        writer.writerow(
            [
                operation.codigo,
                operation.buque,
                operation.generador_de_carga.nombre,
                f"{info['horas_trabajadas']:.2f}",
                f"{info['horas_relacionadas']:.2f}",
                f"{info['horas_pendientes']:.2f}",
                info["valor_generado"],
                info["abonado"],
                info["saldo"],
            ]
        )

    total = resumen_global()
    writer.writerow([])
    writer.writerow(
        [
            "Total",
            "",
            "",
            f"{total['horas_trabajadas']:.2f}",
            f"{total['horas_relacionadas']:.2f}",
            f"{total['horas_pendientes']:.2f}",
            total["valor_generado"],
            total["abonos"],
            total["saldo"],
        ]
    )

    return buffer.getvalue()