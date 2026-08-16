import csv
import io
from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.facturacion.services import generar_billing_operacion, generar_csv_facturacion
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift


class CsvFacturacionTests(TestCase):
    def setUp(self):
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

    def _shift(self, vehicle, dia, inicio=6, fin=17):
        return Shift.objects.create(
            operation=self.op,
            vehicle=vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, dia, inicio, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, dia, fin, 0)),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )

    def test_csv_contiene_filas_y_no_chofer(self):
        self._shift(self.v1, 10)
        self._shift(self.v2, 11)
        generar_billing_operacion(self.op)
        csv_texto = generar_csv_facturacion(self.op)
        self.assertNotIn("Juan", csv_texto)
        self.assertIn("ABC123", csv_texto)
        self.assertIn("DEF456", csv_texto)
        self.assertIn("11.00", csv_texto)
        self.assertIn("11/08/2026", csv_texto)

    def test_csv_incluye_resumen_por_mula(self):
        self._shift(self.v1, 10)
        self._shift(self.v1, 11)
        generar_billing_operacion(self.op)
        csv_texto = generar_csv_facturacion(self.op)
        self.assertIn("Mula;Horas totales", csv_texto)
        self.assertIn("ABC123;22.00", csv_texto)

    def test_csv_separador_punto_y_coma(self):
        self._shift(self.v1, 10)
        generar_billing_operacion(self.op)
        csv_texto = generar_csv_facturacion(self.op)
        self.assertTrue(csv_texto.startswith("\ufeff"))
        reader = list(csv.reader(io.StringIO(csv_texto.lstrip("\ufeff")), delimiter=";"))
        self.assertEqual(reader[0][0], "Fecha")
        self.assertEqual(len(reader[0]), 7)
