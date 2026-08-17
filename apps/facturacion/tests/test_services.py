from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.facturacion.services import (
    agrupar_relaciones,
    aplicacion_fifo,
    crear_relacion,
    horas_pendientes_operacion,
    horas_relacionadas_operacion,
    horas_trabajadas_operacion,
    kpis_facturacion,
    saldo_operacion,
    total_abonado_operacion,
    valor_generado_operacion,
    valor_relacionado_operacion,
)
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift


class FacturacionBase(TestCase):
    def setUp(self):
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
        self.op2 = Operation.objects.create(
            codigo="OP-777",
            buque="BUQUE PACIFIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 15),
            meta_horas=11,
            tarifa_hora=30000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )

    def _shift(self, op, dia, estado=Shift.REALIZADO, inicio=6, fin=17):
        return Shift.objects.create(
            operation=op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, dia, inicio, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, dia, fin, 0)),
            tipo=Shift.DIA,
            meta_horas=op.meta_horas,
            valor_estandar=op.valor_turno_dia,
            estado=estado,
        )


class ValorGeneradoTests(FacturacionBase):
    def test_valor_generado_usa_solo_turnos_realizados(self):
        self._shift(self.op, 10)
        self._shift(self.op, 11, estado=Shift.CANCELADO)
        self.assertEqual(horas_trabajadas_operacion(self.op), 11)
        self.assertEqual(valor_generado_operacion(self.op), 385000)

    def test_valor_generado_con_fraccion_de_horas(self):
        self._shift(self.op, 10, inicio=6, fin=14)
        self.assertEqual(horas_trabajadas_operacion(self.op), 8)
        self.assertEqual(valor_generado_operacion(self.op), 280000)

    def test_valor_generado_no_depende_de_relaciones(self):
        s1 = self._shift(self.op, 10)
        s2 = self._shift(self.op, 11)
        base = valor_generado_operacion(self.op)
        crear_relacion(self.op, [s1.pk])
        crear_relacion(self.op, [s2.pk])
        self.assertEqual(valor_generado_operacion(self.op), base)
        self.assertEqual(base, 770000)


class CrearRelacionTests(FacturacionBase):
    def test_crear_relacion_marca_y_numera(self):
        s1 = self._shift(self.op, 10)
        s2 = self._shift(self.op, 11, inicio=6, fin=14)
        creados = crear_relacion(self.op, [s1.pk, s2.pk])
        self.assertEqual(len(creados), 2)
        self.assertTrue(all(br.numero_relacion == "REL-OP-001-001" for br in creados))
        self.assertEqual(
            horas_relacionadas_operacion(self.op), Decimal(19)
        )
        self.assertEqual(horas_pendientes_operacion(self.op), Decimal(0))

    def test_crear_relacion_ignora_invalidos_y_no_repite(self):
        s1 = self._shift(self.op, 10)
        crear_relacion(self.op, [s1.pk])
        s2 = self._shift(self.op, 11)
        s3 = self._shift(self.op, 12, estado=Shift.CANCELADO)
        creados = crear_relacion(self.op, [s1.pk, s2.pk, s3.pk])
        self.assertEqual(len(creados), 1)
        self.assertEqual(creados[0].numero_relacion, "REL-OP-001-002")
        self.assertEqual(self.op.billing_records.count(), 2)

    def test_crear_relacion_sin_turnos_validos_levanta_error(self):
        s1 = self._shift(self.op, 10, estado=Shift.CANCELADO)
        with self.assertRaises(ValidationError):
            crear_relacion(self.op, [s1.pk])

    def test_crear_relacion_solo_operacion_propia(self):
        s1 = self._shift(self.op, 10)
        with self.assertRaises(ValidationError):
            crear_relacion(self.op2, [s1.pk])
        self.assertEqual(self.op2.billing_records.count(), 0)
        s_ok = self._shift(self.op2, 16)
        creados = crear_relacion(self.op2, [s_ok.pk])
        self.assertEqual(creados[0].numero_relacion, "REL-OP-777-001")

    def test_numero_relacion_secuencial_por_operacion(self):
        s1 = self._shift(self.op, 10)
        s2 = self._shift(self.op2, 16)
        crear_relacion(self.op, [s1.pk])
        crear_relacion(self.op, [self._shift(self.op, 11).pk])
        crear_relacion(self.op2, [s2.pk])
        numeros = list(
            self.op.billing_records.values_list("numero_relacion", flat=True).distinct()
        )
        self.assertEqual(sorted(numeros), ["REL-OP-001-001", "REL-OP-001-002"])
        self.assertEqual(
            self.op2.billing_records.first().numero_relacion, "REL-OP-777-001"
        )

    def test_siete_turnos_forman_un_solo_paquete(self):
        turnos = [self._shift(self.op, 10 + i) for i in range(7)]
        creados = crear_relacion(self.op, [s.pk for s in turnos])
        self.assertEqual(len(creados), 7)
        self.assertEqual(
            {br.numero_relacion for br in creados}, {"REL-OP-001-001"}
        )
        self.assertEqual(
            self.op.billing_records.values_list(
                "numero_relacion", flat=True
            ).distinct().count(),
            1,
        )
        grupos = agrupar_relaciones(self.op)
        self.assertEqual(len(grupos), 1)
        paquete = grupos[0]
        self.assertEqual(paquete["numero"], "REL-OP-001-001")
        self.assertEqual(paquete["turnos"], 7)
        self.assertEqual(paquete["horas"], Decimal(77))
        self.assertEqual(paquete["valor"], 2695000)


