from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Incident, Operation, Shift


class OperativoDashboardTests(TestCase):
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
        self.client.force_login(self.user)

    def _shift(self, inicio_h, fin_h, dia=10):
        return Shift.objects.create(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, dia, inicio_h, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, dia, fin_h, 0)),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )

    def test_operativo_muestra_horas_y_cumplimiento(self):
        self._shift(6, 17)
        response = self.client.get(reverse("dashboard:operativo"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ABC123")

    def test_operativo_muestra_novedades(self):
        shift = self._shift(6, 14)
        cat = IncidentCategory.objects.create(nombre="Lluvia")
        Incident.objects.create(shift=shift, categoria=cat)
        response = self.client.get(reverse("dashboard:operativo"))
        self.assertContains(response, "Lluvia")
