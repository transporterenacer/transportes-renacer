"""Seed de demostración para Transportes Renacer.

Elimina todos los datos existentes y crea datos de prueba realistas
para presentación a cliente.

Uso:
    python manage.py shell < seed_demo.py
"""
import io
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port
from apps.conductores.models import Driver
from apps.documentos.management.commands.setup_document_types import Command as DocCmd
from apps.documentos.models import DocumentType
from apps.documentos.services import cargar_documento
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.facturacion.services import crear_relacion
from apps.flota.models import Vehicle, VehicleDocument
from apps.nomina.models import Payroll, PayrollItem, DriverAdvance
from apps.nomina.services import crear_liquidacion, registrar_pago, resumen_liquidacion
from apps.operaciones.models import (
    Operation, Shift, ShiftStop, Incident, OperationVehicle,
)
from apps.operaciones.services import asignar_mulas, registrar_turno, finalizar_operacion

# ─────────────────────────────────────────────────────────────────────
# PASO 1: Eliminar todos los datos existentes (respetar FKs)
# ─────────────────────────────────────────────────────────────────────
print("Eliminando datos existentes...")
Document.objects.all().delete()
BillingRecord.objects.all().delete()
ClientPayment.objects.all().delete()
PayrollItem.objects.all().delete()
Payroll.objects.all().delete()
DriverAdvance.objects.all().delete()
Incident.objects.all().delete()
ShiftStop.objects.all().delete()
Shift.objects.all().delete()
OperationVehicle.objects.all().delete()
Operation.objects.all().delete()
VehicleDocument.objects.all().delete()
Vehicle.objects.all().delete()
Driver.objects.all().delete()
print("  Datos eliminados.")

# ─────────────────────────────────────────────────────────────────────
# PASO 2: Crear catálogos
# ─────────────────────────────────────────────────────────────────────
DocCmd().handle()

user = User.objects.get(username="admin")

generador1, _ = CargoGenerator.objects.get_or_create(
    nombre="Sociedad Portuaria de Barranquilla", nit="890100123-4"
)
generador2, _ = CargoGenerator.objects.get_or_create(
    nombre="Aguacaliente S.A.", nit="890200456-7"
)
puerto, _ = Port.objects.get_or_create(
    nombre="Puerto de Barranquilla", ciudad="Barranquilla"
)

lluvia, _ = IncidentCategory.objects.get_or_create(nombre="Lluvia")
falla_mecanica, _ = IncidentCategory.objects.get_or_create(nombre="Falla mecánica")
demora_cliente, _ = IncidentCategory.objects.get_or_create(nombre="Demora del cliente")

# ─────────────────────────────────────────────────────────────────────
# PASO 3: Crear conductores (6 conductores colombianos)
# ─────────────────────────────────────────────────────────────────────
conductores_data = [
    ("Carlos Martínez", "1023456789", "3001234567"),
    ("Ana García", "1034567890", "3012345678"),
    ("Luis Rodríguez", "1045678901", "3023456789"),
    ("Pedro Sánchez", "1056789012", "3034567890"),
    ("María López", "1067890123", "3045678901"),
    ("Juan Hernández", "1078901234", "3056789012"),
]
conductores = []
for nombre, doc, tel in conductores_data:
    d, _ = Driver.objects.get_or_create(
        documento=doc, defaults={"nombre": nombre, "telefono": tel}
    )
    conductores.append(d)
carlos, ana, luis, pedro, maria, juan = conductores

# ─────────────────────────────────────────────────────────────────────
# PASO 4: Crear vehículos (6 mulas)
# ─────────────────────────────────────────────────────────────────────
vehiculos_data = [
    ("ABC123", "Kenworth", "T880", 2020, Vehicle.EN_OPERACION),
    ("DEF456", "International", "LT625", 2021, Vehicle.EN_OPERACION),
    ("GHI789", "Freightliner", "Cascadia", 2019, Vehicle.EN_OPERACION),
    ("JKL012", "Volvo", "FH", 2022, Vehicle.DISPONIBLE),
    ("MNO345", "Scania", "R450", 2021, Vehicle.EN_TALLER),
    ("PQR678", "Kenworth", "W900", 2018, Vehicle.DISPONIBLE),
]
vehiculos = []
for placa, marca, modelo, anio, estado in vehiculos_data:
    v, _ = Vehicle.objects.get_or_create(
        placa=placa,
        defaults={"marca": marca, "modelo": modelo, "anio": anio, "estado": estado},
    )
    vehiculos.append(v)
