from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.dashboard.services import kpis_inicio
from apps.flota.models import Vehicle
from apps.nomina.services import crear_liquidacion, registrar_abono, registrar_pago
from apps.operaciones.models import Operation, Shift


class NominaDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.v1 = Vehicle.objects.create(placa="ABC123")
        self.v2 = Vehicle.objects.create(placa="DEF456")
        self.juan = Driver.objects.create(nombre="Juan Pérez", documento="123")
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

    def _shift(self, vehicle, dia):
        return Shift.objects.create(
            operation=self.op,
            vehicle=vehicle,
            driver=self.juan,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, dia, 6, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, dia, 17, 0)),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )

    def test_kpis_inicio_acumula_pendiente(self):
        self._shift(self.v1, 10)
        self._shift(self.v2, 11)
        crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_abono(self.juan, 100000)
        kpis = kpis_inicio()
        self.assertEqual(kpis["nomina_pendiente"], Decimal(260000))

    def test_home_muestra_pendiente_acumulado(self):
        self._shift(self.v1, 10)
        response = self.client.get(reverse("dashboard:inicio"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nómina pendiente")

    def test_lista_muestra_pendiente_acumulado(self):
        self._shift(self.v1, 10)
        self._shift(self.v2, 11)
        crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_pago(self.juan, 100000)
        response = self.client.get(reverse("nomina:lista"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pendiente acumulado")
        self.assertContains(response, "260.000")