from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, OperationExpense, Viaje


class ExpenseViajeTests(TestCase):
    def setUp(self):
        self.cliente = CargoGenerator.objects.create(nombre="Cliente", nit="1")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan", documento="1")
        self.ahora = timezone.make_aware(datetime(2026, 8, 10, 6, 0))
        self.viaje = Viaje.objects.create(
            cliente=self.cliente, vehicle=self.vehicle, driver=self.driver,
            origen="Barranquilla", destino="Cartagena",
            fecha_ida=self.ahora, fecha_vuelta=self.ahora + timedelta(hours=8),
            valor_cobrado=Decimal("800000"), valor_conductor=Decimal("400000"),
        )

    def test_crear_gasto_via_viaje(self):
        gasto = OperationExpense.objects.create(
            viaje=self.viaje, vehicle=self.vehicle,
            categoria=OperationExpense.COMBUSTIBLE,
            fecha=timezone.localdate(), valor=Decimal("450000"), galones=Decimal("120"),
        )
        self.assertEqual(gasto.viaje, self.viaje)
        self.assertIsNone(gasto.operation)

    def test_gasto_sin_viaje_ni_operation_es_invalido(self):
        gasto = OperationExpense(
            vehicle=self.vehicle, categoria=OperationExpense.PEAJE,
            fecha=timezone.localdate(), valor=Decimal("35000"),
        )
        with self.assertRaises(ValidationError):
            gasto.full_clean()

    def test_gasto_con_operation_y_viaje_es_invalido(self):
        puerto = Port.objects.create(nombre="Puerto")
        op = Operation.objects.create(
            codigo="OP-1", buque="B", generador_de_carga=self.cliente, puerto=puerto,
            fecha_inicio=timezone.localdate(), tarifa_hora=Decimal("35000"),
            valor_turno_dia=Decimal("180000"), valor_turno_noche=Decimal("180000"),
        )
        gasto = OperationExpense(
            operation=op, viaje=self.viaje, vehicle=self.vehicle,
            categoria=OperationExpense.PEAJE, fecha=timezone.localdate(), valor=Decimal("1"),
        )
        with self.assertRaises(ValidationError):
            gasto.full_clean()
