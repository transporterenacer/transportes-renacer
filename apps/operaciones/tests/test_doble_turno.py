from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift
from apps.operaciones.services import detectar_dobles_turnos


class DobleTurnoTests(TestCase):
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

    def _crear(self, driver, vehicle, inicio, fin, **kwargs):
        defaults = dict(
            operation=self.op,
            vehicle=vehicle,
            driver=driver,
            fecha_inicio=timezone.make_aware(inicio),
            fecha_fin=timezone.make_aware(fin),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )
        defaults.update(kwargs)
        return Shift.objects.create(**defaults)

    def test_descanso_insuficiente_detectado(self):
        a = self._crear(
            self.juan, self.v1,
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
        )
        b = self._crear(
            self.juan, self.v2,
            timezone.datetime(2026, 8, 10, 18, 0),
            timezone.datetime(2026, 8, 11, 5, 0),
        )
        result = detectar_dobles_turnos(driver=self.juan)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["turno_a"], a)
        self.assertEqual(result[0]["turno_b"], b)
        self.assertEqual(result[0]["tipo"], "descanso")

    def test_solape_detectado(self):
        self._crear(
            self.juan, self.v1,
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
        )
        self._crear(
            self.juan, self.v2,
            timezone.datetime(2026, 8, 10, 16, 0),
            timezone.datetime(2026, 8, 10, 20, 0),
        )
        result = detectar_dobles_turnos(driver=self.juan)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tipo"], "solape")

    def test_programado_y_realizado_con_poco_descanso_detectado(self):
        self._crear(
            self.juan, self.v1,
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
            estado=Shift.PROGRAMADO,
        )
        self._crear(
            self.juan, self.v2,
            timezone.datetime(2026, 8, 10, 18, 0),
            timezone.datetime(2026, 8, 11, 5, 0),
        )
        result = detectar_dobles_turnos(driver=self.juan)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tipo"], "descanso")

    def test_descanso_suficiente_no_detectado(self):
        self._crear(
            self.juan, self.v1,
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
        )
        self._crear(
            self.juan, self.v2,
            timezone.datetime(2026, 8, 11, 6, 0),
            timezone.datetime(2026, 8, 11, 17, 0),
        )
        self.assertEqual(detectar_dobles_turnos(driver=self.juan), [])

    def test_filtro_por_rango_de_fechas(self):
        self._crear(
            self.juan, self.v1,
            timezone.datetime(2026, 8, 1, 6, 0),
            timezone.datetime(2026, 8, 1, 17, 0),
        )
        self._crear(
            self.juan, self.v2,
            timezone.datetime(2026, 8, 1, 18, 0),
            timezone.datetime(2026, 8, 1, 23, 0),
        )
        result = detectar_dobles_turnos(
            driver=self.juan, desde=date(2026, 8, 10), hasta=date(2026, 8, 20)
        )
        self.assertEqual(result, [])
