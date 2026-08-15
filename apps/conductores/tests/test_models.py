from django.db import IntegrityError
from django.test import TestCase

from apps.conductores.models import Driver


class DriverTests(TestCase):
    def test_driver_creation(self):
        driver = Driver.objects.create(nombre="Juan Pérez", documento="12345678")
        self.assertEqual(str(driver), "Juan Pérez")

    def test_driver_document_unique(self):
        Driver.objects.create(nombre="Juan Pérez", documento="12345678")
        with self.assertRaises(IntegrityError):
            Driver.objects.create(nombre="María Gómez", documento="12345678")

    def test_driver_default_state(self):
        driver = Driver.objects.create(nombre="Juan Pérez", documento="12345678")
        self.assertEqual(driver.estado, Driver.DISPONIBLE)

    def test_driver_is_inactive_state(self):
        driver = Driver.objects.create(
            nombre="Juan Pérez", documento="12345678", estado=Driver.INACTIVO
        )
        self.assertTrue(driver.estado == Driver.INACTIVO)
