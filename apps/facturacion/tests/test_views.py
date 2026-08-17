from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift


class FacturacionViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
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
        self.shift = Shift.objects.create(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, 10, 6, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, 10, 17, 0)),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )
        self.client.force_login(self.user)

    def test_detalle_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse("facturacion:detalle", args=[self.op.pk]))
        self.assertEqual(response.status_code, 302)

    def test_lista_renderiza(self):
        response = self.client.get(reverse("facturacion:lista"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OP-001")
        self.assertContains(response, "Valor generado")

    def test_lista_filtra_por_estado(self):
        response = self.client.get(reverse("facturacion:lista") + "?estado=pendientes")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OP-001")

    def test_detalle_muestra_equacion_y_turnos(self):
        response = self.client.get(reverse("facturacion:detalle", args=[self.op.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Valor generado")
        self.assertContains(response, "Saldo por recibir")
        self.assertContains(response, "Enviar turnos al generador")
        self.assertContains(response, "ABC123")

    def test_relacion_nueva_via_post(self):
        response = self.client.post(
            reverse("facturacion:relacion_nueva", args=[self.op.pk]),
            {"shift_ids": [str(self.shift.pk)]},
        )
        self.assertEqual(response.status_code, 302)
        br = BillingRecord.objects.get()
        self.assertEqual(br.valor, 385000)
        self.assertEqual(br.numero_relacion, "REL-OP-001-001")

    def test_registrar_abono_via_post_con_metodo(self):
        response = self.client.post(
            reverse("facturacion:abono", args=[self.op.pk]),
            {"valor": 200000, "fecha": "15/08/2026", "metodo": "transferencia"},
        )
        self.assertEqual(response.status_code, 302)
        abono = ClientPayment.objects.get()
        self.assertEqual(abono.metodo, ClientPayment.TRANSFERENCIA)

    def test_csv_endpoint(self):
        self.client.post(
            reverse("facturacion:relacion_nueva", args=[self.op.pk]),
            {"shift_ids": [str(self.shift.pk)]},
        )
        response = self.client.get(reverse("facturacion:csv", args=[self.op.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("ABC123", response.content.decode("utf-8-sig"))

    def test_csv_resumen_endpoint(self):
        response = self.client.get(reverse("facturacion:csv_resumen"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("Saldo por recibir", response.content.decode("utf-8-sig"))

    def test_detalle_muestra_relaciones_agrupadas(self):
        self.client.post(
            reverse("facturacion:relacion_nueva", args=[self.op.pk]),
            {"shift_ids": [str(self.shift.pk)]},
        )
        response = self.client.get(reverse("facturacion:detalle", args=[self.op.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "REL-OP-001-001")
        self.assertContains(response, "Ver detalle")
        self.assertContains(response, "Cobrado")
        self.assertContains(response, "Saldo pendiente")
        self.assertContains(response, "Pendiente")

    def test_detalle_muestra_kpis_de_operacion(self):
        response = self.client.get(reverse("facturacion:detalle", args=[self.op.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Valor generado")
        self.assertContains(response, "Total relacionado")
        self.assertContains(response, "Abonos recibidos")
        self.assertContains(response, "Saldo por recibir")

    def test_detalle_muestra_anticipo_cuando_abono_excede(self):
        self.client.post(
            reverse("facturacion:relacion_nueva", args=[self.op.pk]),
            {"shift_ids": [str(self.shift.pk)]},
        )
        self.client.post(
            reverse("facturacion:abono", args=[self.op.pk]),
            {"valor": 500000, "fecha": "15/08/2026", "metodo": "efectivo"},
        )
        response = self.client.get(reverse("facturacion:detalle", args=[self.op.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saldo a favor / anticipo")

    def test_relacion_detalle_renderiza(self):
        self.client.post(
            reverse("facturacion:relacion_nueva", args=[self.op.pk]),
            {"shift_ids": [str(self.shift.pk)]},
        )
        url = reverse(
            "facturacion:relacion_detalle",
            args=[self.op.pk, "REL-OP-001-001"],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Turnos incluidos")
        self.assertContains(response, "ABC123")
        self.assertContains(response, "Total de la relación")
        self.assertContains(response, "Cobrado mediante FIFO")
        self.assertContains(response, "Abonos que contribuyeron a cubrirla")

    def test_relacion_detalle_muestra_tarifa_y_total_por_turno(self):
        self.client.post(
            reverse("facturacion:relacion_nueva", args=[self.op.pk]),
            {"shift_ids": [str(self.shift.pk)]},
        )
        url = reverse(
            "facturacion:relacion_detalle",
            args=[self.op.pk, "REL-OP-001-001"],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ">Tarifa<")
        self.assertContains(response, ">Total<")
        self.assertContains(response, "$35.000/h")
        self.assertContains(response, "$385.000")

    def test_lista_muestra_una_fila_por_numero_relacion(self):
        from apps.facturacion.services import crear_relacion

        for dia in range(14, 17):
            Shift.objects.create(
                operation=self.op,
                vehicle=self.vehicle,
                driver=self.driver,
                fecha_inicio=timezone.make_aware(
                    timezone.datetime(2026, 8, dia, 6, 0)
                ),
                fecha_fin=timezone.make_aware(
                    timezone.datetime(2026, 8, dia, 17, 0)
                ),
                tipo=Shift.DIA,
                meta_horas=self.op.meta_horas,
                valor_estandar=self.op.valor_turno_dia,
                estado=Shift.REALIZADO,
            )
        turnos = list(self.op.shifts.filter(estado=Shift.REALIZADO))
        crear_relacion(self.op, [s.pk for s in turnos])
        response = self.client.get(reverse("facturacion:detalle", args=[self.op.pk]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(html.count("REL-OP-001-001"), 2)

    def test_relacion_detalle_muestra_abonos_contribuyentes(self):
        self.client.post(
            reverse("facturacion:relacion_nueva", args=[self.op.pk]),
            {"shift_ids": [str(self.shift.pk)]},
        )
        self.client.post(
            reverse("facturacion:abono", args=[self.op.pk]),
            {"valor": 200000, "fecha": "15/08/2026", "metodo": "efectivo"},
        )
        url = reverse(
            "facturacion:relacion_detalle",
            args=[self.op.pk, "REL-OP-001-001"],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Monto aplicado a esta relación")
        self.assertContains(response, "$200.000")
        self.assertContains(response, "Parcial")

    def test_relacion_detalle_no_existente_404(self):
        url = reverse(
            "facturacion:relacion_detalle",
            args=[self.op.pk, "REL-OP-999-999"],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)