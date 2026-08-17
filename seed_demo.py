import io
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port
from apps.conductores.models import Driver
from apps.documentos.management.commands.setup_document_types import Command as DocCmd
from apps.documentos.models import DocumentType
from apps.documentos.services import cargar_documento
from apps.facturacion.services import generar_billing_operacion
from apps.flota.models import Vehicle
from apps.nomina.services import crear_liquidacion, registrar_pago, resumen_liquidacion
from apps.operaciones.models import Operation, Shift
from apps.operaciones.services import asignar_mulas, registrar_turno, finalizar_operacion

DocCmd().handle()

user = User.objects.get(username="admin")
generador, _ = CargoGenerator.objects.get_or_create(nombre="Sociedad Portuaria de Barranquilla", nit="890100123-4")
puerto, _ = Port.objects.get_or_create(nombre="Sociedad Portuaria Regional", ciudad="Barranquilla")

def ensure_driver(nombre, doc, tel):
    d, _ = Driver.objects.get_or_create(documento=doc, defaults={"nombre": nombre, "telefono": tel})
    return d

def ensure_vehicle(placa, marca, modelo, anio):
    v, _ = Vehicle.objects.get_or_create(placa=placa, defaults={"marca": marca, "modelo": modelo, "anio": anio})
    return v

juan = ensure_driver("Juan Pérez", "123456789", "3001112233")
maria = ensure_driver("María Gómez", "987654321", "3004445566")
carlos = ensure_driver("Carlos Ríos", "555666777", "3007778899")

abc = ensure_vehicle("ABC123", "Kenworth", "T880", 2020)
def_ = ensure_vehicle("DEF456", "International", "LT625", 2021)
ghi = ensure_vehicle("GHI789", "Freightliner", "Cascadia", 2019)
jkl = ensure_vehicle("JKL012", "Volvo", "FH", 2022)

# Operación activa BUQUE ATLANTIC
op1, _ = Operation.objects.get_or_create(
    codigo="OP-001",
    defaults=dict(
        buque="BUQUE ATLANTIC",
        generador_de_carga=generador,
        puerto=puerto,
        fecha_inicio=date(2026, 8, 10),
        fecha_fin_estimada=date(2026, 8, 18),
        estado=Operation.ACTIVA,
        meta_horas=11,
        tarifa_hora=35000,
        valor_turno_dia=180000,
        valor_turno_noche=180000,
    ),
)
if op1.estado != Operation.ACTIVA:
    op1.estado = Operation.ACTIVA
    op1.save()

asignar_mulas(op1, [abc, def_, ghi])

# Turnos del dia 10 y 11
registrar_turno(operation=op1, vehicle=abc, driver=juan,
    fecha_inicio=timezone.datetime(2026, 8, 10, 6, 0), fecha_fin=timezone.datetime(2026, 8, 10, 17, 0),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11)
registrar_turno(operation=op1, vehicle=def_, driver=maria,
    fecha_inicio=timezone.datetime(2026, 8, 10, 6, 0), fecha_fin=timezone.datetime(2026, 8, 10, 17, 0),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11)
# Nocturno que cruza medianoche
registrar_turno(operation=op1, vehicle=abc, driver=carlos,
    fecha_inicio=timezone.datetime(2026, 8, 10, 18, 0), fecha_fin=timezone.datetime(2026, 8, 11, 6, 0),
    tipo=Shift.NOCHE, valor_estandar=180000, meta_horas=11)

# Turno corto con novedad (lluvia) el dia 11
lluvia, _ = IncidentCategory.objects.get_or_create(nombre="Lluvia")
registrar_turno(operation=op1, vehicle=ghi, driver=juan,
    fecha_inicio=timezone.datetime(2026, 8, 11, 6, 0), fecha_fin=timezone.datetime(2026, 8, 11, 14, 0),
    tipo=Shift.DIA, valor_estandar=180000, meta_horas=11,
    novedad_categoria=lluvia, novedad_descripcion="Lluvia intensa 09:00-11:00")

# Operación finalizada para historial
op2, _ = Operation.objects.get_or_create(
    codigo="OP-000",
    defaults=dict(
        buque="BUQUE MAR CARIBE",
        generador_de_carga=generador,
        puerto=puerto,
        fecha_inicio=date(2026, 7, 1),
        fecha_fin_real=date(2026, 7, 5),
        estado=Operation.FINALIZADA,
        meta_horas=11,
        tarifa_hora=32000,
        valor_turno_dia=170000,
        valor_turno_noche=170000,
    ),
)
if op2.estado != Operation.FINALIZADA:
    op2.estado = Operation.FINALIZADA
    op2.fecha_fin_real = date(2026, 7, 5)
    op2.save()

# Nómina de la semana
try:
    payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16), usuario=user)
    for fila in resumen_liquidacion(payroll):
        if fila["pendiente"] > 0:
            registrar_pago(fila["driver"], fila["pendiente"], usuario=user)
except Exception as e:
    print("nomina:", e)

# Facturación de la operación activa
generar_billing_operacion(op1, usuario=user)

# Documentos de ejemplo (Storage local)
hoy = timezone.localdate()
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
        print(f"doc {tipo.codigo} {entidad}:", e)

# ABC123: SOAT proximo (10 dias), tecno vencida (-5), tarjeta registrada
subir_doc(soat, abc, hoy - timedelta(days=355), hoy + timedelta(days=10))
subir_doc(tecno, abc, hoy - timedelta(days=380), hoy - timedelta(days=5))
subir_doc(tarjeta, abc, date(2020, 3, 15))
# DEF456: SOAT vigente
subir_doc(soat, def_, hoy - timedelta(days=200), hoy + timedelta(days=160))
# GHI789: SOAT vencido
subir_doc(soat, ghi, hoy - timedelta(days=400), hoy - timedelta(days=40))

# Juan: cedula + licencia vigente; Maria: cedula; Carlos: nada (faltantes)
subir_doc(cedula, juan, date(2015, 5, 10))
subir_doc(licencia, juan, hoy - timedelta(days=100), hoy + timedelta(days=300))
subir_doc(cedula, maria, date(2018, 2, 20))

print("Datos de demostración listos.")
print(f"vehiculos: {Vehicle.objects.count()}, conductores: {Driver.objects.count()}, operaciones: {Operation.objects.count()}")
