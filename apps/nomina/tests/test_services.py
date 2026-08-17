from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.nomina.models import DriverAdvance, Payroll, PayrollItem
from apps.nomina.services import (
    conductor_pagado,
    crear_liquidacion,
    estado_nomina,
    nomina_pendiente_actual,
    recalcular_fifo,
    registrar_abono,
    registrar_pago,
    resumen_liquidacion,
    saldo_conductor,
    semana_para,
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

    def test_crear_liquidacion_rechaza_periodo_solapado(self):
        self._shift(self.juan, self.v1, 10)
        crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        self._shift(self.juan, self.v2, 15)
        self._shift(self.juan, self.v2, 22)
        with self.assertRaises(ValidationError):
            crear_liquidacion(date(2026, 8, 14), date(2026, 8, 20))

    def test_semana_para_lunes_y_domingo(self):
        lunes, domingo = semana_para(date(2026, 8, 13))
        self.assertEqual(lunes, date(2026, 8, 10))
        self.assertEqual(domingo, date(2026, 8, 16))

    def test_resumen_liquidacion_con_cubierto_y_pendiente(self):
        self._shift(self.juan, self.v1, 10)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_abono(self.juan, 150000, descripcion="Adelanto")
        resumen = resumen_liquidacion(payroll)
        self.assertEqual(len(resumen), 1)
        fila = resumen[0]
        self.assertEqual(fila["driver"], self.juan)
        self.assertEqual(fila["total"], 180000)
        self.assertEqual(fila["cubierto"], 150000)
        self.assertEqual(fila["pendiente"], 30000)
        self.assertEqual(fila["estado"], "parcial")

    def test_resumen_liquidacion_estados_y_pagos(self):
        self._shift(self.juan, self.v1, 10)
        self._shift(self.juan, self.v2, 11)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_pago(self.juan, 360000, metodo=DriverAdvance.TRANSFERENCIA)
        resumen = resumen_liquidacion(payroll)
        fila = resumen[0]
        self.assertEqual(fila["estado"], "pagado")
        self.assertEqual(fila["cubierto"], 360000)
        self.assertEqual(fila["pendiente"], 0)
        estado = estado_nomina(payroll)
        self.assertEqual(estado["estado"], "pagado")
        self.assertEqual(estado["porcentaje"], 100)

    def test_estado_abono_parcial_y_pendiente(self):
        self._shift(self.juan, self.v1, 10)
        self._shift(self.juan, self.v2, 11)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_abono(self.juan, 100000, descripcion="Adelanto")
        resumen = resumen_liquidacion(payroll)
        self.assertEqual(resumen[0]["estado"], "parcial")
        self.assertEqual(resumen[0]["pendiente"], 260000)

    def test_estado_nomina_parcial_mixto(self):
        self._shift(self.juan, self.v1, 10)
        otro = Driver.objects.create(nombre="Ana López", documento="456")
        self._shift(otro, self.v2, 12)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_pago(self.juan, 180000)
        estado = estado_nomina(payroll)
        self.assertEqual(estado["estado"], "parcial")
        self.assertEqual(estado["conductores_pagados"], 1)

    def test_fifo_pago_parcial_cubre_turno_mas_antiguo(self):
        self._shift(self.juan, self.v1, 10)
        self._shift(self.juan, self.v2, 11)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_pago(self.juan, 200000)
        item_dia10 = payroll.items.get(shift__fecha_inicio__day=10)
        item_dia11 = payroll.items.get(shift__fecha_inicio__day=11)
        self.assertEqual(item_dia10.pagado, 180000)
        self.assertEqual(item_dia11.pagado, 20000)
        saldo = saldo_conductor(self.juan)
        self.assertEqual(saldo["saldo_pendiente"], 160000)
        self.assertEqual(saldo["turnos_cubiertos"], 1)
        self.assertEqual(saldo["turnos_pendientes"], 1)

    def test_pago_parcial_deja_pendiente_por_turno(self):
        self._shift(self.juan, self.v1, 10)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_pago(self.juan, 80000)
        item = payroll.items.first()
        self.assertEqual(item.pagado, 80000)
        saldo = saldo_conductor(self.juan)
        self.assertEqual(saldo["saldo_pendiente"], 100000)

    def test_abono_sin_tope_genera_saldo_a_favor(self):
        self._shift(self.juan, self.v1, 10)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_abono(self.juan, 300000)
        item = payroll.items.first()
        self.assertEqual(item.pagado, 180000)
        saldo = saldo_conductor(self.juan)
        self.assertEqual(saldo["saldo_pendiente"], 0)
        self.assertEqual(saldo["saldo_a_favor"], 120000)
        self.assertTrue(conductor_pagado(self.juan))

    def test_abono_suelto_se_aplica_al_liquidar(self):
        registrar_abono(self.juan, 300000)
        saldo = saldo_conductor(self.juan)
        self.assertEqual(saldo["saldo_pendiente"], 0)
        self.assertEqual(saldo["saldo_a_favor"], 300000)
        self._shift(self.juan, self.v1, 10)
        crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        item = PayrollItem.objects.first()
        self.assertEqual(item.pagado, 180000)
        saldo = saldo_conductor(self.juan)
        self.assertEqual(saldo["saldo_a_favor"], 120000)

    def test_saldo_acumulado_multiple_periodos_fifo(self):
        self._shift(self.juan, self.v1, 10)
        p1 = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        self._shift(self.juan, self.v2, 17)
        p2 = crear_liquidacion(date(2026, 8, 17), date(2026, 8, 23))
        registrar_pago(self.juan, 250000)
        item_p1 = p1.items.first()
        item_p2 = p2.items.first()
        self.assertEqual(item_p1.pagado, 180000)
        self.assertEqual(item_p2.pagado, 70000)
        saldo = saldo_conductor(self.juan)
        self.assertEqual(saldo["saldo_pendiente"], 110000)
        self.assertEqual(saldo["total_turnos"], 2)

    def test_registrar_pago_no_supera_saldo(self):
        self._shift(self.juan, self.v1, 10)
        crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_pago(self.juan, 180000)
        with self.assertRaises(ValidationError):
            registrar_pago(self.juan, 10000)

    def test_registrar_pago_con_saldo_cero_levanta_error(self):
        with self.assertRaises(ValidationError):
            registrar_pago(self.juan, 10000)

    def test_abono_despues_de_pago_total_crea_saldo_a_favor(self):
        self._shift(self.juan, self.v1, 10)
        crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_pago(self.juan, 180000)
        abono = registrar_abono(self.juan, 50000, descripcion="Adelanto siguiente semana")
        self.assertEqual(abono.tipo, DriverAdvance.ADELANTO)
        saldo = saldo_conductor(self.juan)
        self.assertEqual(saldo["saldo_pendiente"], 0)
        self.assertEqual(saldo["saldo_a_favor"], 50000)

    def test_nomina_pendiente_actual_global(self):
        self._shift(self.juan, self.v1, 10)
        crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_abono(self.juan, 80000)
        self.assertEqual(nomina_pendiente_actual(), 100000)
        registrar_pago(self.juan, 100000)
        self.assertEqual(nomina_pendiente_actual(), 0)

    def test_saldo_conductor_vacio(self):
        saldo = saldo_conductor(self.juan)
        self.assertEqual(saldo["saldo_pendiente"], 0)
        self.assertEqual(saldo["saldo_a_favor"], 0)
        self.assertEqual(saldo["total_turnos"], 0)
        self.assertEqual(saldo["estado"], "pagado")

    def test_recalcular_fifo_idempotente(self):
        self._shift(self.juan, self.v1, 10)
        self._shift(self.juan, self.v2, 11)
        crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        registrar_pago(self.juan, 200000)
        antes = [i.pagado for i in PayrollItem.objects.order_by("id")]
        recalcular_fifo(self.juan)
        despues = [i.pagado for i in PayrollItem.objects.order_by("id")]
        self.assertEqual(antes, despues)