import os
from pathlib import Path

from django.conf import settings

from apps.documentos.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    def __init__(self):
        self.raiz = Path(settings.BASE_DIR) / settings.DOCUMENT_LOCAL_ROOT

    def _ruta(self, storage_path):
        return self.raiz / storage_path

    def subir(self, storage_path, archivo, content_type):
        ruta = self._ruta(storage_path)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(archivo, "read"):
            with open(ruta, "wb") as f:
                f.write(archivo.read())
        else:
            with open(ruta, "wb") as f:
                f.write(archivo)

    def descargar(self, storage_path):
        with open(self._ruta(storage_path), "rb") as f:
            return f.read()

    def eliminar(self, storage_path):
        ruta = self._ruta(storage_path)
        if ruta.exists():
            ruta.unlink()

    def signed_url(self, storage_path, expira_segundos):
        return f"/documentos/media/{storage_path}"

    def existe(self, storage_path):
        return self._ruta(storage_path).exists()
