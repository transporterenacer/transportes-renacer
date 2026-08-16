from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from supabase import create_client

from apps.documentos.storage.base import StorageBackend


class SupabaseStorage(StorageBackend):
    def __init__(self):
        url = settings.SUPABASE_URL
        key = settings.SUPABASE_SERVICE_ROLE_KEY
        if not url or not key:
            raise ImproperlyConfigured(
                "SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY son requeridos para el backend supabase."
            )
        self.client = create_client(url, key)
        self.bucket = self.client.storage.from_(settings.DOCUMENT_BUCKET)

    def subir(self, storage_path, archivo, content_type):
        self.bucket.upload(storage_path, archivo, {"content-type": content_type})

    def descargar(self, storage_path):
        return self.bucket.download(storage_path)

    def eliminar(self, storage_path):
        self.bucket.remove([storage_path])

    def signed_url(self, storage_path, expira_segundos):
        data = self.bucket.create_signed_url(storage_path, expira_segundos)
        return data["signedURL"]

    def existe(self, storage_path):
        try:
            self.descargar(storage_path)
            return True
        except Exception:
            return False