class SaldoOperacionTests(FacturacionBase):
    def test_saldo_es_valor_generado_menos_abonado(self):
        s1 = self._shift(self.op, 10)
        crear_relacion(self.op, [s1.pk])
        ClientPayment.objects.create(operation=self.op, valor=200000)
        self.assertEqual(valor_generado_operacion(self.op), 385000)
        self.assertEqual(total_abonado_operacion(self.op), 200000)
        self.assertEqual(saldo_operacion(self.op), 185000)

    def test_saldo_no_cambia_al_relacionar(self):
        s1 = self._shift(self.op, 10)
        self.assertEqual(saldo_operacion(self.op), 385000)
        crear_relacion(self.op, [s1.pk])
        self.assertEqual(saldo_operacion(self.op), 385000)

    def test_saldo_sin_abonos(self):
        self._shift(self.op, 10)
        self.assertEqual(saldo_operacion(self.op), 385000)


class GlobalesTests(FacturacionBase):
    def test_kpis_facturacion_globales(self):
        self._shift(self.op, 10)
        self._shift(self.op2, 16, inicio=6, fin=14)
        ClientPayment.objects.create(operation=self.op, valor=50000)
        kpis = kpis_facturacion()
        self.assertEqual(kpis["valor_generado"], 385000 + 8 * 30000)
        self.assertEqual(kpis["abonos"], 50000)
        self.assertEqual(kpis["saldo"], 385000 + 240000 - 50000)
        self.assertEqual(kpis["horas_trabajadas"], 11 + 8)


class AgruparRelacionesTests(FacturacionBase):
    def test_agrupa_por_numero_con_totales(self):
        s1 = self._shift(self.op, 10)
        s2 = self._shift(self.op, 11, inicio=6, fin=14)
        s3 = self._shift(self.op, 12)
        crear_relacion(self.op, [s1.pk, s2.pk])
        crear_relacion(self.op, [s3.pk])
        grupos = agrupar_relaciones(self.op)
        self.assertEqual(len(grupos), 2)
        g1 = next(g for g in grupos if g["numero"] == "REL-OP-001-001")
        g2 = next(g for g in grupos if g["numero"] == "REL-OP-001-002")
        self.assertEqual(g1["turnos"], 2)
        self.assertEqual(g1["horas"], Decimal(19))
        self.assertEqual(g1["valor"], 665000)
        self.assertEqual(g2["turnos"], 1)
        self.assertEqual(g2["horas"], Decimal(11))
        self.assertEqual(g2["valor"], 385000)
        self.assertIsNotNone(g1["fecha"])

    def test_ignora_registros_sin_numero(self):
        s1 = self._shift(self.op, 10)
        crear_relacion(self.op, [s1.pk])
        BillingRecord.objects.filter(operation=self.op).update(numero_relacion=None)
        self.assertEqual(agrupar_relaciones(self.op), [])


