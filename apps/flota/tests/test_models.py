from datetime import timedelta

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.flota.models import Vehicle, VehicleDocument


class VehicleTests(TestCase):
    def test_vehicle_creation(self):
        v = Vehicle.objects.create(placa="ABC123", marca="Kenworth", modelo="T880", anio=2020)
        self.assertEqual(str(v), "ABC123")

    def test_vehicle_plate_uppercased(self):
        v = Vehicle.objects.create(placa="abc123")
        self.assertEqual(v.placa, "ABC123")

    def test_vehicle_plate_stripped(self):
        v = Vehicle.objects.create(placa=" abc123 ")
        self.assertEqual(v.placa, "ABC123")

    def test_vehicle_default_state(self):
        v = Vehicle.objects.create(placa="ABC123")
        self.assertEqual(v.estado, Vehicle.DISPONIBLE)

    def test_vehicle_plate_unique(self):
        Vehicle.objects.create(placa="ABC123")
        with self.assertRaises(IntegrityError):
            Vehicle.objects.create(placa="ABC123")


class VehicleDocumentLegacyTests(TestCase):
    """VehicleDocument es legado: se conserva por compatibilidad de migraciones.

    La funcionalidad nueva usa apps.documentos.Document.
    """

    def setUp(self):
        self.vehicle = Vehicle.objects.create(placa="ABC123")

    def test_dias_restantes(self):
        doc = VehicleDocument.objects.create(
            vehicle=self.vehicle,
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() + timedelta(days=10),
        )
        self.assertEqual(doc.dias_restantes(), 10)
