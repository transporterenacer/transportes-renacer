from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.nomina.models import Payroll
from apps.nomina.services import crear_liquidacion
from apps.operaciones.models import Operation, Shift


class NominaViewsTests(TestCase):
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

    def test_lista_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse("nomina:lista"))
        self.assertEqual(response.status_code, 302)

    def test_crear_liquidacion_via_post(self):
        response = self.client.post(
            reverse("nomina:nueva"),
            {"periodo_inicio": "10/08/2026", "periodo_fin": "16/08/2026"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Payroll.objects.count(), 1)
        self.assertEqual(Payroll.objects.first().numero, "NOM-2026-001")

    def test_periodo_sin_turnos_no_rompe_http_500(self):
        response = self.client.post(
            reverse("nomina:nueva"),
            {"periodo_inicio": "01/09/2026", "periodo_fin": "07/09/2026"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "No hay turnos pendientes de pago en el periodo seleccionado."
        )
        self.assertEqual(Payroll.objects.count(), 0)

    def test_detalle_muestra_conductor_y_neto(self):
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        response = self.client.get(reverse("nomina:detalle", args=[payroll.pk]))
        self.assertContains(response, "Juan Pérez")
        self.assertContains(response, "NOM-2026-001")

    def test_marcar_pagada_via_post(self):
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        response = self.client.post(reverse("nomina:marcar_pagada", args=[payroll.pk]))
        self.assertEqual(response.status_code, 302)
        payroll.refresh_from_db()
        self.assertEqual(payroll.estado, Payroll.PAGADO)