class AplicacionFifoTests(FacturacionBase):
    def _paquete(self, op, numero):
        return next(p for p in aplicacion_fifo(op)["paquetes"] if p["numero"] == numero)

    def _abono(self, valor, dia=20):
        return ClientPayment.objects.create(
            operation=self.op, valor=valor, fecha=date(2026, 8, dia)
        )

    def test_fifo_cubre_primero_el_paquete_mas_antiguo(self):
        s1 = self._shift(self.op, 10)
        s2 = self._shift(self.op, 11)
        crear_relacion(self.op, [s1.pk])
        crear_relacion(self.op, [s2.pk])
        self._abono(385000)
        fifo = aplicacion_fifo(self.op)
        g1 = next(p for p in fifo["paquetes"] if p["numero"] == "REL-OP-001-001")
        g2 = next(p for p in fifo["paquetes"] if p["numero"] == "REL-OP-001-002")
        self.assertEqual(g1["estado"], "pagada")
        self.assertEqual(g1["cobrado"], 385000)
        self.assertEqual(g2["estado"], "pendiente")
        self.assertEqual(g2["cobrado"], 0)
        self.assertEqual(g2["pendiente"], 385000)

    def test_abono_corta_entre_dos_paquetes(self):
        s1 = self._shift(self.op, 10)
        s2 = self._shift(self.op, 11)
        crear_relacion(self.op, [s1.pk])
        crear_relacion(self.op, [s2.pk])
        self._abono(400000)
        g1 = self._paquete(self.op, "REL-OP-001-001")
        g2 = self._paquete(self.op, "REL-OP-001-002")
        self.assertEqual(g1["estado"], "pagada")
        self.assertEqual(g1["cobrado"], 385000)
        self.assertEqual(g2["estado"], "parcial")
        self.assertEqual(g2["cobrado"], 15000)
        self.assertEqual(g2["pendiente"], 370000)

    def test_excedente_queda_como_anticipo(self):
        s1 = self._shift(self.op, 10)
        crear_relacion(self.op, [s1.pk])
        self._abono(500000)
        fifo = aplicacion_fifo(self.op)
        self.assertEqual(fifo["anticipo"], 115000)
        g1 = self._paquete(self.op, "REL-OP-001-001")
        self.assertEqual(g1["estado"], "pagada")
        self.assertEqual(g1["pendiente"], 0)

    def test_anticipo_se_consume_en_relacion_futura(self):
        s1 = self._shift(self.op, 10)
        crear_relacion(self.op, [s1.pk])
        self._abono(500000)
        s2 = self._shift(self.op, 11)
        crear_relacion(self.op, [s2.pk])
        fifo = aplicacion_fifo(self.op)
        self.assertEqual(fifo["anticipo"], 0)
        g2 = self._paquete(self.op, "REL-OP-001-002")
        self.assertEqual(g2["cobrado"], 115000)
        self.assertEqual(g2["pendiente"], 270000)
        self.assertEqual(g2["estado"], "parcial")

    def test_estado_parcial_y_contribuciones_por_abono(self):
        s1 = self._shift(self.op, 10)
        s2 = self._shift(self.op, 11)
        crear_relacion(self.op, [s1.pk, s2.pk])
        self._abono(200000)
        self._abono(200000)
        g1 = self._paquete(self.op, "REL-OP-001-001")
        self.assertEqual(g1["estado"], "parcial")
        self.assertEqual(g1["cobrado"], 400000)
        self.assertEqual(g1["pendiente"], 370000)
        self.assertEqual(len(g1["abonos"]), 2)
        self.assertEqual(sum(e["monto"] for e in g1["abonos"]), 400000)

    def test_valor_relacionado_no_altera_globales(self):
        s1 = self._shift(self.op, 10)
        s2 = self._shift(self.op, 11)
        crear_relacion(self.op, [s1.pk, s2.pk])
        self._abono(100000)
        self.assertEqual(valor_relacionado_operacion(self.op), 770000)
        self.assertEqual(valor_generado_operacion(self.op), 770000)
        self.assertEqual(total_abonado_operacion(self.op), 100000)
        self.assertEqual(saldo_operacion(self.op), 670000)

    def test_abono_se_aplica_al_paquete_no_a_cada_turno(self):
        turnos = [self._shift(self.op, 10 + i) for i in range(7)]
        crear_relacion(self.op, [s.pk for s in turnos])
        self._abono(1000000)
        paquete = self._paquete(self.op, "REL-OP-001-001")
        self.assertEqual(paquete["valor"], 2695000)
        self.assertEqual(paquete["cobrado"], 1000000)
        self.assertEqual(paquete["pendiente"], 1695000)
        self.assertEqual(paquete["estado"], "parcial")
        self.assertEqual(len(paquete["abonos"]), 1)
        self.assertEqual(len(agrupar_relaciones(self.op)), 1)