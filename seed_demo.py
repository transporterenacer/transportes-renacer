"""Seed de demostración para Transportes Renacer.

Elimina todos los datos existentes y crea datos de prueba realistas
para presentación a cliente.

Uso:
    python manage.py shell < seed_demo.py
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port, Proveedor
from apps.conductores.models import Driver
from apps.documentos.management.commands.setup_document_types import Command as DocCmd
from apps.documentos.models import Document
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.facturacion.services import crear_relacion
from apps.flota.models import Vehicle, VehicleDocument
from apps.nomina.models import Payroll, PayrollItem, DriverAdvance
from apps.nomina.services import crear_liquidacion, registrar_pago, resumen_liquidacion
from apps.operaciones.models import (
    Operation, Shift, ShiftStop, Incident, OperationVehicle, OperationExpense, Viaje,
)
from apps.operaciones.services import (
    asignar_mulas, registrar_turno, finalizar_operacion,
    crear_viaje, iniciar_viaje, finalizar_viaje,
)

# ─────────────────────────────────────────────────────────────────────
# PASO 1: Eliminar todos los datos existentes (respetar FKs)
# ─────────────────────────────────────────────────────────────────────
print("Eliminando datos existentes...")
PayrollItem.objects.filter(viaje__isnull=False).delete()
OperationExpense.objects.filter(viaje__isnull=False).delete()
BillingRecord.objects.filter(viaje__isnull=False).delete()
Viaje.objects.all().delete()
OperationExpense.objects.all().delete()
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
Proveedor.objects.all().delete()
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
asignar_mulas(op3, [abc, def_, ghi])

# ─────────────────────────────────────────────────────────────────────
# PASO 6: Crear turnos con paradas (fechas relativas a hoy)
# ─────────────────────────────────────────────────────────────────────

def dt(dias_atras, hora, minuto=0):
    base = hoy - timedelta(days=dias_atras)
    return timezone.datetime(base.year, base.month, base.day, hora, minuto)


# --- Operación 1 (ACTIVA): 7 turnos en los últimos 7 días ---

# Día 1 (hoy - 7): Turno día completo con parada de 1h
registrar_turno(
    operation=op1, vehicle=abc, driver=carlos,
    fecha_inicio=dt(7, 6), fecha_fin=dt(7, 18),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11,
    stops=[{
        "inicio": dt(7, 12),
        "fin": dt(7, 13),
    }],
)

# Día 1: Turno noche (cruza medianoche)
registrar_turno(
    operation=op1, vehicle=def_, driver=ana,
    fecha_inicio=dt(7, 18), fecha_fin=dt(6, 6),
    tipo=Shift.NOCHE, valor_estandar=180000, meta_horas=11,
)

# Día 2 (hoy - 6): Turno día con parada de 45min
registrar_turno(
    operation=op1, vehicle=ghi, driver=luis,
    fecha_inicio=dt(6, 6), fecha_fin=dt(6, 18),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11,
    stops=[{
        "inicio": dt(6, 14),
        "fin": dt(6, 14, 45),
    }],
)

# Día 3 (hoy - 5): Turno día con novedad (lluvia) - turno corto
registrar_turno(
    operation=op1, vehicle=abc, driver=pedro,
    fecha_inicio=dt(5, 6), fecha_fin=dt(5, 14),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11,
    novedad_categoria=lluvia,
    novedad_descripcion="Lluvia intensa 09:00-11:00, cierre temporal de operaciones",
)

# Día 4 (hoy - 4): Turno día completo
registrar_turno(
    operation=op1, vehicle=def_, driver=maria,
    fecha_inicio=dt(4, 6), fecha_fin=dt(4, 18),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11,
)

# Día 5 (hoy - 3): Turno noche con parada de 30min
registrar_turno(
    operation=op1, vehicle=ghi, driver=juan,
    fecha_inicio=dt(3, 18), fecha_fin=dt(2, 6),
    tipo=Shift.NOCHE, valor_estandar=180000, meta_horas=11,
    stops=[{
        "inicio": dt(2, 2),
        "fin": dt(2, 2, 30),
    }],
)

# Día 6 (hoy - 2): Turno día completo
registrar_turno(
    operation=op1, vehicle=abc, driver=carlos,
    fecha_inicio=dt(2, 6), fecha_fin=dt(2, 18),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11,
)

# Día 7 (hoy - 1): Turno día con novedad (falla mecánica)
registrar_turno(
    operation=op1, vehicle=def_, driver=ana,
    fecha_inicio=dt(1, 6), fecha_fin=dt(1, 15),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11,
    novedad_categoria=falla_mecanica,
    novedad_descripcion="Falla en sistema hidráulico, reparación en sitio 12:00-14:00",
    stops=[{
        "inicio": dt(1, 12),
        "fin": dt(1, 14),
    }],
)

# --- Operación 3 (FINALIZADA): 4 turnos entre hoy-20 y hoy-17 ---

registrar_turno(
    operation=op3, vehicle=abc, driver=carlos,
    fecha_inicio=dt(20, 6), fecha_fin=dt(20, 18),
    tipo=Shift.DIA, valor_estandar=170000, meta_horas=11,
    stops=[{
        "inicio": dt(20, 12),
        "fin": dt(20, 13),
    }],
)

registrar_turno(
    operation=op3, vehicle=def_, driver=ana,
    fecha_inicio=dt(19, 6), fecha_fin=dt(19, 18),
    tipo=Shift.DIA, valor_estandar=170000, meta_horas=11,
)

registrar_turno(
    operation=op3, vehicle=ghi, driver=luis,
    fecha_inicio=dt(18, 18), fecha_fin=dt(17, 6),
    tipo=Shift.NOCHE, valor_estandar=170000, meta_horas=11,
)

registrar_turno(
    operation=op3, vehicle=abc, driver=pedro,
    fecha_inicio=dt(17, 6), fecha_fin=dt(17, 18),
    tipo=Shift.DIA, valor_estandar=170000, meta_horas=11,
    novedad_categoria=demora_cliente,
    novedad_descripcion="Demora en asignación de Slots por parte del generador",
)

# ─────────────────────────────────────────────────────────────────────
# PASO 7: Crear registros de facturación
# ─────────────────────────────────────────────────────────────────────
turnos_op1 = list(op1.shifts.filter(estado=Shift.REALIZADO).values_list("pk", flat=True)[:4])
if turnos_op1:
    crear_relacion(op1, turnos_op1, usuario=user)

# ─────────────────────────────────────────────────────────────────────
# PASO 8: Crear nómina
# ─────────────────────────────────────────────────────────────────────
try:
    # Nómina de la semana pasada
    payroll = crear_liquidacion(
        hoy - timedelta(days=7), hoy - timedelta(days=1), usuario=user
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
# PASO 10: Crear proveedores
# ─────────────────────────────────────────────────────────────────────
proveedor_acpm, _ = Proveedor.objects.get_or_create(
    nombre="Estación de Servicio Portuario", nit="900123456-1",
    defaults={"contacto": "Carlos Vargas", "telefono": "3001112233"}
)
proveedor_repuestos, _ = Proveedor.objects.get_or_create(
    nombre="Repuestos Diesel S.A.S", nit="900567890-2",
    defaults={"contacto": "María López", "telefono": "3002223344"}
)
proveedor_llantas, _ = Proveedor.objects.get_or_create(
    nombre="Llantería Portual", nit="900987654-3",
    defaults={"contacto": "Pedro Sánchez", "telefono": "3003334455"}
)
proveedor_mantenimiento, _ = Proveedor.objects.get_or_create(
    nombre="Taller Mecánico del Norte", nit="900456789-4",
    defaults={"contacto": "Luis Rodríguez", "telefono": "3004445566"}
)

# ─────────────────────────────────────────────────────────────────────
# PASO 11: Crear gastos de operación
# ─────────────────────────────────────────────────────────────────────
# Operación 1: 5 gastos
OperationExpense.objects.create(
    operation=op1, vehicle=abc, proveedor=proveedor_acpm,
    categoria=OperationExpense.COMBUSTIBLE, fecha=hoy - timedelta(days=6),
    valor=450000, galones=120, numero_factura="FAC-001234",
    descripcion="ACPM para operación MSC NAPOLI",
)
OperationExpense.objects.create(
    operation=op1, vehicle=def_, proveedor=proveedor_acpm,
    categoria=OperationExpense.COMBUSTIBLE, fecha=hoy - timedelta(days=5),
    valor=380000, galones=100, numero_factura="FAC-001235",
)
OperationExpense.objects.create(
    operation=op1, vehicle=abc, proveedor=proveedor_repuestos,
    categoria=OperationExpense.REPUESTO, fecha=hoy - timedelta(days=4),
    valor=280000, descripcion="Filtro de aceite + filtro de aire",
    numero_factura="FAC-001236",
)
OperationExpense.objects.create(
    operation=op1, vehicle=ghi, proveedor=proveedor_llantas,
    categoria=OperationExpense.LLANTA, fecha=hoy - timedelta(days=3),
    valor=650000, descripcion="2 llantas 11R22.5 para Freightliner",
    numero_factura="FAC-001237",
)
OperationExpense.objects.create(
    operation=op1, vehicle=def_, proveedor=proveedor_mantenimiento,
    categoria=OperationExpense.MANTENIMIENTO, fecha=hoy - timedelta(days=2),
    valor=180000, descripcion="Cambio de aceite y revisión general",
    numero_factura="FAC-001238",
)

# Operación 3 (finalizada): 3 gastos
OperationExpense.objects.create(
    operation=op3, vehicle=abc, proveedor=proveedor_acpm,
    categoria=OperationExpense.COMBUSTIBLE, fecha=hoy - timedelta(days=18),
    valor=520000, galones=140, numero_factura="FAC-002001",
)
OperationExpense.objects.create(
    operation=op3, vehicle=def_, proveedor=proveedor_repuestos,
    categoria=OperationExpense.REPUESTO, fecha=hoy - timedelta(days=16),
    valor=95000, descripcion="Bombilla de freno delantera",
    numero_factura="FAC-002002",
)
OperationExpense.objects.create(
    operation=op3, vehicle=ghi, proveedor=None,
    categoria=OperationExpense.PEAJE, fecha=hoy - timedelta(days=15),
    valor=35000, descripcion="Peaje vía al puerto",
)

# ─────────────────────────────────────────────────────────────────────
# PASO 11b: Crear viajes locales de ejemplo
# ─────────────────────────────────────────────────────────────────────

def dt_viaje(fecha, hora, minuto=0):
    return timezone.make_aware(timezone.datetime(fecha.year, fecha.month, fecha.day, hora, minuto))

# Viaje 1: FINALIZADO (hace ~10 días) con gastos
viaje1 = crear_viaje(
    cliente=generador1, vehicle=jkl, driver=maria,
    origen="Barranquilla", destino="Cartagena",
    fecha_ida=dt_viaje(hoy - timedelta(days=10), 6),
    fecha_vuelta=dt_viaje(hoy - timedelta(days=10), 16),
    valor_cobrado=Decimal("1200000"), valor_conductor=Decimal("600000"),
    usuario=user,
)
iniciar_viaje(viaje1, usuario=user)
finalizar_viaje(viaje1, usuario=user)
OperationExpense.objects.create(
    viaje=viaje1, vehicle=jkl, proveedor=proveedor_acpm,
    categoria=OperationExpense.COMBUSTIBLE, fecha=hoy - timedelta(days=10),
    valor=Decimal("380000"), galones=Decimal("100"), numero_factura="FV-001",
)
OperationExpense.objects.create(
    viaje=viaje1, vehicle=jkl,
    categoria=OperationExpense.PEAJE, fecha=hoy - timedelta(days=10),
    valor=Decimal("70000"), descripcion="Peaje Barranquilla-Cartagena",
)

# Viaje 2: EN_VIAJE (iniciado hace 2 días)
viaje2 = crear_viaje(
    cliente=generador2, vehicle=pqr, driver=juan,
    origen="Barranquilla", destino="Santa Marta",
    fecha_ida=dt_viaje(hoy - timedelta(days=2), 5),
    fecha_vuelta=dt_viaje(hoy - timedelta(days=2), 18),
    valor_cobrado=Decimal("1500000"), valor_conductor=Decimal("750000"),
    usuario=user,
)
iniciar_viaje(viaje2, usuario=user)

# Viaje 3: PENDIENTE (sale mañana)
crear_viaje(
    cliente=generador1, vehicle=jkl, driver=luis,
    origen="Cartagena", destino="Barranquilla",
    fecha_ida=dt_viaje(hoy + timedelta(days=1), 7),
    fecha_vuelta=dt_viaje(hoy + timedelta(days=1), 17),
    valor_cobrado=Decimal("1100000"), valor_conductor=Decimal("550000"),
    usuario=user,
)

# ─────────────────────────────────────────────────────────────────────
# PASO 12: Resumen
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
print(f"Proveedores: {Proveedor.objects.count()}")
print(f"Gastos: {OperationExpense.objects.count()}")
print(f"Viajes locales: {Viaje.objects.count()}")