abc, def_, ghi, jkl, mno, pqr = vehiculos

# ─────────────────────────────────────────────────────────────────────
# PASO 5: Crear operaciones
# ─────────────────────────────────────────────────────────────────────
hoy = timezone.localdate()

# Operación 1: ACTIVA - Buque MSC NAPOLI
op1, _ = Operation.objects.get_or_create(
    codigo="OP-2026-001",
    defaults=dict(
        buque="MSC NAPOLI",
        generador_de_carga=generador1,
        puerto=puerto,
        fecha_inicio=hoy - timedelta(days=7),
        estado=Operation.ACTIVA,
        meta_horas=11,
        tarifa_hora=35000,
        valor_turno_dia=180000,
        valor_turno_noche=180000,
    ),
)

# Operación 2: PROGRAMADA - Buque COSCO SHIPPING
op2, _ = Operation.objects.get_or_create(
    codigo="OP-2026-002",
    defaults=dict(
        buque="COSCO SHIPPING",
        generador_de_carga=generador2,
        puerto=puerto,
        fecha_inicio=hoy,
        estado=Operation.PROGRAMADA,
        meta_horas=11,
        tarifa_hora=38000,
        valor_turno_dia=190000,
        valor_turno_noche=190000,
    ),
)

# Operación 3: FINALIZADA - Buque MAERSK SELETAR
op3, _ = Operation.objects.get_or_create(
    codigo="OP-2026-003",
    defaults=dict(
        buque="MAERSK SELETAR",
        generador_de_carga=generador1,
        puerto=puerto,
        fecha_inicio=hoy - timedelta(days=20),
        fecha_fin_real=hoy - timedelta(days=12),
        estado=Operation.FINALIZADA,
        meta_horas=11,
        tarifa_hora=32000,
        valor_turno_dia=170000,
        valor_turno_noche=170000,
    ),
)

# Asignar mulas
asignar_mulas(op1, [abc, def_, ghi])
asignar_mulas(op2, [jkl, pqr])

# ─────────────────────────────────────────────────────────────────────
# PASO 6: Crear turnos con paradas
# ─────────────────────────────────────────────────────────────────────

# --- Operación 1 (ACTIVA): 7 turnos en los últimos 7 días ---

# Día 1 (hoy - 7): Turno día completo con parada de 1h
registrar_turno(
    operation=op1, vehicle=abc, driver=carlos,
    fecha_inicio=timezone.datetime(2026, 8, 29, 6, 0),
    fecha_fin=timezone.datetime(2026, 8, 29, 18, 0),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11,
    stops=[{
        "inicio": timezone.datetime(2026, 8, 29, 12, 0),
        "fin": timezone.datetime(2026, 8, 29, 13, 0),
    }],
)

# Día 1: Turno noche (cruza medianoche)
registrar_turno(
    operation=op1, vehicle=def_, driver=ana,
    fecha_inicio=timezone.datetime(2026, 8, 29, 18, 0),
    fecha_fin=timezone.datetime(2026, 8, 30, 6, 0),
    tipo=Shift.NOCHE, valor_estandar=180000, meta_horas=11,
)

# Día 2 (hoy - 6): Turno día con parada de 45min
registrar_turno(
    operation=op1, vehicle=ghi, driver=luis,
    fecha_inicio=timezone.datetime(2026, 8, 30, 6, 0),
    fecha_fin=timezone.datetime(2026, 8, 30, 18, 0),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11,
    stops=[{
        "inicio": timezone.datetime(2026, 8, 30, 14, 0),
        "fin": timezone.datetime(2026, 8, 30, 14, 45),
    }],
)

