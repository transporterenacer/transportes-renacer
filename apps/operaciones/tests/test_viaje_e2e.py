from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator
from apps.conductores.models import Driver
from apps.facturacion.models import BillingRecord
from apps.flota.models import Vehicle
from apps.nomina.services import crear_liquidacion
from apps.operaciones.models import OperationExpense, Viaje
from apps.operaciones.services import cancelar_viaje, crear_viaje, finalizar_viaje, iniciar_viaje


class ViajeE2ETests(TestCase):
    """Flujo completo: crear → iniciar → gastos → finalizar → facturación → nómina → cancelar bloqueado."""

    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="x")
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        self.user.groups.add(admin_group)
        self.cliente = CargoGenerator.objects.create(nombre="Comercial El Éxito", nit="900111222-3")
        self.vehicle = Vehicle.objects.create(placa="XYZ789", marca="Volvo", estado=Vehicle.DISPONIBLE)
        self.driver = Driver.objects.create(nombre="Luis Pérez", documento="1099887766")
        self.ahora = timezone.make_aware(datetime(2026, 8, 10, 6, 0))

    def test_flujo_completo_viaje_local(self):
        viaje = crear_viaje(
            cliente=self.cliente, vehicle=self.vehicle, driver=self.driver,
            origen="Barranquilla", destino="Cartagena",
            fecha_ida=self.ahora, fecha_vuelta=self.ahora + timedelta(hours=10),
            valor_cobrado=Decimal("1200000"), valor_conductor=Decimal("600000"),
            usuario=self.user,
        )
        self.assertEqual(viaje.estado, Viaje.PENDIENTE)
        self.assertTrue(viaje.codigo.startswith("VJ-"))

        iniciar_viaje(viaje, usuario=self.user)
        viaje.refresh_from_db()
        self.assertEqual(viaje.estado, Viaje.EN_VIAJE)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.estado, Vehicle.EN_OPERACION)

        self.client.force_login(self.user)
        resp = self.client.post(reverse("operaciones:viaje_gasto_nuevo", args=[viaje.pk]), {
            "categoria": OperationExpense.COMBUSTIBLE,
            "vehicle": self.vehicle.pk,
            "proveedor": "",
            "fecha": "2026-08-10",
            "valor": "450000",
            "galones": "120",
            "descripcion": "ACPM viaje",
            "numero_factura": "FV-100",
            "observaciones": "",
        })
        self.assertEqual(resp.status_code, 302)
        resp = self.client.post(reverse("operaciones:viaje_gasto_nuevo", args=[viaje.pk]), {
            "categoria": OperationExpense.PEAJE,
            "vehicle": self.vehicle.pk,
            "proveedor": "",
            "fecha": "2026-08-10",
            "valor": "70000",
            "galones": "",
            "descripcion": "Peaje",
            "numero_factura": "",
            "observaciones": "",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(viaje.expenses.count(), 2)

        finalizar_viaje(viaje, usuario=self.user)
        viaje.refresh_from_db()
        self.assertEqual(viaje.estado, Viaje.FINALIZADO)
        record = BillingRecord.objects.get(viaje=viaje)
        self.assertEqual(record.valor, Decimal("1200000"))
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.estado, Vehicle.DISPONIBLE)

        resp = self.client.get(reverse("operaciones:viaje_detalle", args=[viaje.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "1.200.000")
        self.assertContains(resp, "520.000")

        payroll = crear_liquidacion(date(2026, 8, 1), date(2026, 8, 31), usuario=self.user)
        item = payroll.items.get()
        self.assertEqual(item.viaje, viaje)
        self.assertEqual(item.valor, Decimal("600000"))
        self.assertEqual(payroll.total, Decimal("600000"))

        with self.assertRaises(ValidationError):
            cancelar_viaje(viaje, "intento")
