import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.documentos.models import (
    Document,
    DocumentAudit,
    DocumentType,
    content_type_driver,
    content_type_vehicle,
)
from apps.documentos.storage import get_storage_backend
from apps.conductores.models import Driver
from apps.flota.models import Vehicle


def documentos_vigentes_entidad(entidad, tipo=None):
    qs = Document.objects.filter(entity_id=entidad.pk, estado=Document.VIGENTE)
    if tipo is not None:
        qs = qs.filter(tipo=tipo)
    return qs


def generar_storage_path(tipo, entidad, extension):
    if isinstance(entidad, Vehicle):
        prefijo = f"vehicles/{entidad.placa}/{tipo.codigo}"
    elif isinstance(entidad, Driver):
        prefijo = f"drivers/{entidad.documento}/{tipo.codigo}"
    else:
        raise ValidationError("Entidad no soportada para documentos.")
    return f"{prefijo}/{uuid.uuid4()}.{extension}"


def generar_nombre_archivo(tipo, entidad, anio, extension):
    if isinstance(entidad, Vehicle):
        identificador = entidad.placa
    elif isinstance(entidad, Driver):
        identificador = entidad.documento
    else:
        raise ValidationError("Entidad no soportada para documentos.")
    return f"{tipo.codigo.upper()}_{identificador}_{anio}.{extension}"


def _ruta_tipo_entidad(tipo, entidad):
    if isinstance(entidad, Vehicle):
        return f"vehicles/{entidad.placa}/{tipo.codigo}"
    if isinstance(entidad, Driver):
        return f"drivers/{entidad.documento}/{tipo.codigo}"
    raise ValidationError("Entidad no soportada.")


def validar_archivo(tipo, entidad, nombre, contenido, content_type):
    ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if ext not in settings.DOCUMENT_ALLOWED_EXTENSIONS:
        raise ValidationError(f"Extensión '{ext}' no permitida.")
    if len(contenido) > settings.DOCUMENT_MAX_SIZE:
        raise ValidationError(
            f"El archivo supera el máximo de {settings.DOCUMENT_MAX_SIZE // 1048576} MB."
        )
    entidad_ct = tipo.entity_type
    if not isinstance(entidad, entidad_ct.model_class()):
        raise ValidationError("El tipo documental no aplica a esta entidad.")
    return ext


def cargar_documento(
    tipo,
    entidad,
    archivo,
    content_type,
    extension,
    tamano,
    fecha_expedicion=None,
    fecha_vencimiento=None,
    usuario=None,
):
    if tipo.requires_issue_date and not fecha_expedicion:
        raise ValidationError("Este tipo de documento requiere fecha de expedición.")
    if tipo.requires_expiration and not fecha_vencimiento:
        raise ValidationError("Este tipo de documento requiere fecha de vencimiento.")

    contenido = archivo.read() if hasattr(archivo, "read") else archivo
    extension = extension.lower()
    if extension not in settings.DOCUMENT_ALLOWED_EXTENSIONS:
        raise ValidationError(f"Extensión '{extension}' no permitida.")
    if len(contenido) > settings.DOCUMENT_MAX_SIZE:
        raise ValidationError(
            f"El archivo supera el máximo de {settings.DOCUMENT_MAX_SIZE // 1048576} MB."
        )

    storage = get_storage_backend()
    storage_path = generar_storage_path(tipo, entidad, extension)
    anio = (fecha_vencimiento or fecha_expedicion or timezone.localdate()).year
    nombre_archivo = generar_nombre_archivo(tipo, entidad, anio, extension)

    storage.subir(storage_path, contenido, content_type)
    if not storage.existe(storage_path):
        raise ValidationError("La subida al almacenamiento falló; el documento anterior queda intacto.")

    with transaction.atomic():
        anterior = None
        if tipo.replace_previous:
            anterior = (
                Document.objects.filter(
                    entity_id=entidad.pk,
                    entity_type=tipo.entity_type,
                    tipo=tipo,
                    estado=Document.VIGENTE,
                )
                .exclude(storage_path=storage_path)
                .first()
            )
        doc = Document.objects.create(
            entity=entidad,
            tipo=tipo,
            nombre_archivo=nombre_archivo,
            storage_path=storage_path,
            extension=extension,
            mime_type=content_type,
            tamano=tamano,
            fecha_expedicion=fecha_expedicion,
            fecha_vencimiento=fecha_vencimiento,
            estado=Document.VIGENTE,
            cargado_por=usuario,
        )
        if anterior is not None:
            anterior.estado = Document.REEMPLAZADO
            anterior.save(update_fields=["estado", "updated_by"])
            storage.eliminar(anterior.storage_path)
            DocumentAudit.objects.create(
                usuario=usuario,
                accion=DocumentAudit.REEMPLAZO,
                entity_type=tipo.entity_type,
                entity_id=entidad.pk,
                tipo=tipo.codigo,
                archivo_anterior=anterior.storage_path,
                archivo_nuevo=storage_path,
                detalle=f"Reemplazo de {tipo.nombre} para {entidad}",
            )
        else:
            DocumentAudit.objects.create(
                usuario=usuario,
                accion=DocumentAudit.CARGA,
                entity_type=tipo.entity_type,
                entity_id=entidad.pk,
                tipo=tipo.codigo,
                archivo_nuevo=storage_path,
                detalle=f"Carga de {tipo.nombre} para {entidad}",
            )
    return doc


