from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.facturacion.services import (
    generar_billing_operacion,
    saldo_operacion,
    total_abonado_operacion,
    total_facturado_operacion,
)
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift


class GenerarBillingTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123")
        self.op = Operation.objects.create(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            meta_horas=11,
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )

    def _shift(self, dia, estado=Shift.REALIZADO, inicio=6, fin=17):
        return Shift.objects.create(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, dia, inicio, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, dia, fin, 0)),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=estado,
        )

    def test_generar_billing_solo_turnos_realizados(self):
        self._shift(10)
        self._shift(11, estado=Shift.CANCELADO)
        creados = generar_billing_operacion(self.op)
        self.assertEqual(len(creados), 1)
        br = creados[0]
        self.assertEqual(br.horas, 11)
        self.assertEqual(br.tarifa_hora, 35000)
        self.assertEqual(br.valor, 385000)

    def test_generar_billing_idempotente(self):
        self._shift(10)
        generar_billing_operacion(self.op)
        segunda = generar_billing_operacion(self.op)
        self.assertEqual(segunda, [])
        self.assertEqual(self.op.billing_records.count(), 1)

    def test_generar_billing_usa_tarifa_congelada_de_la_operacion(self):
        self._shift(10, inicio=6, fin=14)
        creados = generar_billing_operacion(self.op)
        self.assertEqual(creados[0].horas, 8)
        self.assertEqual(creados[0].valor, 280000)


class SaldoOperacionTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123")
        self.op = Operation.objects.create(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            meta_horas=11,
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )
        Shift.objects.create(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, 10, 6, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, 10, 17, 0)),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )

    def test_saldo_es_facturado_menos_abonado(self):
        generar_billing_operacion(self.op)
        ClientPayment.objects.create(operation=self.op, valor=200000)
        self.assertEqual(total_facturado_operacion(self.op), 385000)
        self.assertEqual(total_abonado_operacion(self.op), 200000)
        self.assertEqual(saldo_operacion(self.op), 185000)

    def test_saldo_sin_abonos(self):
        generar_billing_operacion(self.op)
        self.assertEqual(saldo_operacion(self.op), 385000)
