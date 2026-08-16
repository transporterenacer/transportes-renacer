from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from apps.documentos.storage.supabase import SupabaseStorage


@override_settings(
    DOCUMENT_STORAGE_BACKEND="supabase",
    SUPABASE_URL="https://proyecto.supabase.co",
    SUPABASE_SERVICE_ROLE_KEY="clave-servicio",
)
class SupabaseStorageTests(SimpleTestCase):
    def test_sin_credenciales_lanza_error(self):
        with override_settings(SUPABASE_URL="", SUPABASE_SERVICE_ROLE_KEY=""):
            with self.assertRaises(ImproperlyConfigured):
                SupabaseStorage()

    @mock.patch("apps.documentos.storage.supabase.create_client")
    def test_subir_llama_upload(self, mock_create):
        client = mock.MagicMock()
        bucket = mock.MagicMock()
        client.storage.from_.return_value = bucket
        mock_create.return_value = client

        storage = SupabaseStorage()
        storage.subir("vehicles/ABC123/soat/x.pdf", b"%PDF-1.4", "application/pdf")

        bucket.upload.assert_called_once_with(
            "vehicles/ABC123/soat/x.pdf", b"%PDF-1.4", {"content-type": "application/pdf"}
        )

    @mock.patch("apps.documentos.storage.supabase.create_client")
    def test_signed_url_devuelve_url(self, mock_create):
        client = mock.MagicMock()
        bucket = mock.MagicMock()
        bucket.create_signed_url.return_value = {"signedURL": "https://x/y?sig=1"}
        client.storage.from_.return_value = bucket
        mock_create.return_value = client

        storage = SupabaseStorage()
        url = storage.signed_url("vehicles/ABC123/soat/x.pdf", 300)
        self.assertEqual(url, "https://x/y?sig=1")
        bucket.create_signed_url.assert_called_once_with("vehicles/ABC123/soat/x.pdf", 300)
