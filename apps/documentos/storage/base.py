class StorageBackend:
    def subir(self, storage_path, archivo, content_type):
        raise NotImplementedError

    def descargar(self, storage_path):
        raise NotImplementedError

    def eliminar(self, storage_path):
        raise NotImplementedError

    def signed_url(self, storage_path, expira_segundos):
        raise NotImplementedError

    def existe(self, storage_path):
        raise NotImplementedError
