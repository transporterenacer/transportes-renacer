from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.documentos.management.commands.setup_document_types import Command as C
from apps.documentos.models import Document, DocumentType
from apps.documentos.services import cargar_documento
from apps.flota.models import Vehicle
from apps.flota.services import (
    ESTADO_NORMAL,
    ESTADO_PROXIMO,
    ESTADO_VENCIDO,
    alertas_vencimiento,
    documento_estado,
)


class DocumentoEstadoTests(TestCase):
    def setUp(self):
        C().handle()
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.soat = DocumentType.objects.get(codigo="soat")

    def _doc(self, vencimiento):
        return cargar_documento(
            tipo=self.soat, entidad=self.vehicle, archivo=b"%PDF-1.4",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=timezone.localdate(),
            fecha_vencimiento=vencimiento,
        )

    def test_normal_cuando_mas_de_30_dias(self):
        doc = self._doc(timezone.localdate() + timedelta(days=31))
        self.assertEqual(documento_estado(doc), ESTADO_NORMAL)

    def test_proximo_dentro_de_30_dias(self):
        doc = self._doc(timezone.localdate() + timedelta(days=10))
        self.assertEqual(documento_estado(doc), ESTADO_PROXIMO)

    def test_vencido(self):
        doc = self._doc(timezone.localdate() - timedelta(days=1))
        self.assertEqual(documento_estado(doc), ESTADO_VENCIDO)


class AlertasVencimientoTests(TestCase):
    def setUp(self):
        C().handle()
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.soat = DocumentType.objects.get(codigo="soat")
        self.tecno = DocumentType.objects.get(codigo="tecnomecanica")

    def _cargar(self, tipo, vencimiento):
        cargar_documento(
            tipo=tipo, entidad=self.vehicle, archivo=b"%PDF-1.4",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=timezone.localdate(),
            fecha_vencimiento=vencimiento,
        )

    def test_alertas_solo_proximo_y_vencido(self):
        self._cargar(self.soat, timezone.localdate() + timedelta(days=60))
        self._cargar(self.tecno, timezone.localdate() + timedelta(days=10))
        alerts = alertas_vencimiento()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["estado"], ESTADO_PROXIMO)

    def test_alertas_ordenadas_por_dias(self):
        self._cargar(self.soat, timezone.localdate() + timedelta(days=15))
        self._cargar(self.tecno, timezone.localdate() - timedelta(days=3))
        alerts = alertas_vencimiento()
        days = [a["dias"] for a in alerts]
        self.assertEqual(days, sorted(days))
        self.assertEqual(alerts[0]["estado"], ESTADO_VENCIDO)
