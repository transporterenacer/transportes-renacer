from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift


class FacturacionViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123")
        self.op = Operation.objects.create(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            meta_horas=11,
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )
        Shift.objects.create(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, 10, 6, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, 10, 17, 0)),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )
        self.client.force_login(self.user)

    def test_detalle_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse("facturacion:detalle", args=[self.op.pk]))
        self.assertEqual(response.status_code, 302)

    def test_generar_billing_via_post(self):
        response = self.client.post(reverse("facturacion:generar", args=[self.op.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BillingRecord.objects.count(), 1)
        self.assertEqual(BillingRecord.objects.first().valor, 385000)

    def test_registrar_abono_via_post(self):
        response = self.client.post(
            reverse("facturacion:abono", args=[self.op.pk]),
            {"valor": 200000, "fecha": "15/08/2026"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ClientPayment.objects.count(), 1)

    def test_csv_endpoint(self):
        response = self.client.post(reverse("facturacion:generar", args=[self.op.pk]))
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse("facturacion:csv", args=[self.op.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("ABC123", response.content.decode("utf-8-sig"))
