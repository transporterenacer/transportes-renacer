from datetime import date

from django.test import TestCase

from apps.conductores.models import Driver
from apps.nomina.models import DriverAdvance, Payroll


class DriverAdvanceTests(TestCase):
    def setUp(self):
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123")

    def test_creacion_abono_sin_liquidacion(self):
        a = DriverAdvance.objects.create(driver=self.driver, valor=150000)
        self.assertEqual(a.valor, 150000)
        self.assertIsNone(a.payroll)

    def test_abono_vinculado_a_liquidacion(self):
        payroll = Payroll.objects.create(
            numero="NOM-2026-001",
            periodo_inicio=date(2026, 8, 10),
            periodo_fin=date(2026, 8, 16),
        )
        a = DriverAdvance.objects.create(driver=self.driver, valor=150000, payroll=payroll)
        self.assertEqual(a.payroll, payroll)
        self.assertEqual(payroll.abonos.count(), 1)

    def test_str(self):
        a = DriverAdvance.objects.create(driver=self.driver, valor=150000)
        self.assertIn("Juan Pérez", str(a))
