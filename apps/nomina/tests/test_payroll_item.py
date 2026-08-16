from datetime import date, timedelta

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.nomina.models import Payroll, PayrollItem
from apps.operaciones.models import Operation, Shift


class PayrollItemTests(TestCase):
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
        self.shift = Shift.objects.create(
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
        self.payroll = Payroll.objects.create(
            numero="NOM-2026-001",
            periodo_inicio=date(2026, 8, 10),
            periodo_fin=date(2026, 8, 16),
        )

    def test_creacion_item(self):
        item = PayrollItem.objects.create(
            payroll=self.payroll, shift=self.shift, valor=180000
        )
        self.assertEqual(item.valor, 180000)
        self.assertEqual(self.payroll.items.count(), 1)

    def test_un_turno_no_puede_estar_en_dos_liquidaciones(self):
        PayrollItem.objects.create(payroll=self.payroll, shift=self.shift, valor=180000)
        otra = Payroll.objects.create(
            numero="NOM-2026-002",
            periodo_inicio=date(2026, 8, 17),
            periodo_fin=date(2026, 8, 23),
        )
        with self.assertRaises(IntegrityError):
            PayrollItem.objects.create(payroll=otra, shift=self.shift, valor=180000)

    def test_relacion_inversa_shift_payroll_items(self):
        PayrollItem.objects.create(payroll=self.payroll, shift=self.shift, valor=180000)
        self.assertEqual(self.shift.payroll_items.count(), 1)