# Día 3 (hoy - 5): Turno día con novedad (lluvia) - turno corto
registrar_turno(
    operation=op1, vehicle=abc, driver=pedro,
    fecha_inicio=timezone.datetime(2026, 8, 31, 6, 0),
    fecha_fin=timezone.datetime(2026, 8, 31, 14, 0),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11,
    novedad_categoria=lluvia,
    novedad_descripcion="Lluvia intensa 09:00-11:00, cierre temporal de operaciones",
)

# Día 4 (hoy - 4): Turno día completo
registrar_turno(
    operation=op1, vehicle=def_, driver=maria,
    fecha_inicio=timezone.datetime(2026, 9, 1, 6, 0),
    fecha_fin=timezone.datetime(2026, 9, 1, 18, 0),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11,
)

# Día 5 (hoy - 3): Turno noche con parada de 30min
registrar_turno(
    operation=op1, vehicle=ghi, driver=juan,
    fecha_inicio=timezone.datetime(2026, 9, 1, 18, 0),
    fecha_fin=timezone.datetime(2026, 9, 2, 6, 0),
    tipo=Shift.NOCHE, valor_estandar=180000, meta_horas=11,
    stops=[{
        "inicio": timezone.datetime(2026, 9, 2, 2, 0),
        "fin": timezone.datetime(2026, 9, 2, 2, 30),
    }],
)

# Día 6 (hoy - 2): Turno día completo
registrar_turno(
    operation=op1, vehicle=abc, driver=carlos,
    fecha_inicio=timezone.datetime(2026, 9, 2, 6, 0),
    fecha_fin=timezone.datetime(2026, 9, 2, 18, 0),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11,
)

# Día 7 (hoy - 1): Turno día con novedad (falla mecánica)
registrar_turno(
    operation=op1, vehicle=def_, driver=ana,
    fecha_inicio=timezone.datetime(2026, 9, 3, 6, 0),
    fecha_fin=timezone.datetime(2026, 9, 3, 15, 0),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11,
    novedad_categoria=falla_mecanica,
    novedad_descripcion="Falla en sistema hidráulico, reparación en sitio 12:00-14:00",
    stops=[{
        "inicio": timezone.datetime(2026, 9, 3, 12, 0),
        "fin": timezone.datetime(2026, 9, 3, 14, 0),
    }],
)

# --- Operación 3 (FINALIZADA): 4 turnos ---

registrar_turno(
    operation=op3, vehicle=abc, driver=carlos,
    fecha_inicio=timezone.datetime(2026, 8, 16, 6, 0),
    fecha_fin=timezone.datetime(2026, 8, 16, 18, 0),
    tipo=Shift.DIA, valor_estandar=170000, meta_horas=11,
    stops=[{
        "inicio": timezone.datetime(2026, 8, 16, 12, 0),
        "fin": timezone.datetime(2026, 8, 16, 13, 0),
    }],
)

registrar_turno(
    operation=op3, vehicle=def_, driver=ana,
    fecha_inicio=timezone.datetime(2026, 8, 17, 6, 0),
    fecha_fin=timezone.datetime(2026, 8, 17, 18, 0),
    tipo=Shift.DIA, valor_estandar=170000, meta_horas=11,
)

registrar_turno(
    operation=op3, vehicle=ghi, driver=luis,
    fecha_inicio=timezone.datetime(2026, 8, 18, 18, 0),
    fecha_fin=timezone.datetime(2026, 8, 19, 6, 0),
    tipo=Shift.NOCHE, valor_estandar=170000, meta_horas=11,
)

registrar_turno(
    operation=op3, vehicle=abc, driver=pedro,
    fecha_inicio=timezone.datetime(2026, 8, 19, 6, 0),
    fecha_fin=timezone.datetime(2026, 8, 19, 18, 0),
    tipo=Shift.DIA, valor_estandar=170000, meta_horas=11,
    novedad_categoria=demora_cliente,
    novedad_descripcion="Demora en asignación deSlots por parte del generador",
)

# ─────────────────────────────────────────────────────────────────────
# PASO 7: Crear registros de facturación
# ─────────────────────────────────────────────────────────────────────
turnos_op1 = list(op1.shifts.filter(estado=Shift.REALIZADO).values_list("pk", flat=True)[:4])
if turnos_op1:
    crear_relacion(op1, turnos_op1, usuario=user)