def estado_documento(doc):
    if not doc.fecha_vencimiento:
        return Document.VIGENTE
    dias = (doc.fecha_vencimiento - timezone.localdate()).days
    if dias < 0:
        return "vencido"
    if dias <= settings.DOCUMENT_ALERT_DAYS:
        return "proximo"
    return Document.VIGENTE


def alertas_vencimiento_documentos():
    alerts = []
    for doc in (
        Document.objects.filter(
            entity_type=content_type_vehicle(), estado=Document.VIGENTE
        )
        .select_related("tipo", "entity_type")
        .exclude(fecha_vencimiento__isnull=True)
    ):
        estado = estado_documento(doc)
        if estado in ("proximo", "vencido"):
            alerts.append(
                {
                    "documento": doc,
                    "vehiculo": doc.entity,
                    "tipo": doc.tipo.nombre,
                    "fecha_vencimiento": doc.fecha_vencimiento,
                    "dias": (doc.fecha_vencimiento - timezone.localdate()).days,
                    "estado": estado,
                }
            )
    alerts.sort(key=lambda a: a["dias"])
    return alerts


def documentos_faltantes():
    faltantes = []
    tipos_vehicle = DocumentType.objects.filter(
        entity_type=content_type_vehicle(), is_required=True, activo=True
    )
    for vehicle in Vehicle.objects.all():
        codigos = set(
            Document.objects.filter(
                entity_id=vehicle.pk,
                entity_type=content_type_vehicle(),
                estado=Document.VIGENTE,
            ).values_list("tipo__codigo", flat=True)
        )
        for tipo in tipos_vehicle:
            if tipo.codigo not in codigos:
                faltantes.append(
                    {"entidad": vehicle, "tipo": tipo, "es_personal": False}
                )
    tipos_driver = DocumentType.objects.filter(
        entity_type=content_type_driver(), is_required=True, activo=True
    )
    for driver in Driver.objects.filter(estado=Driver.DISPONIBLE):
        codigos = set(
            Document.objects.filter(
                entity_id=driver.pk,
                entity_type=content_type_driver(),
                estado=Document.VIGENTE,
            ).values_list("tipo__codigo", flat=True)
        )
        for tipo in tipos_driver:
            if tipo.codigo not in codigos:
                faltantes.append(
                    {"entidad": driver, "tipo": tipo, "es_personal": True}
                )
    return faltantes


def desactivar_conductor(driver, usuario=None):
    borrados = 0
    for doc in list(
        Document.objects.filter(
            entity_id=driver.pk,
            entity_type=content_type_driver(),
            estado=Document.VIGENTE,
        ).select_related("tipo")
    ):
        if doc.es_personal:
            get_storage_backend().eliminar(doc.storage_path)
            DocumentAudit.objects.create(
                usuario=usuario,
                accion=DocumentAudit.BORRADO,
                entity_type=doc.entity_type,
                entity_id=driver.pk,
                tipo=doc.tipo.codigo,
                archivo_anterior=doc.storage_path,
                detalle=f"Borrado por desactivación del conductor {driver}",
            )
            doc.delete()
            borrados += 1
    driver.estado = Driver.INACTIVO
    driver.save(update_fields=["estado"])
    return borrados
