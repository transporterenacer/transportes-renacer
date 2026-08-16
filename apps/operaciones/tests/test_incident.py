from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift
from apps.operaciones.services import cancelar_turno, registrar_turno


class IncidentTests(TestCase):
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
        self.lluvia = IncidentCategory.objects.create(nombre="Lluvia")

    def test_registrar_turno_crea_shift_realizado_sin_novedad(self):
        shift = registrar_turno(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.datetime(2026, 8, 10, 6, 0),
            fecha_fin=timezone.datetime(2026, 8, 10, 17, 0),
            tipo=Shift.DIA,
            valor_estandar=self.op.valor_turno_dia,
            meta_horas=self.op.meta_horas,
        )
        self.assertEqual(shift.estado, Shift.REALIZADO)
        self.assertEqual(shift.horas_trabajadas, 11.0)
        self.assertFalse(hasattr(shift, "incidente"))

    def test_registrar_turno_con_novedad_crea_incident(self):
        shift = registrar_turno(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.datetime(2026, 8, 10, 6, 0),
            fecha_fin=timezone.datetime(2026, 8, 10, 17, 0),
            tipo=Shift.DIA,
            valor_estandar=self.op.valor_turno_dia,
            meta_horas=self.op.meta_horas,
            novedad_categoria=self.lluvia,
            novedad_descripcion="Lluvia 09:00-10:00",
        )
        self.assertEqual(shift.incidente.categoria, self.lluvia)
        self.assertEqual(shift.incidente.descripcion, "Lluvia 09:00-10:00")

    def test_turno_corto_exige_novedad(self):
        with self.assertRaises(ValidationError):
            registrar_turno(
                operation=self.op,
                vehicle=self.vehicle,
                driver=self.driver,
                fecha_inicio=timezone.datetime(2026, 8, 10, 6, 0),
                fecha_fin=timezone.datetime(2026, 8, 10, 14, 0),
                tipo=Shift.DIA,
                valor_estandar=self.op.valor_turno_dia,
                meta_horas=self.op.meta_horas,
            )

    def test_turno_corto_con_novedad_es_valido(self):
        shift = registrar_turno(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.datetime(2026, 8, 10, 6, 0),
            fecha_fin=timezone.datetime(2026, 8, 10, 14, 0),
            tipo=Shift.DIA,
            valor_estandar=self.op.valor_turno_dia,
            meta_horas=self.op.meta_horas,
            novedad_categoria=self.lluvia,
        )
        self.assertEqual(shift.cumplimiento_pct, 72.7)

    def test_cancelar_turno_estado_y_motivo(self):
        shift = registrar_turno(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.datetime(2026, 8, 10, 6, 0),
            fecha_fin=timezone.datetime(2026, 8, 10, 17, 0),
            tipo=Shift.DIA,
            valor_estandar=self.op.valor_turno_dia,
            meta_horas=self.op.meta_horas,
        )
        cancelar_turno(shift, "Avería mecánica", usuario=None)
        shift.refresh_from_db()
        self.assertEqual(shift.estado, Shift.CANCELADO)
        self.assertEqual(shift.motivo_cancelacion, "Avería mecánica")
        self.assertEqual(shift.valor_pagado, 0)
