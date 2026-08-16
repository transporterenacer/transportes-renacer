from django.utils import timezone

from apps.flota.models import Vehicle
from apps.operaciones.models import OperationVehicle


def mulas_disponibles():
    return Vehicle.objects.filter(estado=Vehicle.DISPONIBLE)


def asignar_mulas(operation, vehicles):
    for vehicle in vehicles:
        relation, _ = operation.mulas.get_or_create(vehicle=vehicle)
        relation.activa = True
        relation.fecha_asignacion = timezone.localdate()
        relation.save()
        vehicle.estado = Vehicle.EN_OPERACION
        vehicle.save(update_fields=["estado"])


def liberar_mulas(operation):
    for relation in operation.mulas.filter(activa=True):
        relation.activa = False
        relation.save(update_fields=["activa"])
        en_otra_activa = OperationVehicle.objects.filter(
            vehicle=relation.vehicle, activa=True
        ).exclude(operation=operation).exists()
        if not en_otra_activa:
            relation.vehicle.estado = Vehicle.DISPONIBLE
            relation.vehicle.save(update_fields=["estado"])
