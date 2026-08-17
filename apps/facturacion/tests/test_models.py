from datetime import date

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
        self.assertIsNone(br.numero_relacion)

    def test_numero_relacion_nullable_repite_sin_conflicto(self):
        BillingRecord.objects.create(
            operation=self.op, fecha=date(2026, 8, 10), horas=11,
            tarifa_hora=35000, valor=385000,
        )
        BillingRecord.objects.create(
            operation=self.op, fecha=date(2026, 8, 11), horas=8,
            tarifa_hora=35000, valor=280000,
        )
        self.assertEqual(self.op.billing_records.count(), 2)

    def test_numero_relacion_compartido_por_relacion(self):
        BillingRecord.objects.create(
            operation=self.op, numero_relacion="REL-OP-001-001",
            fecha=date(2026, 8, 10), horas=11, tarifa_hora=35000, valor=385000,
        )
        BillingRecord.objects.create(
            operation=self.op, numero_relacion="REL-OP-001-001",
            fecha=date(2026, 8, 11), horas=8, tarifa_hora=35000, valor=280000,
        )
        self.assertEqual(self.op.billing_records.count(), 2)

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
        self.assertEqual(cp.metodo, ClientPayment.EFECTIVO)
        self.assertEqual(self.op.client_payments.count(), 1)
