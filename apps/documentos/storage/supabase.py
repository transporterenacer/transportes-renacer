from apps.documentos.storage.base import StorageBackend


class SupabaseStorage(StorageBackend):
    def __init__(self):
        raise NotImplementedError(
            "SupabaseStorage se implementa en la Task 4 (requiere supabase-py)."
        )