# ─────────────────────────────────────────────────────────────────────
# PASO 8: Crear documentos
# ─────────────────────────────────────────────────────────────────────
soat = DocumentType.objects.get(codigo="soat")
tecno = DocumentType.objects.get(codigo="tecnomecanica")
tarjeta = DocumentType.objects.get(codigo="tarjeta_propiedad")
cedula = DocumentType.objects.get(codigo="cedula")
licencia = DocumentType.objects.get(codigo="licencia")


def subir_doc(tipo, entidad, fecha_exp, fecha_venc=None):
    contenido = b"%PDF-1.4 \n Documento de ejemplo de Transportes Renacer"
    try:
        cargar_documento(
            tipo=tipo, entidad=entidad, archivo=io.BytesIO(contenido),
            content_type="application/pdf", extension="pdf", tamano=len(contenido),
            fecha_expedicion=fecha_exp, fecha_vencimiento=fecha_venc,
            usuario=user,
        )
    except Exception as e:
        print(f"doc {tipo.codigo} {entidad}: {e}")


# ABC123: SOAT próximo (10 días), tecno vencida (-5), tarjeta registrada
subir_doc(soat, abc, hoy - timedelta(days=355), hoy + timedelta(days=10))
subir_doc(tecno, abc, hoy - timedelta(days=380), hoy - timedelta(days=5))
subir_doc(tarjeta, abc, date(2020, 3, 15))

# DEF456: SOAT vigente
subir_doc(soat, def_, hoy - timedelta(days=200), hoy + timedelta(days=160))

# GHI789: SOAT vencido
subir_doc(soat, ghi, hoy - timedelta(days=400), hoy - timedelta(days=40))

# JKL012: SOAT vigente, tecno vigente
subir_doc(soat, jkl, hoy - timedelta(days=100), hoy + timedelta(days=265))
subir_doc(tecno, jkl, hoy - timedelta(days=300), hoy + timedelta(days=65))

# PQR678: Sin documentos (en taller)

# Cédula y licencia para conductores
subir_doc(cedula, carlos, date(2015, 5, 10))
subir_doc(licencia, carlos, hoy - timedelta(days=100), hoy + timedelta(days=300))

subir_doc(cedula, ana, date(2018, 2, 20))
subir_doc(licencia, ana, hoy - timedelta(days=200), hoy + timedelta(days=200))

subir_doc(cedula, luis, date(2016, 8, 15))
subir_doc(licencia, luis, hoy - timedelta(days=50), hoy + timedelta(days=350))

subir_doc(cedula, pedro, date(2019, 11, 3))
# Pedro sin licencia (faltante)

subir_doc(cedula, maria, date(2017, 7, 25))
subir_doc(licencia, maria, hoy - timedelta(days=300), hoy + timedelta(days=100))

# Juan sin documentos (faltante total)

# ─────────────────────────────────────────────────────────────────────
# PASO 9: Crear nómina
# ─────────────────────────────────────────────────────────────────────
try:
    # Nómina de la semana del 27 ago - 2 sep 2026
    payroll = crear_liquidacion(
        date(2026, 8, 27), date(2026, 9, 2), usuario=user
    )
    # Registrar pagos parciales para algunos conductores
    for fila in resumen_liquidacion(payroll):
        if fila["pendiente"] > 0 and fila["driver"] in (carlos, ana):
            registrar_pago(
                fila["driver"], fila["pendiente"], usuario=user
            )
except Exception as e:
    print(f"nómina: {e}")

# ─────────────────────────────────────────────────────────────────────
# PASO 10: Resumen
# ─────────────────────────────────────────────────────────────────────
print("\n=== Datos de demostración listos ===")
print(f"Operaciones: {Operation.objects.count()}")
print(f"Turnos: {Shift.objects.count()}")
print(f"Paradas: {ShiftStop.objects.count()}")
print(f"Vehículos: {Vehicle.objects.count()}")
print(f"Conductores: {Driver.objects.count()}")
print(f"Documentos: {Document.objects.count()}")
print(f"Facturación: {BillingRecord.objects.count()}")
print(f"Nómina: {Payroll.objects.count()}")
