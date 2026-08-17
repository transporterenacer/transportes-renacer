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


class FinancieroDashboardTests(TestCase):
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
        BillingRecord.objects.create(
            operation=self.op, fecha=date(2026, 8, 10), horas=11,
            tarifa_hora=35000, valor=385000,
        )
        ClientPayment.objects.create(operation=self.op, valor=200000)
        self.client.force_login(self.user)

    def test_financiero_muestra_totales(self):
        response = self.client.get(reverse("dashboard:financiero"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OP-001")

    def test_financiero_saldo_desde_turnos_no_desde_relaciones(self):
        response = self.client.get(reverse("dashboard:financiero"))
        self.assertContains(response, "OP-001")
        self.assertContains(response, "185.000")

    def test_financiero_carga_chartjs_vendored(self):
        response = self.client.get(reverse("dashboard:financiero"))
        self.assertContains(response, "chart.umd.js")
