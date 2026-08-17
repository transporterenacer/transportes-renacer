from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.nomina.models import Payroll
from apps.nomina.services import (
    crear_liquidacion,
    registrar_abono,
    registrar_pago,
)
from apps.operaciones.models import Operation, Shift


def _fecha(dia, hora):
    return timezone.make_aware(
        datetime.combine(dia, hora), timezone.get_current_timezone()
    )


def _horas(dia):
    return _fecha(dia, datetime.min.time().replace(hour=7)), _fecha(
        dia, datetime.min.time().replace(hour=18)
    )


def _noche(dia):
    return _fecha(dia, datetime.min.time().replace(hour=20)), _fecha(
        dia + timedelta(days=1), datetime.min.time().replace(hour=7)
    )


class Command(BaseCommand):
    help = "Crea datos de prueba para ejercitar el módulo de nómina."

    def handle(self, *args, **options):
        with transaction.atomic():
            self._crear_catalogos()
            flota = self._crear_flota()
            conductores = self._crear_conductores()
            operaciones = self._crear_operaciones()

            hoy = timezone.localdate()
            lunes = hoy - timedelta(days=hoy.weekday())
            lunes_prev = lunes - timedelta(days=7)
            lunes_prev2 = lunes_prev - timedelta(days=7)

            self._crear_turnos(lunes_prev2, conductores, flota, operaciones)
            self._crear_turnos(lunes_prev, conductores, flota, operaciones)
            self._crear_programados(lunes, conductores, flota, operaciones)

            self._crear_payroll(lunes_prev2)
            self._crear_payroll(lunes_prev)

            self._crear_movimientos(conductores)

        self.stdout.write(self.style.SUCCESS("Datos de prueba de nómina creados."))

    def _crear_catalogos(self):
        Port.objects.get_or_create(
            nombre="Puerto de Barranquilla", defaults={"ciudad": "Barranquilla"}
        )
        CargoGenerator.objects.get_or_create(
            nombre="Granel del Caribe S.A.S.",
            defaults={
                "nit": "901234567-8",
                "contacto": "Roberto Mesa",
                "telefono": "3001112233",
            },
        )
        CargoGenerator.objects.get_or_create(
            nombre="Agroexportaciones del Norte Ltda.",
            defaults={
                "nit": "890112233-4",
                "contacto": "Luz Dary Páez",
                "telefono": "3004455667",
            },
        )

    def _crear_flota(self):
        datos = [
            ("ABC123", "Kenworth", "T800", 2019),
            ("DEF456", "International", "ProStar", 2020),
            ("GHI789", "Freightliner", "Cascadia", 2021),
            ("JKL012", "Volvo", "FH16", 2022),
        ]
        flota = {}
        for placa, marca, modelo, anio in datos:
            v, _ = Vehicle.objects.get_or_create(
                placa=placa,
                defaults={
                    "marca": marca,
                    "modelo": modelo,
                    "anio": anio,
                    "estado": Vehicle.DISPONIBLE,
                },
            )
            flota[placa] = v
        return flota

    def _crear_conductores(self):
        datos = [
            ("Juan Pérez", "123456789"),
            ("María Gómez", "987654321"),
            ("Carlos Ríos", "555666777"),
            ("Pedro Torres", "111222333"),
            ("Ana Martínez", "444555666"),
            ("Luis Morales", "777888999"),
        ]
        conductores = {}
        for nombre, documento in datos:
            d, _ = Driver.objects.get_or_create(
                documento=documento,
                defaults={"nombre": nombre, "estado": Driver.DISPONIBLE},
            )
            conductores[nombre] = d
        return conductores

    def _crear_operaciones(self):
        puerto = Port.objects.get(nombre="Puerto de Barranquilla")
        gen1 = CargoGenerator.objects.get(nombre="Granel del Caribe S.A.S.")
        gen2 = CargoGenerator.objects.get(nombre="Agroexportaciones del Norte Ltda.")
        hoy = timezone.localdate()
        datos = [
            ("OP-000", "BUQUE MAR CARIBE", gen2, 32000, 170000, 170000, hoy - timedelta(days=21), Operation.FINALIZADA),
            ("OP-001", "BUQUE ATLANTIC", gen1, 35000, 180000, 180000, hoy - timedelta(days=14), Operation.ACTIVA),
            ("OP-002", "BUQUE ORINOCO", gen2, 38000, 190000, 195000, hoy - timedelta(days=7), Operation.ACTIVA),
        ]
        operaciones = {}
        for codigo, buque, gen, tarifa, dia, noche, f_ini, estado in datos:
            op, _ = Operation.objects.get_or_create(
                codigo=codigo,
                defaults={
                    "buque": buque,
                    "generador_de_carga": gen,
                    "puerto": puerto,
                    "fecha_inicio": f_ini,
                    "estado": estado,
                    "tarifa_hora": tarifa,
                    "valor_turno_dia": dia,
                    "valor_turno_noche": noche,
                },
            )
            operaciones[codigo] = op
        return operaciones

    def _crear_turno(self, op, placa, conductor, dia, tipo, estado):
        inicio, fin = _horas(dia) if tipo == Shift.DIA else _noche(dia)
        if Shift.objects.filter(driver=conductor, fecha_inicio=inicio).exists():
            return None
        valor = op.valor_turno_dia if tipo == Shift.DIA else op.valor_turno_noche
        return Shift.objects.create(
            operation=op,
            vehicle=placa,
            driver=conductor,
            fecha_inicio=inicio,
            fecha_fin=fin,
            meta_horas=op.meta_horas,
            tipo=tipo,
            valor_estandar=valor,
            estado=estado,
        )

    def _crear_turnos(self, lunes, conductores, flota, operaciones):
        dias = {i: lunes + timedelta(days=i) for i in range(7)}
        v = lambda p: flota[p]
        d = lambda n: conductores[n]
        plan = [
            (operaciones["OP-000"], v("ABC123"), d("Juan Pérez"), dias[0], Shift.DIA),
            (operaciones["OP-000"], v("DEF456"), d("María Gómez"), dias[1], Shift.DIA),
            (operaciones["OP-001"], v("GHI789"), d("Carlos Ríos"), dias[2], Shift.DIA),
            (operaciones["OP-001"], v("JKL012"), d("Pedro Torres"), dias[4], Shift.DIA),
            (operaciones["OP-001"], v("ABC123"), d("Ana Martínez"), dias[5], Shift.NOCHE),
            (operaciones["OP-002"], v("DEF456"), d("Luis Morales"), dias[6], Shift.DIA),
            (operaciones["OP-001"], v("ABC123"), d("Juan Pérez"), dias[0], Shift.NOCHE),
            (operaciones["OP-001"], v("DEF456"), d("María Gómez"), dias[1], Shift.NOCHE),
            (operaciones["OP-000"], v("GHI789"), d("Carlos Ríos"), dias[2], Shift.DIA),
            (operaciones["OP-002"], v("JKL012"), d("Pedro Torres"), dias[4], Shift.NOCHE),
            (operaciones["OP-002"], v("ABC123"), d("Ana Martínez"), dias[5], Shift.NOCHE),
            (operaciones["OP-000"], v("DEF456"), d("Juan Pérez"), dias[6], Shift.DIA),
        ]
        for op, vehicle, conductor, dia, tipo in plan:
            self._crear_turno(op, vehicle, conductor, dia, tipo, Shift.REALIZADO)

    def _crear_programados(self, lunes, conductores, flota, operaciones):
        dias = {i: lunes + timedelta(days=i) for i in range(7)}
        plan = [
            (operaciones["OP-002"], flota["JKL012"], conductores["Pedro Torres"], dias[6], Shift.DIA),
            (operaciones["OP-001"], flota["ABC123"], conductores["Ana Martínez"], dias[6] + timedelta(days=1), Shift.NOCHE),
            (operaciones["OP-000"], flota["DEF456"], conductores["Luis Morales"], dias[6] + timedelta(days=2), Shift.DIA),
        ]
        for op, vehicle, conductor, dia, tipo in plan:
            self._crear_turno(op, vehicle, conductor, dia, tipo, Shift.PROGRAMADO)

    def _crear_payroll(self, lunes):
        domingo = lunes + timedelta(days=6)
        if Payroll.objects.filter(periodo_inicio=lunes, periodo_fin=domingo).exists():
            self.stdout.write(f"  Ya existe liquidación para {lunes}–{domingo}, se omite.")
            return
        payroll = crear_liquidacion(lunes, domingo)
        self.stdout.write(
            f"  Liquidación {payroll.numero} ({lunes}–{domingo}) "
            f"${payroll.total:,.0f} — {payroll.items.count()} turnos"
        )

    def _crear_movimientos(self, conductores):
        pedro = conductores["Pedro Torres"]
        ana = conductores["Ana Martínez"]
        registrar_abono(
            pedro,
            Decimal(250000),
            "Adelanto quincena",
            fecha=self._fecha(-12),
        )
        registrar_pago(pedro, Decimal(125000), metodo="transferencia")
        registrar_abono(
            ana,
            Decimal(100000),
            "Adelanto combustible",
            fecha=self._fecha(-10),
        )
        registrar_pago(ana, Decimal(80000), metodo="efectivo")
        self.stdout.write("  Abonos y pagos de prueba registrados.")

    def _fecha(self, dias):
        return timezone.localdate() + timedelta(days=dias)
