import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Incident, Operation, Shift


class GanttTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.v1 = Vehicle.objects.create(placa="ABC123")
        self.v2 = Vehicle.objects.create(placa="DEF456")
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

    def _shift(self, vehicle, inicio, fin, estado=Shift.REALIZADO, tipo=Shift.DIA):
        return Shift.objects.create(
            operation=self.op,
            vehicle=vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(inicio),
            fecha_fin=timezone.make_aware(fin),
            tipo=tipo,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=estado,
        )

    def test_gantt_pagina_renderiza(self):
        response = self.client.get(reverse("dashboard:gantt", args=[self.op.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BUQUE ATLANTIC")

    def test_gantt_datos_incluye_filas_y_bloques(self):
        self._shift(
            self.v1,
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
        )
        self._shift(
            self.v2,
            timezone.datetime(2026, 8, 10, 18, 0),
            timezone.datetime(2026, 8, 11, 6, 0),
            tipo=Shift.NOCHE,
        )
        response = self.client.get(reverse("dashboard:gantt_datos", args=[self.op.pk]))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["operation"]["codigo"], "OP-001")
        placas = [fila["placa"] for fila in data["filas"]]
        self.assertIn("ABC123", placas)
        self.assertIn("DEF456", placas)

    def test_gantt_datos_incluye_novedad(self):
        shift = self._shift(
            self.v1,
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 14, 0),
        )
        cat = IncidentCategory.objects.create(nombre="Lluvia")
        Incident.objects.create(shift=shift, categoria=cat, descripcion="Todo el día")
        response = self.client.get(reverse("dashboard:gantt_datos", args=[self.op.pk]))
        data = json.loads(response.content)
        bloque = data["filas"][0]["bloques"][0]
        self.assertEqual(bloque["novedad"], "Lluvia")
