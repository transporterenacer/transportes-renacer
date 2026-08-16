from datetime import date

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.operaciones.models import Operation


class OperationTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")

    def _crear(self, **kwargs):
        defaults = dict(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )
        defaults.update(kwargs)
        return Operation.objects.create(**defaults)

    def test_operation_creation(self):
        op = self._crear()
        self.assertEqual(str(op), "OP-001 - BUQUE ATLANTIC")
        self.assertEqual(op.estado, Operation.PROGRAMADA)
        self.assertEqual(op.meta_horas, 11)

    def test_operation_codigo_unique(self):
        self._crear()
        with self.assertRaises(IntegrityError):
            self._crear()

    def test_estado_activa_property(self):
        op = self._crear(estado=Operation.ACTIVA)
        self.assertTrue(op.estado_activa)
        op2 = self._crear(codigo="OP-002", estado=Operation.PROGRAMADA)
        self.assertFalse(op2.estado_activa)

    def test_total_horas_suma_shifts_realizados(self):
        from apps.conductores.models import Driver
        from apps.flota.models import Vehicle
        from apps.operaciones.models import Shift

        op = self._crear(estado=Operation.ACTIVA)
        vehicle = Vehicle.objects.create(placa="ABC123")
        driver = Driver.objects.create(nombre="Juan Pérez", documento="123")
        Shift.objects.create(
            operation=op,
            vehicle=vehicle,
            driver=driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, 10, 6, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, 10, 17, 0)),
            tipo=Shift.DIA,
            meta_horas=op.meta_horas,
            valor_estandar=op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )
        self.assertEqual(op.total_horas, 11.0)
