from datetime import date

from django.test import TestCase

from apps.nomina.models import Payroll
from apps.nomina.services import generar_numero_liquidacion


class PayrollTests(TestCase):
    def test_creation_y_str(self):
        p = Payroll.objects.create(
            numero="NOM-2026-001",
            periodo_inicio=date(2026, 8, 10),
            periodo_fin=date(2026, 8, 16),
        )
        self.assertEqual(str(p), "NOM-2026-001")
        self.assertEqual(p.estado, Payroll.PENDIENTE)
        self.assertIsNone(p.fecha_pago)

    def test_numero_unique(self):
        from django.db import IntegrityError

        Payroll.objects.create(
            numero="NOM-2026-001",
            periodo_inicio=date(2026, 8, 10),
            periodo_fin=date(2026, 8, 16),
        )
        with self.assertRaises(IntegrityError):
            Payroll.objects.create(
                numero="NOM-2026-001",
                periodo_inicio=date(2026, 8, 17),
                periodo_fin=date(2026, 8, 23),
            )

    def test_estado_pagado_fija_fecha_pago(self):
        p = Payroll.objects.create(
            numero="NOM-2026-002",
            periodo_inicio=date(2026, 8, 10),
            periodo_fin=date(2026, 8, 16),
            estado=Payroll.PAGADO,
            fecha_pago=date(2026, 8, 16),
        )
        self.assertEqual(p.fecha_pago, date(2026, 8, 16))


class GenerarNumeroLiquidacionTests(TestCase):
    def test_primer_numero_del_anio(self):
        self.assertEqual(generar_numero_liquidacion(2026), "NOM-2026-001")

    def test_numero_secuencial(self):
        Payroll.objects.create(
            numero="NOM-2026-001",
            periodo_inicio=date(2026, 8, 10),
            periodo_fin=date(2026, 8, 16),
        )
        Payroll.objects.create(
            numero="NOM-2026-002",
            periodo_inicio=date(2026, 8, 17),
            periodo_fin=date(2026, 8, 23),
        )
        self.assertEqual(generar_numero_liquidacion(2026), "NOM-2026-003")

    def test_anios_separados(self):
        Payroll.objects.create(
            numero="NOM-2025-005",
            periodo_inicio=date(2025, 12, 29),
            periodo_fin=date(2026, 1, 4),
        )
        self.assertEqual(generar_numero_liquidacion(2026), "NOM-2026-001")
