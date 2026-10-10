from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator
from apps.conductores.models import Driver
from apps.facturacion.models import BillingRecord
from apps.flota.models import Vehicle
from apps.nomina.models import Payroll, PayrollItem
from apps.operaciones.models import Viaje
from apps.operaciones.services import cancelar_viaje, crear_viaje, finalizar_viaje, iniciar_viaje


class ViajeServicesTests(TestCase):
    def setUp(self):
        self.cliente = CargoGenerator.objects.create(nombre="Cliente", nit="1")
        self.vehicle = Vehicle.objects.create(placa="ABC123", estado=Vehicle.DISPONIBLE)
        self.driver = Driver.objects.create(nombre="Juan", documento="1")
        self.ahora = timezone.make_aware(datetime(2026, 8, 10, 6, 0))

    def _crear(self, **kwargs):
        defaults = dict(
            cliente=self.cliente, vehicle=self.vehicle, driver=self.driver,
            origen="Barranquilla", destino="Cartagena",
            fecha_ida=self.ahora, fecha_vuelta=self.ahora + timedelta(hours=8),
            valor_cobrado=Decimal("800000"), valor_conductor=Decimal("400000"),
        )
        defaults.update(kwargs)
        return crear_viaje(**defaults)

    def test_crear_viaje_genera_codigo_y_estado_pendiente(self):
        v = self._crear()
        self.assertTrue(v.codigo.startswith("VJ-"))
        self.assertEqual(v.estado, Viaje.PENDIENTE)

    def test_crear_viaje_rechaza_solape_vehiculo(self):
        self._crear()
        with self.assertRaises(ValidationError):
            self._crear(
                driver=Driver.objects.create(nombre="Ana", documento="2"),
                fecha_ida=self.ahora + timedelta(hours=1),
                fecha_vuelta=self.ahora + timedelta(hours=9),
            )

    def test_iniciar_viaje_cambia_estado_y_vehiculo(self):
        v = self._crear()
        iniciar_viaje(v)
        v.refresh_from_db()
        self.assertEqual(v.estado, Viaje.EN_VIAJE)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.estado, Vehicle.EN_OPERACION)

    def test_finalizar_viaje_crea_billing_record(self):
        v = self._crear()
        iniciar_viaje(v)
        finalizar_viaje(v)
        v.refresh_from_db()
        self.assertEqual(v.estado, Viaje.FINALIZADO)
        record = BillingRecord.objects.get(viaje=v)
        self.assertEqual(record.valor, Decimal("800000"))
        self.assertEqual(record.horas, Decimal("0"))
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.estado, Vehicle.DISPONIBLE)

    def test_cancelar_viaje_bloquea_si_payroll_item(self):
        v = self._crear()
        payroll = Payroll.objects.create(
            numero="NOM-2026-099", periodo_inicio=timezone.localdate(),
            periodo_fin=timezone.localdate()
        )
        PayrollItem.objects.create(payroll=payroll, viaje=v, valor=Decimal("400000"))
        with self.assertRaises(ValidationError):
            cancelar_viaje(v, "motivo")

    def test_finalizar_viaje_bloquea_si_no_en_viaje(self):
        v = self._crear()
        with self.assertRaises(ValidationError):
            finalizar_viaje(v)

    def test_iniciar_viaje_bloquea_si_no_pendiente(self):
        v = self._crear()
        iniciar_viaje(v)
        with self.assertRaises(ValidationError):
            iniciar_viaje(v)
