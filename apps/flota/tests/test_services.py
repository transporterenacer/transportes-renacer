from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.flota.models import Vehicle, VehicleDocument
from apps.flota.services import (
    ALERT_DAYS,
    ESTADO_NORMAL,
    ESTADO_PROXIMO,
    ESTADO_VENCIDO,
    alertas_vencimiento,
    documento_estado,
)


class DocumentoEstadoTests(TestCase):
    def test_normal_when_more_than_30_days(self):
        doc = VehicleDocument(
            vehicle=Vehicle(placa="ABC123"),
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() + timedelta(days=ALERT_DAYS + 1),
        )
        self.assertEqual(documento_estado(doc), ESTADO_NORMAL)

    def test_proximo_when_within_30_days(self):
        doc = VehicleDocument(
            vehicle=Vehicle(placa="ABC123"),
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() + timedelta(days=10),
        )
        self.assertEqual(documento_estado(doc), ESTADO_PROXIMO)

    def test_vencido_when_expired(self):
        doc = VehicleDocument(
            vehicle=Vehicle(placa="ABC123"),
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() - timedelta(days=1),
        )
        self.assertEqual(documento_estado(doc), ESTADO_VENCIDO)


class AlertasVencimientoTests(TestCase):
    def setUp(self):
        self.vehiculo = Vehicle.objects.create(placa="ABC123")

    def test_alerts_include_only_proximo_and_vencido(self):
        VehicleDocument.objects.create(
            vehicle=self.vehiculo,
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() + timedelta(days=60),
        )
        VehicleDocument.objects.create(
            vehicle=self.vehiculo,
            tipo=VehicleDocument.TECNOMECANICA,
            fecha_vencimiento=timezone.localdate() + timedelta(days=10),
        )
        alerts = alertas_vencimiento()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["estado"], ESTADO_PROXIMO)

    def test_alerts_sorted_by_days_ascending(self):
        VehicleDocument.objects.create(
            vehicle=self.vehiculo,
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() + timedelta(days=15),
        )
        VehicleDocument.objects.create(
            vehicle=self.vehiculo,
            tipo=VehicleDocument.TECNOMECANICA,
            fecha_vencimiento=timezone.localdate() - timedelta(days=3),
        )
        alerts = alertas_vencimiento()
        days = [a["dias"] for a in alerts]
        self.assertEqual(days, sorted(days))
        self.assertEqual(days[0], -3)
        self.assertEqual(alerts[0]["estado"], ESTADO_VENCIDO)
