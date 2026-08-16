from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.documentos.models import (
    DocumentType,
    content_type_driver,
    content_type_vehicle,
)
from apps.conductores.models import Driver
from apps.flota.models import Vehicle


class DocumentTypeTests(TestCase):
    def test_creation_y_str(self):
        ct = content_type_vehicle()
        tipo = DocumentType.objects.create(
            nombre="Permiso especial", codigo="permiso_especial", entity_type=ct
        )
        self.assertEqual(str(tipo), "Permiso especial")
        self.assertTrue(tipo.activo)
        self.assertFalse(tipo.requires_expiration)

    def test_codigo_unique(self):
        from django.db import IntegrityError

        ct = content_type_vehicle()
        DocumentType.objects.create(
            nombre="Permiso especial", codigo="permiso_especial", entity_type=ct
        )
        with self.assertRaises(IntegrityError):
            DocumentType.objects.create(
                nombre="Permiso especial 2", codigo="permiso_especial", entity_type=ct
            )

    def test_content_type_vehicle_apunta_a_vehicle(self):
        self.assertEqual(content_type_vehicle().model_class(), Vehicle)

    def test_content_type_driver_apunta_a_driver(self):
        self.assertEqual(content_type_driver().model_class(), Driver)
