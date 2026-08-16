import uuid
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from apps.documentos.models import Document, DocumentAudit, DocumentType
from apps.conductores.models import Driver
from apps.flota.models import Vehicle


class DocumentTests(TestCase):
    def setUp(self):
        from apps.documentos.management.commands.setup_document_types import Command as C

        C().handle()
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123456789")
        self.soat = DocumentType.objects.get(codigo="soat")
        self.cedula = DocumentType.objects.get(codigo="cedula")

    def _doc(self, tipo, entidad, **kwargs):
        defaults = dict(
            tipo=tipo,
            nombre_archivo="SOAT_ABC123_2027.pdf",
            storage_path=f"vehicles/ABC123/soat/{uuid.uuid4()}.pdf",
            extension="pdf",
            mime_type="application/pdf",
            tamano=1024,
            fecha_expedicion=date(2027, 1, 1),
        )
        defaults.update(kwargs)
        return Document.objects.create(entity=entidad, **defaults)

    def test_creacion_con_entity(self):
        doc = self._doc(self.soat, self.vehicle)
        self.assertEqual(doc.entity, self.vehicle)
        self.assertEqual(doc.estado, Document.VIGENTE)
        self.assertEqual(str(doc), "SOAT_ABC123_2027.pdf")

    def test_generic_relation_en_vehicle(self):
        self._doc(self.soat, self.vehicle)
        self.assertEqual(self.vehicle.documentos_doc.count(), 1)

    def test_generic_relation_en_driver(self):
        self._doc(self.cedula, self.driver)
        self.assertEqual(self.driver.documentos_doc.count(), 1)

    def test_es_personal_true_para_driver(self):
        doc = self._doc(self.cedula, self.driver)
        self.assertTrue(doc.es_personal)

    def test_es_personal_false_para_vehicle(self):
        doc = self._doc(self.soat, self.vehicle)
        self.assertFalse(doc.es_personal)

    def test_storage_path_unique(self):
        from django.db import IntegrityError

        path = f"vehicles/ABC123/soat/{uuid.uuid4()}.pdf"
        self._doc(self.soat, self.vehicle, storage_path=path)
        with self.assertRaises(IntegrityError):
            self._doc(self.soat, self.vehicle, storage_path=path)


class DocumentAuditTests(TestCase):
    def test_creacion(self):
        usuario = User.objects.create_user(username="maria", password="x")
        audit = DocumentAudit.objects.create(
            usuario=usuario,
            accion=DocumentAudit.REEMPLAZO,
            tipo="soat",
            archivo_anterior="SOAT_ABC123_2026.pdf",
            archivo_nuevo="SOAT_ABC123_2027.pdf",
            detalle="Reemplazo",
        )
        self.assertEqual(str(audit), "reemplazo soat")
        self.assertEqual(audit.archivo_anterior, "SOAT_ABC123_2026.pdf")
