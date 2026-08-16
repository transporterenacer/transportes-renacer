from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port


class CatalogModelsTests(TestCase):
    def test_cargo_generator_creation(self):
        generator = CargoGenerator.objects.create(
            nombre="Puerto de Barranquilla", nit="901000000-0"
        )
        self.assertEqual(str(generator), "Puerto de Barranquilla")

    def test_multiple_generators_without_nit(self):
        first = CargoGenerator.objects.create(nombre="Generador A")
        second = CargoGenerator.objects.create(nombre="Generador B")
        self.assertIsNone(first.nit)
        self.assertIsNone(second.nit)

    def test_port_creation(self):
        port = Port.objects.create(nombre="Sociedad Portuaria Regional", ciudad="Barranquilla")
        self.assertEqual(str(port), "Sociedad Portuaria Regional")

    def test_incident_category_unique_name(self):
        IncidentCategory.objects.create(nombre="Lluvia")
        with self.assertRaises(IntegrityError):
            IncidentCategory.objects.create(nombre="Lluvia")

    def test_incident_category_active_by_default(self):
        cat = IncidentCategory.objects.create(nombre="Avería mecánica")
        self.assertTrue(cat.activa)

    def test_incident_category_str(self):
        cat = IncidentCategory.objects.create(nombre="Pinchazo")
        self.assertEqual(str(cat), "Pinchazo")
