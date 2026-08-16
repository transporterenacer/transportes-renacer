from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.nomina.models import DriverAdvance, Payroll
from apps.nomina.services import (
    crear_liquidacion,
    marcar_pagada,
    resumen_liquidacion,
    turnos_pendientes_pago,
)
from apps.operaciones.models import Operation, Shift


class NominaServicesTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.v1 = Vehicle.objects.create(placa="ABC123")
        self.v2 = Vehicle.objects.create(placa="DEF456")
        self.juan = Driver.objects.create(nombre="Juan Pérez", documento="123")
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

    def _shift(self, driver, vehicle, dia, estado=Shift.REALIZADO, tipo=Shift.DIA):
        return Shift.objects.create(
            operation=self.op,
            vehicle=vehicle,
            driver=driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, dia, 6, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, dia, 17, 0)),
            tipo=tipo,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia if tipo == Shift.DIA else self.op.valor_turno_noche,
            estado=estado,
        )

    def test_turnos_pendientes_filtra_estado_y_periodo(self):
        s1 = self._shift(self.juan, self.v1, 10)
        self._shift(self.juan, self.v2, 20, estado=Shift.REALIZADO)
        self._shift(self.juan, self.v1, 11, estado=Shift.CANCELADO)
        pendientes = turnos_pendientes_pago(date(2026, 8, 10), date(2026, 8, 16))
        self.assertEqual(list(pendientes), [s1])

    def test_turnos_pendientes_excluye_ya_liquidados(self):
        self._shift(self.juan, self.v1, 10)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        self.assertEqual(payroll.items.count(), 1)
        self.assertEqual(list(turnos_pendientes_pago(date(2026, 8, 10), date(2026, 8, 16))), [])

    def test_crear_liquidacion_numero_y_total(self):
        self._shift(self.juan, self.v1, 10)
        self._shift(self.juan, self.v2, 11)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        self.assertEqual(payroll.numero, "NOM-2026-001")
        self.assertEqual(payroll.estado, Payroll.LIQUIDADO)
        self.assertEqual(payroll.total, 360000)
        self.assertEqual(payroll.items.count(), 2)

    def test_crear_liquidacion_sin_turnos_levanta_error(self):
        with self.assertRaises(ValidationError):
            crear_liquidacion(date(2026, 9, 1), date(2026, 9, 7))

    def test_resumen_liquidacion_con_abonos(self):
        self._shift(self.juan, self.v1, 10)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        DriverAdvance.objects.create(driver=self.juan, valor=150000, payroll=payroll)
        resumen = resumen_liquidacion(payroll)
        self.assertEqual(len(resumen), 1)
        fila = resumen[0]
        self.assertEqual(fila["driver"], self.juan)
        self.assertEqual(fila["total"], 180000)
        self.assertEqual(fila["abonos"], 150000)
        self.assertEqual(fila["neto"], 30000)

    def test_marcar_pagada(self):
        self._shift(self.juan, self.v1, 10)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        marcar_pagada(payroll)
        payroll.refresh_from_db()
        self.assertEqual(payroll.estado, Payroll.PAGADO)
        self.assertEqual(payroll.fecha_pago, timezone.localdate())
