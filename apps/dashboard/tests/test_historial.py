from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift


class HistorialDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.client.force_login(self.user)

    def _crear(self, codigo, estado):
        return Operation.objects.create(
            codigo=codigo,
            buque=f"BUQUE {codigo}",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
            estado=estado,
        )

    def test_historial_muestra_finalizadas_y_canceladas(self):
        self._crear("OP-001", Operation.FINALIZADA)
        self._crear("OP-002", Operation.CANCELADA)
        response = self.client.get(reverse("dashboard:historial"))
        self.assertContains(response, "OP-001")
        self.assertContains(response, "OP-002")

    def test_historial_no_muestra_activas(self):
        self._crear("OP-003", Operation.ACTIVA)
        response = self.client.get(reverse("dashboard:historial"))
        self.assertNotContains(response, "OP-003")

    def test_historial_anota_turnos_y_horas(self):
        op = self._crear("OP-004", Operation.FINALIZADA)
        vehicle = Vehicle.objects.create(placa="ABC123")
        driver = Driver.objects.create(nombre="Juan Pérez", documento="123")
        Shift.objects.create(
            operation=op,
            vehicle=vehicle,
            driver=driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, 10, 6, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, 10, 17, 0)),
            tipo=Shift.DIA,
            meta_horas=op.meta_horas,
            valor_estandar=op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )
        response = self.client.get(reverse("dashboard:historial"))
        self.assertEqual(response.status_code, 200)
        fila = response.context["operaciones"].get(codigo="OP-004")
        self.assertEqual(fila.num_turnos, 1)
        self.assertEqual(fila.horas_totales, Decimal("11.00"))
        self.assertContains(response, "11,00")
