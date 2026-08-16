from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase

from apps.documentos.models import DocumentType


class SetupDocumentTypesTests(TestCase):
    def test_seed_crea_los_seis_tipos(self):
        call_command("setup_document_types")
        codigos = set(DocumentType.objects.values_list("codigo", flat=True))
        self.assertEqual(
            codigos,
            {"soat", "tecnomecanica", "tarjeta_propiedad", "cedula", "licencia", "curso"},
        )

    def test_seed_es_idempotente(self):
        call_command("setup_document_types")
        call_command("setup_document_types")
        self.assertEqual(DocumentType.objects.count(), 6)

    def test_soat_configurado_correctamente(self):
        call_command("setup_document_types")
        soat = DocumentType.objects.get(codigo="soat")
        self.assertTrue(soat.requires_expiration)
        self.assertTrue(soat.requires_issue_date)
        self.assertTrue(soat.replace_previous)
        self.assertFalse(soat.allow_multiple)
        self.assertFalse(soat.keep_history)
        self.assertTrue(soat.is_required)
        self.assertEqual(soat.entity_type.model_class().__name__, "Vehicle")

    def test_curso_configurado_correctamente(self):
        call_command("setup_document_types")
        curso = DocumentType.objects.get(codigo="curso")
        self.assertTrue(curso.allow_multiple)
        self.assertFalse(curso.replace_previous)
        self.assertTrue(curso.keep_history)
        self.assertFalse(curso.is_required)
        self.assertEqual(curso.entity_type.model_class().__name__, "Driver")
