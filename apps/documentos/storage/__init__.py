from django.conf import settings


def get_storage_backend():
    backend = settings.DOCUMENT_STORAGE_BACKEND
    if backend == "local":
        from apps.documentos.storage.local import LocalStorage

        return LocalStorage()
    if backend == "supabase":
        from apps.documentos.storage.supabase import SupabaseStorage

        return SupabaseStorage()
    raise ValueError(f"Backend de storage desconocido: {backend}")
