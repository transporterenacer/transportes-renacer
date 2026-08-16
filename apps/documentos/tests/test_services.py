import uuid
from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from apps.documentos.management.commands.setup_document_types import Command as C
from apps.documentos.models import Document, DocumentAudit, DocumentType
from apps.documentos.services import (
    cargar_documento,
    desactivar_conductor,
    documentos_faltantes,
    documentos_vigentes_entidad,
    estado_documento,
    generar_nombre_archivo,
    generar_storage_path,
)
from apps.documentos.storage import get_storage_backend
from apps.conductores.models import Driver
from apps.flota.models import Vehicle


@override_settings(DOCUMENT_STORAGE_BACKEND="local")
class CargarDocumentoTests(TestCase):
    def setUp(self):
        C().handle()
        self.usuario = User.objects.create_user(username="maria", password="x")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.soat = DocumentType.objects.get(codigo="soat")

    def test_generar_storage_path(self):
        path = generar_storage_path(self.soat, self.vehicle, "pdf")
        self.assertTrue(path.startswith("vehicles/ABC123/soat/"))
        self.assertTrue(path.endswith(".pdf"))
        self.assertEqual(len(path.split("/")[-1].split(".")[0]), 36)  # uuid

    def test_generar_nombre_archivo(self):
        nombre = generar_nombre_archivo(self.soat, self.vehicle, 2027, "pdf")
        self.assertEqual(nombre, "SOAT_ABC123_2027.pdf")

    def test_cargar_documento_crea_vigente(self):
        doc = cargar_documento(
            tipo=self.soat,
            entidad=self.vehicle,
            archivo=b"%PDF-1.4",
            content_type="application/pdf",
            extension="pdf",
            tamano=1024,
            fecha_expedicion=date(2027, 1, 1),
            fecha_vencimiento=date(2028, 1, 1),
            usuario=self.usuario,
        )
        self.assertEqual(doc.estado, Document.VIGENTE)
        self.assertEqual(doc.cargado_por, self.usuario)
        self.assertEqual(self.vehicle.documentos_doc.count(), 1)
        self.assertTrue(DocumentAudit.objects.filter(accion=DocumentAudit.CARGA).exists())

    def test_cargar_documento_reemplaza_anterior(self):
        doc1 = cargar_documento(
            tipo=self.soat, entidad=self.vehicle, archivo=b"%PDF-1.4 v1",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2026, 1, 1), fecha_vencimiento=date(2027, 1, 1),
            usuario=self.usuario,
        )
        path1 = doc1.storage_path
        doc2 = cargar_documento(
            tipo=self.soat, entidad=self.vehicle, archivo=b"%PDF-1.4 v2",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2027, 1, 1), fecha_vencimiento=date(2028, 1, 1),
            usuario=self.usuario,
        )
        doc1.refresh_from_db()
        self.assertEqual(doc1.estado, Document.REEMPLAZADO)
        self.assertEqual(doc2.estado, Document.VIGENTE)
        self.assertNotEqual(path1, doc2.storage_path)
        self.assertFalse(get_storage_backend().existe(path1))
        audit = DocumentAudit.objects.get(accion=DocumentAudit.REEMPLAZO)
        self.assertEqual(audit.archivo_anterior, path1)
        self.assertEqual(audit.archivo_nuevo, doc2.storage_path)

    def test_estado_documento(self):
        from django.utils import timezone
        from datetime import timedelta

        doc = cargar_documento(
            tipo=self.soat, entidad=self.vehicle, archivo=b"%PDF-1.4",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2027, 1, 1),
            fecha_vencimiento=timezone.localdate() + timedelta(days=10),
            usuario=self.usuario,
        )
        self.assertEqual(estado_documento(doc), "proximo")


class FaltantesTests(TestCase):
    def setUp(self):
        C().handle()
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123456789")

    def test_vehicle_sin_soat_aparece_faltante(self):
        faltantes = documentos_faltantes()
        soat_vehicles = [f for f in faltantes if f["tipo"].codigo == "soat"]
        self.assertTrue(soat_vehicles)

    def test_driver_sin_cedula_aparece_faltante(self):
        faltantes = documentos_faltantes()
        cedula_drivers = [f for f in faltantes if f["tipo"].codigo == "cedula"]
        self.assertTrue(cedula_drivers)


@override_settings(DOCUMENT_STORAGE_LIMIT=10000)
class IndicadorAlmacenamientoTests(TestCase):
    def setUp(self):
        C().handle()
        self.usuario = User.objects.create_user(username="maria", password="x")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.soat = DocumentType.objects.get(codigo="soat")
        cargar_documento(
            tipo=self.soat, entidad=self.vehicle, archivo=b"%PDF-1.4",
            content_type="application/pdf", extension="pdf", tamano=2048,
            fecha_expedicion=date(2027, 1, 1), fecha_vencimiento=date(2028, 1, 1),
            usuario=self.usuario,
        )

    def test_indicador_almacenamiento(self):
        from apps.documentos.services import indicador_almacenamiento

        data = indicador_almacenamiento()
        self.assertIn("usado", data)
        self.assertIn("limite", data)
        self.assertIn("porcentaje", data)
        self.assertGreaterEqual(data["usado"], 2048)
        self.assertGreater(data["porcentaje"], 0.0)


class DocumentosVigentesEntidadTests(TestCase):
    def setUp(self):
        C().handle()
        self.usuario = User.objects.create_user(username="maria", password="x")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123456789")
        self.soat = DocumentType.objects.get(codigo="soat")
        self.cedula = DocumentType.objects.get(codigo="cedula")

    def test_vigentes_filtra_por_entity_type_con_mismo_pk(self):
        self.assertEqual(self.vehicle.pk, self.driver.pk)
        doc_vehicle = cargar_documento(
            tipo=self.soat, entidad=self.vehicle, archivo=b"%PDF-1.4",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2027, 1, 1), fecha_vencimiento=date(2028, 1, 1),
            usuario=self.usuario,
        )
        doc_driver = cargar_documento(
            tipo=self.cedula, entidad=self.driver, archivo=b"datos",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2027, 1, 1), usuario=self.usuario,
        )
        self.assertEqual(doc_vehicle.entity_id, doc_driver.entity_id)
        self.assertNotEqual(doc_vehicle.entity_type_id, doc_driver.entity_type_id)
        self.assertEqual(
            [d.pk for d in documentos_vigentes_entidad(self.vehicle)],
            [doc_vehicle.pk],
        )
        self.assertEqual(
            [d.pk for d in documentos_vigentes_entidad(self.driver)],
            [doc_driver.pk],
        )


class DesactivarConductorTests(TestCase):
    def setUp(self):
        C().handle()
        self.usuario = User.objects.create_user(username="maria", password="x")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123456789")
        self.cedula = DocumentType.objects.get(codigo="cedula")

    @override_settings(DOCUMENT_STORAGE_BACKEND="local")
    def test_desactivar_marca_inactivo_y_borra_documentos(self):
        cargar_documento(
            tipo=self.cedula, entidad=self.driver, archivo=b"datos",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2026, 1, 1), usuario=self.usuario,
        )
        self.assertEqual(self.driver.documentos_doc.count(), 1)
        borrados = desactivar_conductor(self.driver, usuario=self.usuario)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.estado, Driver.INACTIVO)
        self.assertEqual(borrados, 1)
        self.assertEqual(self.driver.documentos_doc.count(), 0)
        self.assertTrue(
            DocumentAudit.objects.filter(accion=DocumentAudit.BORRADO).exists()
        )
