from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation
from apps.operaciones.services import asignar_mulas, registrar_turno


class OperacionesViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123")
        self.lluvia = IncidentCategory.objects.create(nombre="Lluvia")
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
            estado=Operation.ACTIVA,
        )
        asignar_mulas(self.op, [self.vehicle])
        self.client.force_login(self.user)

    def test_lista_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse("operaciones:lista"))
        self.assertEqual(response.status_code, 302)

    def test_lista_muestra_operaciones(self):
        response = self.client.get(reverse("operaciones:lista"))
        self.assertContains(response, "BUQUE ATLANTIC")

    def test_detalle_muestra_turnos(self):
        registrar_turno(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.datetime(2026, 8, 10, 6, 0),
            fecha_fin=timezone.datetime(2026, 8, 10, 17, 0),
            tipo="dia",
            valor_estandar=self.op.valor_turno_dia,
            meta_horas=self.op.meta_horas,
        )
        response = self.client.get(reverse("operaciones:detalle", args=[self.op.pk]))
        self.assertContains(response, "Juan Pérez")
        self.assertContains(response, "ABC123")

    def test_registrar_turno_via_post(self):
        response = self.client.post(
            reverse("operaciones:turno_nuevo", args=[self.op.pk]),
            {
                "vehicle": self.vehicle.pk,
                "driver": self.driver.pk,
                "fecha_inicio_date": "2026-08-10",
                "fecha_inicio_time": "06:00",
                "fecha_fin_date": "2026-08-10",
                "fecha_fin_time": "17:00",
                "tipo": "dia",
                "novedad_categoria": self.lluvia.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.op.shifts.count(), 1)


class AgregarMulaOperacionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.v1 = Vehicle.objects.create(placa="ABC123")
        self.v2 = Vehicle.objects.create(placa="DEF456")
        self.op = Operation.objects.create(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
            estado=Operation.ACTIVA,
        )
        self.client.force_login(self.user)

    def test_agregar_mula_disponible_via_post(self):
        response = self.client.post(
            reverse("operaciones:mula_agregar", args=[self.op.pk, self.v2.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.v2.refresh_from_db()
        self.assertEqual(self.v2.estado, Vehicle.EN_OPERACION)
        self.assertTrue(self.op.mulas.filter(activa=True, vehicle=self.v2).exists())

    def test_agregar_mula_en_taller_rechazada(self):
        self.v2.estado = Vehicle.EN_TALLER
        self.v2.save()
        response = self.client.post(
            reverse("operaciones:mula_agregar", args=[self.op.pk, self.v2.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.op.mulas.filter(activa=True, vehicle=self.v2).exists())

    def test_detalle_muestra_mulas_disponibles(self):
        response = self.client.get(reverse("operaciones:detalle", args=[self.op.pk]))
        self.assertContains(response, "DEF456")
        self.assertContains(response, "Agregar mula")
