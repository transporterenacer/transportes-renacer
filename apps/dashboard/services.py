from decimal import Decimal

from django.db.models import Max, Sum

from apps.facturacion.models import BillingRecord, ClientPayment
from apps.flota.models import Vehicle
from apps.nomina.models import Payroll
from apps.operaciones.models import Operation, Shift


def ultima_actualizacion(*modelos):
    actual = None
    for modelo in modelos:
        ts = modelo.objects.aggregate(max_ts=Max("updated_at"))["max_ts"]
        if ts and (actual is None or ts > actual):
            actual = ts
    return actual


def kpis_inicio():
    activas = Operation.objects.filter(estado=Operation.ACTIVA)
    horas_trabajadas = (
        Shift.objects.filter(estado=Shift.REALIZADO)
        .aggregate(total=Sum("horas_trabajadas"))["total"]
        or Decimal(0)
    )
    horas_facturables = (
        BillingRecord.objects.aggregate(total=Sum("horas"))["total"] or Decimal(0)
    )
    valor_generado = (
        BillingRecord.objects.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )
    abonos = (
        ClientPayment.objects.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )
    nomina_pendiente = (
        Payroll.objects.exclude(estado=Payroll.PAGADO)
        .aggregate(total=Sum("total"))["total"]
        or Decimal(0)
    )
    return {
        "operaciones_activas": activas.count(),
        "mulas_en_operacion": Vehicle.objects.filter(estado=Vehicle.EN_OPERACION).count(),
        "mulas_disponibles": Vehicle.objects.filter(estado=Vehicle.DISPONIBLE).count(),
        "mulas_en_taller": Vehicle.objects.filter(estado=Vehicle.EN_TALLER).count(),
        "horas_trabajadas": horas_trabajadas,
        "horas_facturables": horas_facturables,
        "valor_generado": valor_generado,
        "abonos": abonos,
        "saldo_pendiente": valor_generado - abonos,
        "nomina_semanal_pendiente": nomina_pendiente,
    }
