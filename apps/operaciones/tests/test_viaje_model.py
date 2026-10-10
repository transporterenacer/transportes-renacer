from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Viaje


class ViajeModelTests(TestCase):
    def setUp(self):
        self.cliente = CargoGenerator.objects.create(
            nombre="Distribuidora Norte", nit="900111222-3"
        )
        self.vehicle = Vehicle.objects.create(
            placa="XYZ789", marca="Volvo", modelo="FH", anio=2022
        )
        self.driver = Driver.objects.create(nombre="Pedro Gómez", documento="987654321")
        self.ahora = timezone.make_aware(datetime(2026, 8, 10, 6, 0))

    def _viaje(self, **kwargs):
        defaults = dict(
            cliente=self.cliente,
            vehicle=self.vehicle,
            driver=self.driver,
            origen="Barranquilla",
            destino="Cartagena",
            fecha_ida=self.ahora,
            fecha_vuelta=self.ahora + timedelta(hours=8),
            valor_cobrado=Decimal("800000"),
            valor_conductor=Decimal("400000"),
        )
        defaults.update(kwargs)
        return Viaje(**defaults)

    def test_estado_inicial_es_pendiente(self):
        v = self._viaje()
        self.assertEqual(v.estado, Viaje.PENDIENTE)

    def test_clean_acepta_fechas_validas(self):
        v = self._viaje()
        v.full_clean()

    def test_clean_rechaza_fecha_vuelta_menor_o_igual(self):
        v = self._viaje(fecha_vuelta=self.ahora)
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_clean_rechaza_valor_cobrado_cero(self):
        v = self._viaje(valor_cobrado=Decimal("0"))
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_clean_rechaza_valor_conductor_negativo(self):
        v = self._viaje(valor_conductor=Decimal("-1000"))
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_codigo_auto_en_save(self):
        v = self._viaje()
        v.save()
        self.assertTrue(v.codigo.startswith("VJ-"))
        self.assertIn(str(v.fecha_ida.year), v.codigo)

    def test_str_muestra_ruta(self):
        v = self._viaje()
        self.assertIn("Barranquilla", str(v))
        self.assertIn("Cartagena", str(v))
