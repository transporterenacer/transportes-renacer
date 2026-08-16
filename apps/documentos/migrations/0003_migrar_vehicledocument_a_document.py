import uuid

from django.db import migrations


def _asegurar_tipos(ContentType, DocumentType):
    vehicle_ct = ContentType.objects.get_or_create(
        app_label="flota", model="vehicle"
    )[0]
    tipos = [
        {
            "codigo": "soat",
            "nombre": "SOAT",
            "requires_expiration": True,
            "requires_issue_date": True,
            "replace_previous": True,
            "allow_multiple": False,
            "keep_history": False,
            "is_required": True,
        },
        {
            "codigo": "tecnomecanica",
            "nombre": "Técnico-mecánica",
            "requires_expiration": True,
            "requires_issue_date": True,
            "replace_previous": True,
            "allow_multiple": False,
            "keep_history": False,
            "is_required": True,
        },
    ]
    for data in tipos:
        codigo = data.pop("codigo")
        DocumentType.objects.get_or_create(
            codigo=codigo, entity_type=vehicle_ct, defaults=data
        )
    return vehicle_ct


def migrar(apps, schema_editor):
    VehicleDocument = apps.get_model("flota", "VehicleDocument")
    Document = apps.get_model("documentos", "Document")
    DocumentType = apps.get_model("documentos", "DocumentType")
    ContentType = apps.get_model("contenttypes", "ContentType")

    vehicle_ct = _asegurar_tipos(ContentType, DocumentType)

    for vd in VehicleDocument.objects.all():
        tipo_codigo = "soat" if vd.tipo == "soat" else "tecnomecanica"
        tipo = DocumentType.objects.get(codigo=tipo_codigo)
        placa = vd.vehicle.placa
        anio = vd.fecha_vencimiento.year if vd.fecha_vencimiento else ""
        Document.objects.create(
            entity_type=vehicle_ct,
            entity_id=vd.vehicle_id,
            tipo=tipo,
            nombre_archivo=f"{tipo_codigo.upper()}_{placa}_{anio}.pdf",
            storage_path=f"vehicles/{placa}/{tipo_codigo}/{uuid.uuid4()}.pdf",
            extension="pdf",
            mime_type="application/pdf",
            tamano=0,
            fecha_vencimiento=vd.fecha_vencimiento,
            estado="vigente",
        )


def revertir(apps, schema_editor):
    Document = apps.get_model("documentos", "Document")
    Document.objects.filter(
        entity_type__app_label="flota", entity_type__model="vehicle"
    ).filter(tipo__codigo__in=["soat", "tecnomecanica"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("documentos", "0002_documentaudit_historicaldocument_and_more"),
        ("flota", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(migrar, revertir),
    ]
