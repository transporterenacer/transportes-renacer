from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.nomina.models import DriverAdvance, Payroll
from apps.nomina.services import crear_liquidacion, registrar_pago
from apps.operaciones.models import Operation, Shift


class NominaViewsTests(TestCase):
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
        Shift.objects.create(
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

    def test_lista_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse("nomina:lista"))
        self.assertEqual(response.status_code, 302)

    def test_crear_liquidacion_via_post(self):
        response = self.client.post(
            reverse("nomina:nueva"),
            {"periodo_inicio": "10/08/2026", "periodo_fin": "16/08/2026"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Payroll.objects.count(), 1)
        self.assertEqual(Payroll.objects.first().numero, "NOM-2026-001")

    def test_periodo_sin_turnos_no_rompe_http_500(self):
        response = self.client.post(
            reverse("nomina:nueva"),
            {"periodo_inicio": "01/09/2026", "periodo_fin": "07/09/2026"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "No hay turnos pendientes de pago en el periodo seleccionado."
        )
        self.assertEqual(Payroll.objects.count(), 0)

    def test_detalle_muestra_conductor_y_neto(self):
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        response = self.client.get(reverse("nomina:detalle", args=[payroll.pk]))
        self.assertContains(response, "Juan Pérez")
        self.assertContains(response, "NOM-2026-001")

    def test_conductor_muestra_saldo_y_turnos(self):
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        response = self.client.get(
            reverse("nomina:conductor", args=[self.driver.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ABC123")
        self.assertContains(response, "Saldo pendiente")

    def test_pago_conductor_via_post(self):
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        response = self.client.post(
            reverse("nomina:pago_nuevo", args=[self.driver.pk]),
            {"valor": 180000, "metodo": DriverAdvance.TRANSFERENCIA},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            DriverAdvance.objects.filter(
                driver=self.driver, tipo=DriverAdvance.PAGO
            ).exists()
        )
        self.assertEqual(
            DriverAdvance.objects.filter(driver=self.driver, tipo=DriverAdvance.PAGO)
            .first()
            .valor,
            180000,
        )

    def test_pago_supera_saldo_bloqueado(self):
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_pago(self.driver, 180000)
        response = self.client.post(
            reverse("nomina:pago_nuevo", args=[self.driver.pk]),
            {"valor": 180000, "metodo": DriverAdvance.EFECTIVO},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            DriverAdvance.objects.filter(driver=self.driver).count(), 1
        )

    def test_abono_conductor_via_post(self):
        response = self.client.post(
            reverse("nomina:abono_conductor_nuevo", args=[self.driver.pk]),
            {"fecha": "12/08/2026", "valor": 50000, "metodo": DriverAdvance.EFECTIVO, "descripcion": "Adelanto"},
        )
        self.assertEqual(response.status_code, 302)
        abono = DriverAdvance.objects.get(driver=self.driver)
        self.assertEqual(abono.tipo, DriverAdvance.ADELANTO)
        self.assertIsNone(abono.payroll)

    def test_abono_conductor_guarda_metodo(self):
        response = self.client.post(
            reverse("nomina:abono_conductor_nuevo", args=[self.driver.pk]),
            {
                "fecha": "12/08/2026",
                "valor": 50000,
                "metodo": DriverAdvance.TRANSFERENCIA,
                "descripcion": "Adelanto",
            },
        )
        self.assertEqual(response.status_code, 302)
        abono = DriverAdvance.objects.get(driver=self.driver)
        self.assertEqual(abono.metodo, DriverAdvance.TRANSFERENCIA)

    def test_conductor_filtro_cubiertos_y_pendientes(self):
        crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_pago(self.driver, 180000)
        cubiertos = self.client.get(
            reverse("nomina:conductor", args=[self.driver.pk]),
            {"filtro": "cubiertos"},
        )
        self.assertEqual(cubiertos.status_code, 200)
        self.assertContains(cubiertos, "ABC123")
        pendientes = self.client.get(
            reverse("nomina:conductor", args=[self.driver.pk]),
            {"filtro": "pendientes"},
        )
        self.assertContains(
            pendientes, "Sin turnos liquidados para este conductor."
        )

    def test_exportar_csv_via_get(self):
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        response = self.client.get(reverse("nomina:exportar", args=[payroll.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertContains(response, "Juan Pérez")
        self.assertContains(response, "ABC123")
        self.assertContains(response, "Cubierto")