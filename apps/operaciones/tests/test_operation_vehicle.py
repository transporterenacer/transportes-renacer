from datetime import date

from django.test import TestCase

from apps.catalogos.models import CargoGenerator, Port
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation
from apps.operaciones.services import asignar_mulas, liberar_mulas, mulas_disponibles


class AsignacionMulasTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.v1 = Vehicle.objects.create(placa="ABC123")
        self.v2 = Vehicle.objects.create(placa="DEF456")
        self.op = Operation.objects.create(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )

    def test_asignar_mulas_cambia_estado_y_crea_relaciones(self):
        asignar_mulas(self.op, [self.v1, self.v2])
        self.v1.refresh_from_db()
        self.v2.refresh_from_db()
        self.assertEqual(self.v1.estado, Vehicle.EN_OPERACION)
        self.assertEqual(self.v2.estado, Vehicle.EN_OPERACION)
        self.assertEqual(self.op.mulas.filter(activa=True).count(), 2)

    def test_asignar_mulas_idempotente(self):
        asignar_mulas(self.op, [self.v1])
        asignar_mulas(self.op, [self.v1])
        self.assertEqual(self.op.mulas.filter(activa=True).count(), 1)

    def test_liberar_mulas_libera_si_no_esta_en_otra_operacion(self):
        asignar_mulas(self.op, [self.v1])
        liberar_mulas(self.op)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.estado, Vehicle.DISPONIBLE)
        self.assertFalse(self.op.mulas.get(vehicle=self.v1).activa)

    def test_liberar_mulas_no_libera_vehicle_en_otra_operacion(self):
        op2 = Operation.objects.create(
            codigo="OP-002",
            buque="BUQUE OTRO",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 11),
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )
        asignar_mulas(self.op, [self.v1])
        asignar_mulas(op2, [self.v1])
        liberar_mulas(self.op)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.estado, Vehicle.EN_OPERACION)

    def test_mulas_disponibles_solo_filtra_disponibles(self):
        self.v1.estado = Vehicle.EN_TALLER
        self.v1.save()
        disponibles = list(mulas_disponibles())
        self.assertIn(self.v2, disponibles)
        self.assertNotIn(self.v1, disponibles)
