"""Borra los datos de demo de Transportes Renacer.

Deja el sistema base (usuarios, grupos, catálogos, tipos documentales)
y elimina solo los datos de negocio de la demo:
operaciones, turnos, flota, conductores, facturación, nómina, documentos
y gastos.

Uso:
    python manage.py shell < clear_demo.py
"""

from apps.catalogos.models import Proveedor
from apps.conductores.models import Driver
from apps.documentos.models import Document
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.flota.models import Vehicle, VehicleDocument
from apps.nomina.models import DriverAdvance, Payroll, PayrollItem
from apps.operaciones.models import (
    Incident,
    Operation,
    OperationExpense,
    OperationVehicle,
    Shift,
    ShiftStop,
    Viaje,
)

print("Eliminando datos de demo...")
OperationExpense.objects.filter(viaje__isnull=False).delete()
BillingRecord.objects.filter(viaje__isnull=False).delete()
PayrollItem.objects.filter(viaje__isnull=False).delete()
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
print("Datos de demo eliminados. Sistema base intacto.")
