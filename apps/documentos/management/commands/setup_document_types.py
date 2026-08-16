from django.core.management.base import BaseCommand

from apps.documentos.models import DocumentType, content_type_driver, content_type_vehicle


class Command(BaseCommand):
    help = "Crea o actualiza los tipos documentales iniciales."

    TIPOS = [
        {
            "codigo": "soat",
            "nombre": "SOAT",
            "entity": content_type_vehicle,
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
            "entity": content_type_vehicle,
            "requires_expiration": True,
            "requires_issue_date": True,
            "replace_previous": True,
            "allow_multiple": False,
            "keep_history": False,
            "is_required": True,
        },
        {
            "codigo": "tarjeta_propiedad",
            "nombre": "Tarjeta de propiedad",
            "entity": content_type_vehicle,
            "requires_expiration": False,
            "requires_issue_date": True,
            "replace_previous": True,
            "allow_multiple": False,
            "keep_history": False,
            "is_required": True,
        },
        {
            "codigo": "cedula",
            "nombre": "Cédula",
            "entity": content_type_driver,
            "requires_expiration": False,
            "requires_issue_date": True,
            "replace_previous": True,
            "allow_multiple": False,
            "keep_history": False,
            "is_required": True,
        },
        {
            "codigo": "licencia",
            "nombre": "Licencia de conducción",
            "entity": content_type_driver,
            "requires_expiration": True,
            "requires_issue_date": True,
            "replace_previous": True,
            "allow_multiple": False,
            "keep_history": False,
            "is_required": True,
        },
        {
            "codigo": "curso",
            "nombre": "Curso",
            "entity": content_type_driver,
            "requires_expiration": False,
            "requires_issue_date": True,
            "replace_previous": False,
            "allow_multiple": True,
            "keep_history": True,
            "is_required": False,
        },
    ]

    def handle(self, *args, **options):
        for data in self.TIPOS:
            entity = data["entity"]()
            defaults = {k: v for k, v in data.items() if k not in ("codigo", "entity")}
            obj, created = DocumentType.objects.update_or_create(
                codigo=data["codigo"], entity_type=entity, defaults=defaults
            )
            action = "creado" if created else "actualizado"
            self.stdout.write(self.style.SUCCESS(f"Tipo '{obj.codigo}' {action}"))
