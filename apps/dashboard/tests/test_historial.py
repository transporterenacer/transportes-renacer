from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.catalogos.models import CargoGenerator, Port
from apps.operaciones.models import Operation


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
