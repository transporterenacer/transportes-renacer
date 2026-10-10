from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.nomina.models import Payroll, PayrollItem
from apps.nomina.services import crear_liquidacion, resumen_liquidacion, viajes_pendientes_pago
from apps.operaciones.models import Viaje


class PayrollItemViajeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="x")
        self.cliente = CargoGenerator.objects.create(nombre="Cliente SA", nit="1")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Carlos", documento="1")
        self.ahora = timezone.make_aware(datetime(2026, 8, 10, 6, 0))

    def _viaje(self, driver=None, fecha_ida=None, **kwargs):
        defaults = dict(
            cliente=self.cliente,
            vehicle=self.vehicle,
            driver=driver or self.driver,
            origen="Barranquilla",
            destino="Cartagena",
            fecha_ida=fecha_ida or self.ahora,
            fecha_vuelta=(fecha_ida or self.ahora) + timedelta(hours=8),
            valor_cobrado=Decimal("800000"),
            valor_conductor=Decimal("400000"),
            estado=Viaje.FINALIZADO,
        )
        defaults.update(kwargs)
        return Viaje.objects.create(**defaults)

    def test_viajes_pendientes_pago_encuentra_finalizados_sin_payroll(self):
        v = self._viaje()
        qs = viajes_pendientes_pago(date(2026, 8, 1), date(2026, 8, 31))
        self.assertIn(v, qs)

    def test_viajes_pendientes_pago_excluye_liquidados(self):
        v = self._viaje()
        payroll = Payroll.objects.create(
            numero="NOM-2026-001",
            periodo_inicio=date(2026, 8, 1),
            periodo_fin=date(2026, 8, 31),
        )
        PayrollItem.objects.create(payroll=payroll, viaje=v, valor=Decimal("400000"))
        qs = viajes_pendientes_pago(date(2026, 8, 1), date(2026, 8, 31))
        self.assertNotIn(v, qs)

    def test_crear_liquidacion_incluye_viaje(self):
        self._viaje()
        payroll = crear_liquidacion(date(2026, 8, 1), date(2026, 8, 31), usuario=self.user)
        item = payroll.items.get()
        self.assertIsNotNone(item.viaje)
        self.assertIsNone(item.shift)
        self.assertEqual(item.valor, Decimal("400000"))
        self.assertEqual(payroll.total, Decimal("400000"))

    def test_resumen_liquidacion_agrupa_por_conductor_con_viajes(self):
        self._viaje()
        payroll = crear_liquidacion(date(2026, 8, 1), date(2026, 8, 31))
        resumen = resumen_liquidacion(payroll)
        self.assertEqual(len(resumen), 1)
        self.assertEqual(resumen[0]["driver"], self.driver)
        self.assertEqual(resumen[0]["total"], Decimal("400000"))
        self.assertEqual(resumen[0]["horas"], Decimal("0"))

    def test_crear_liquidacion_sin_nada_lanza_error(self):
        with self.assertRaises(ValidationError):
            crear_liquidacion(date(2026, 8, 1), date(2026, 8, 31))

    def test_payroll_item_requiere_exactamente_un_concepto(self):
        payroll = Payroll.objects.create(
            numero="NOM-2026-050",
            periodo_inicio=date(2026, 8, 1),
            periodo_fin=date(2026, 8, 31),
        )
        item = PayrollItem(payroll=payroll, valor=Decimal("1000"))
        with self.assertRaises(ValidationError):
            item.full_clean()
