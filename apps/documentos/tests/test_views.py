from datetime import date

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.documentos.management.commands.setup_document_types import Command as C
from apps.documentos.models import Document
from apps.documentos.services import cargar_documento
from apps.conductores.models import Driver
from apps.flota.models import Vehicle


@override_settings(DOCUMENT_STORAGE_BACKEND="local")
class DocumentosViewsTests(TestCase):
    def setUp(self):
        C().handle()
        self.user = User.objects.create_user(username="ana", password="x")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123456789")
        self.client.force_login(self.user)

    def test_panel_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse("documentos:panel"))
        self.assertEqual(response.status_code, 302)

    def test_panel_renderiza(self):
        response = self.client.get(reverse("documentos:panel"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Documentos")

    def test_ficha_vehicle_muestra_documentos(self):
        from apps.documentos.models import DocumentType

        soat = DocumentType.objects.get(codigo="soat")
        cargar_documento(
            tipo=soat, entidad=self.vehicle, archivo=b"%PDF-1.4",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2027, 1, 1), fecha_vencimiento=date(2028, 1, 1),
            usuario=self.user,
        )
        response = self.client.get(reverse("documentos:vehicle", args=[self.vehicle.pk]))
        self.assertContains(response, "ABC123")
        self.assertContains(response, "SOAT")

    def test_subir_documento_via_post(self):
        soat = self.client.post(
            reverse("documentos:subir") + "?vehicle=" + str(self.vehicle.pk),
            {
                "tipo": "soat",
                "archivo": SimpleUploadedFile(
                    "soat.pdf", b"%PDF-1.4 datos", content_type="application/pdf"
                ),
                "fecha_expedicion": "01/01/2027",
                "fecha_vencimiento": "01/01/2028",
            },
        )
        self.assertEqual(soat.status_code, 302)
        self.assertEqual(self.vehicle.documentos_doc.count(), 1)

    def test_descargar_envia_archivo_adjunto(self):
        from apps.documentos.models import DocumentType

        soat = DocumentType.objects.get(codigo="soat")
        doc = cargar_documento(
            tipo=soat, entidad=self.vehicle, archivo=b"%PDF-1.4",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2027, 1, 1), fecha_vencimiento=date(2028, 1, 1),
            usuario=self.user,
        )
        response = self.client.get(reverse("documentos:descargar", args=[doc.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response.content, b"%PDF-1.4")

    def test_reemplazo_confirmacion_y_post(self):
        from apps.documentos.models import DocumentType

        soat = DocumentType.objects.get(codigo="soat")
        doc = cargar_documento(
            tipo=soat, entidad=self.vehicle, archivo=b"%PDF-1.4 v1",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2026, 1, 1), fecha_vencimiento=date(2027, 1, 1),
            usuario=self.user,
        )
        url = reverse("documentos:reemplazar", args=[doc.pk])
        get = self.client.get(url)
        self.assertContains(get, "reemplazar")

        post = self.client.post(
            url,
            {
                "archivo": SimpleUploadedFile(
                    "soat.pdf", b"%PDF-1.4 v2", content_type="application/pdf"
                ),
                "fecha_expedicion": "01/01/2027",
                "fecha_vencimiento": "01/01/2028",
            },
        )
        self.assertEqual(post.status_code, 302)
        doc.refresh_from_db()
        self.assertEqual(doc.estado, "reemplazado")

    def test_desactivar_conductor_via_post(self):
        url = reverse("documentos:desactivar_conductor", args=[self.driver.pk])
        get = self.client.get(url)
        self.assertContains(get, "será marcado como inactivo")
        post = self.client.post(url)
        self.assertEqual(post.status_code, 302)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.estado, Driver.INACTIVO)
