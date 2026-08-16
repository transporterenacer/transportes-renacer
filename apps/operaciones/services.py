from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.flota.models import Vehicle
from apps.operaciones.models import Incident, OperationVehicle, Shift


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


def registrar_turno(
    operation,
    vehicle,
    driver,
    fecha_inicio,
    fecha_fin,
    tipo,
    valor_estandar,
    meta_horas,
    novedad_categoria=None,
    novedad_descripcion="",
    observaciones="",
):
    inicio = timezone.make_aware(fecha_inicio)
    fin = timezone.make_aware(fecha_fin)
    horas = (fin - inicio).total_seconds() / 3600

    if horas < float(meta_horas) and novedad_categoria is None:
        raise ValidationError(
            "Un turno con menos horas que la meta requiere una novedad."
        )

    overlap = (
        Shift.objects.filter(vehicle=vehicle, estado__in=["programado", "realizado"])
        .filter(fecha_inicio__lt=fin, fecha_fin__gt=inicio)
        .exists()
    )
    if overlap:
        raise ValidationError("El vehículo ya tiene un turno en ese horario.")

    shift = Shift.objects.create(
        operation=operation,
        vehicle=vehicle,
        driver=driver,
        fecha_inicio=inicio,
        fecha_fin=fin,
        tipo=tipo,
        valor_estandar=valor_estandar,
        meta_horas=meta_horas,
        estado=Shift.REALIZADO,
        observaciones=observaciones,
    )
    if novedad_categoria is not None:
        Incident.objects.create(
            shift=shift, categoria=novedad_categoria, descripcion=novedad_descripcion
        )
    return shift


def cancelar_turno(shift, motivo, usuario=None):
    shift.estado = Shift.CANCELADO
    shift.motivo_cancelacion = motivo
    if usuario is not None:
        shift.updated_by = usuario
    shift.save()
