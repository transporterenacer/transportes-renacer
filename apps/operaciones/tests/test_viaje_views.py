from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import OperationExpense, Viaje


class ViajeViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        self.user.groups.add(admin_group)
        self.cliente = CargoGenerator.objects.create(nombre="Cliente SA", nit="900111222-3")
        self.vehicle = Vehicle.objects.create(placa="ABC123", marca="Kenworth", estado=Vehicle.DISPONIBLE)
        self.driver = Driver.objects.create(nombre="Carlos", documento="1023456789")
        self.ahora = timezone.make_aware(datetime(2026, 8, 10, 6, 0))
        self.viaje = Viaje.objects.create(
            cliente=self.cliente, vehicle=self.vehicle, driver=self.driver,
            origen="Barranquilla", destino="Cartagena",
            fecha_ida=self.ahora, fecha_vuelta=self.ahora + timedelta(hours=8),
            valor_cobrado=Decimal("800000"), valor_conductor=Decimal("400000"),
        )
        self.client.force_login(self.user)

    def test_lista_requiere_login(self):
        self.client.logout()
        resp = self.client.get(reverse("operaciones:viaje_lista"))
        self.assertEqual(resp.status_code, 302)

    def test_lista_muestra_viajes(self):
        resp = self.client.get(reverse("operaciones:viaje_lista"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Barranquilla")

    def test_nuevo_viaje_post_crea(self):
        resp = self.client.post(reverse("operaciones:viaje_nuevo"), {
            "cliente": self.cliente.pk,
            "vehicle": self.vehicle.pk,
            "driver": self.driver.pk,
            "origen": "Barranquilla",
            "destino": "Santa Marta",
            "fecha_ida": "2026-08-15T06:00",
            "fecha_vuelta": "2026-08-15T14:00",
            "valor_cobrado": "900000",
            "valor_conductor": "450000",
            "observaciones": "",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Viaje.objects.filter(destino="Santa Marta").exists())

    def test_detalle_muestra_resumen(self):
        resp = self.client.get(reverse("operaciones:viaje_detalle", args=[self.viaje.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "800.000")

    def test_iniciar_viaje(self):
        resp = self.client.post(reverse("operaciones:viaje_iniciar", args=[self.viaje.pk]))
        self.assertEqual(resp.status_code, 302)
        self.viaje.refresh_from_db()
        self.assertEqual(self.viaje.estado, Viaje.EN_VIAJE)

    def test_finalizar_viaje(self):
        self.viaje.estado = Viaje.EN_VIAJE
        self.viaje.save()
        resp = self.client.post(reverse("operaciones:viaje_finalizar", args=[self.viaje.pk]))
        self.assertEqual(resp.status_code, 302)
        self.viaje.refresh_from_db()
        self.assertEqual(self.viaje.estado, Viaje.FINALIZADO)

    def test_cancelar_viaje(self):
        resp = self.client.post(reverse("operaciones:viaje_cancelar", args=[self.viaje.pk]), {"motivo": "no aplica"})
        self.assertEqual(resp.status_code, 302)
        self.viaje.refresh_from_db()
        self.assertEqual(self.viaje.estado, Viaje.CANCELADO)

    def test_gasto_nuevo_viaje(self):
        resp = self.client.post(reverse("operaciones:viaje_gasto_nuevo", args=[self.viaje.pk]), {
            "categoria": OperationExpense.COMBUSTIBLE,
            "vehicle": self.vehicle.pk,
            "proveedor": "",
            "fecha": "2026-08-10",
            "valor": "450000",
            "galones": "120",
            "descripcion": "ACPM",
            "numero_factura": "FAC-001",
            "observaciones": "",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(OperationExpense.objects.filter(viaje=self.viaje).exists())
