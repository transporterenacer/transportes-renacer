from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift


class ShiftTests(TestCase):
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

    def _crear_shift(self, inicio, fin, **kwargs):
        defaults = dict(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(inicio),
            fecha_fin=timezone.make_aware(fin),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
        )
        defaults.update(kwargs)
        return Shift.objects.create(**defaults)

    def test_horas_calculadas_turno_dia(self):
        shift = self._crear_shift(
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
        )
        self.assertEqual(shift.horas_trabajadas, 11.0)
        self.assertEqual(shift.cumplimiento_pct, 100.0)

    def test_horas_nocturno_cruza_medianoche(self):
        shift = self._crear_shift(
            timezone.datetime(2026, 8, 10, 18, 0),
            timezone.datetime(2026, 8, 11, 6, 0),
            tipo=Shift.NOCHE,
        )
        self.assertEqual(shift.horas_trabajadas, 12.0)
        self.assertEqual(shift.cumplimiento_pct, 109.1)

    def test_cumplimiento_bajo(self):
        shift = self._crear_shift(
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 14, 0),
        )
        self.assertEqual(shift.horas_trabajadas, 8.0)
        self.assertEqual(shift.cumplimiento_pct, 72.7)

    def test_valor_es_pagable_solo_realizado(self):
        shift = self._crear_shift(
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
            estado=Shift.REALIZADO,
        )
        self.assertTrue(shift.valor_es_pagable)
        shift.estado = Shift.CANCELADO
        shift.save()
        self.assertFalse(shift.valor_es_pagable)

    def test_estado_default_programado(self):
        shift = self._crear_shift(
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
        )
        self.assertEqual(shift.estado, Shift.PROGRAMADO)

    def test_edicion_manual_del_valor_no_es_sobreescrita(self):
        shift = self._crear_shift(
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
            estado=Shift.REALIZADO,
        )
        self.assertEqual(shift.valor_pagado, 180000)
        shift.valor_pagado = 200000
        shift.observaciones = "Ajuste manual"
        shift.save()
        shift.refresh_from_db()
        self.assertEqual(shift.valor_pagado, 200000)

    def test_cancelar_resetea_valor_pagado(self):
        shift = self._crear_shift(
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
            estado=Shift.REALIZADO,
        )
        self.assertEqual(shift.valor_pagado, 180000)
        shift.estado = Shift.CANCELADO
        shift.motivo_cancelacion = "Avería"
        shift.save()
        shift.refresh_from_db()
        self.assertEqual(shift.valor_pagado, 0)
