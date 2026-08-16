from datetime import date

from django.db import IntegrityError
from django.test import TestCase

from apps.catalogos.models import CargoGenerator, Port
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.operaciones.models import Operation


class BillingRecordTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.op = Operation.objects.create(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )

    def test_creation_y_str(self):
        br = BillingRecord.objects.create(
            operation=self.op,
            fecha=date(2026, 8, 10),
            horas=11,
            tarifa_hora=35000,
            valor=385000,
        )
        self.assertEqual(str(br), "OP-001 - -")
        self.assertEqual(br.estado, BillingRecord.PENDIENTE)

    def test_estados_constants(self):
        self.assertEqual(BillingRecord.PENDIENTE, "pendiente")
        self.assertEqual(BillingRecord.COBRADO, "cobrado")


class ClientPaymentTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.op = Operation.objects.create(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )

    def test_creacion_y_str(self):
        cp = ClientPayment.objects.create(operation=self.op, valor=5000000)
        self.assertEqual(str(cp), "OP-001 $5000000")
        self.assertEqual(self.op.client_payments.count(), 1)
