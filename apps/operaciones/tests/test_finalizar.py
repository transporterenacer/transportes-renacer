from datetime import date

from django.test import TestCase

from apps.catalogos.models import CargoGenerator, Port
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation
from apps.operaciones.services import (
    asignar_mulas,
    cancelar_operacion,
    finalizar_operacion,
    liberar_mulas,
)


class FinalizarOperacionTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.v1 = Vehicle.objects.create(placa="ABC123")
        self.op = Operation.objects.create(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
            estado=Operation.ACTIVA,
        )

    def test_finalizar_cambia_estado_y_fecha_real(self):
        finalizar_operacion(self.op)
        self.op.refresh_from_db()
        self.assertEqual(self.op.estado, Operation.FINALIZADA)
        self.assertIsNotNone(self.op.fecha_fin_real)

    def test_finalizar_libera_mulas(self):
        asignar_mulas(self.op, [self.v1])
        finalizar_operacion(self.op)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.estado, Vehicle.DISPONIBLE)
        self.assertFalse(self.op.mulas.get(vehicle=self.v1).activa)

    def test_cancelar_operacion(self):
        asignar_mulas(self.op, [self.v1])
        cancelar_operacion(self.op)
        self.op.refresh_from_db()
        self.assertEqual(self.op.estado, Operation.CANCELADA)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.estado, Vehicle.DISPONIBLE)

    def test_finalizar_es_idempotente(self):
        finalizar_operacion(self.op)
        finalizar_operacion(self.op)
        self.assertEqual(self.op.estado, Operation.FINALIZADA)
