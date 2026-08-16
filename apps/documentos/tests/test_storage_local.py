import os
from django.test import TestCase, override_settings

from apps.documentos.storage import get_storage_backend
from apps.documentos.storage.local import LocalStorage


@override_settings(DOCUMENT_STORAGE_BACKEND="local")
class LocalStorageTests(TestCase):
    def test_backend_es_local(self):
        self.assertIsInstance(get_storage_backend(), LocalStorage)

    def test_subir_y_existe(self):
        storage = get_storage_backend()
        storage.subir("vehicles/ABC123/soat/test.pdf", b"%PDF-1.4", "application/pdf")
        self.assertTrue(storage.existe("vehicles/ABC123/soat/test.pdf"))

    def test_descargar_devuelve_bytes(self):
        storage = get_storage_backend()
        storage.subir("drivers/123/cedula/test.pdf", b"datos", "application/pdf")
        self.assertEqual(storage.descargar("drivers/123/cedula/test.pdf"), b"datos")

    def test_eliminar(self):
        storage = get_storage_backend()
        storage.subir("vehicles/ABC123/soat/test.pdf", b"%PDF-1.4", "application/pdf")
        storage.eliminar("vehicles/ABC123/soat/test.pdf")
        self.assertFalse(storage.existe("vehicles/ABC123/soat/test.pdf"))

    def test_signed_url_devuelve_ruta_local(self):
        storage = get_storage_backend()
        url = storage.signed_url("vehicles/ABC123/soat/test.pdf", 300)
        self.assertIn("/documentos/media/", url)
