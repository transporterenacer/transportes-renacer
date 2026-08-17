from datetime import date

from django.test import TestCase

from apps.catalogos.models import CargoGenerator, Port
from apps.flota.forms import VehicleForm
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation
from apps.operaciones.services import asignar_mulas


class VehicleFormTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.v1 = Vehicle.objects.create(placa="ABC123")
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

    def test_estado_en_taller_rechazado_si_operacion_activa(self):
        asignar_mulas(self.op, [self.v1])
        form = VehicleForm(
            data={
                "placa": "ABC123",
                "marca": "",
                "modelo": "",
                "anio": "",
                "estado": Vehicle.EN_TALLER,
                "observaciones": "",
            },
            instance=self.v1,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("estado", form.errors)

    def test_estado_fuera_de_servicio_rechazado_si_operacion_activa(self):
        asignar_mulas(self.op, [self.v1])
        form = VehicleForm(
            data={
                "placa": "ABC123",
                "marca": "",
                "modelo": "",
                "anio": "",
                "estado": Vehicle.FUERA_DE_SERVICIO,
                "observaciones": "",
            },
            instance=self.v1,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("estado", form.errors)

    def test_estado_en_taller_permitido_sin_operacion(self):
        form = VehicleForm(
            data={
                "placa": "ABC123",
                "marca": "",
                "modelo": "",
                "anio": "",
                "estado": Vehicle.EN_TALLER,
                "observaciones": "",
            },
            instance=self.v1,
        )
        self.assertTrue(form.is_valid())

    def test_estado_disponible_permitido_si_operacion_activa(self):
        asignar_mulas(self.op, [self.v1])
        form = VehicleForm(
            data={
                "placa": "ABC123",
                "marca": "",
                "modelo": "",
                "anio": "",
                "estado": Vehicle.DISPONIBLE,
                "observaciones": "",
            },
            instance=self.v1,
        )
        self.assertTrue(form.is_valid())

    def test_asignar_mulas_antes_no_deberia_bloquear_form_crear(self):
        form = VehicleForm(
            data={
                "placa": "XYZ789",
                "marca": "",
                "modelo": "",
                "anio": "",
                "estado": Vehicle.DISPONIBLE,
                "observaciones": "",
            }
        )
        self.assertTrue(form.is_valid())