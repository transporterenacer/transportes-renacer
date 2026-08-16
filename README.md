# Sistema de Gestión de Operaciones — Transportes Renacer

Sistema web de gestión de operaciones portuarias para **Transportes Renacer** (Colombia). Centraliza la operación de mulas (vehículos), conductores, nómina, facturación y la documentación digital de la flota.

## Módulos

| Módulo | Descripción |
| ------ | ----------- |
| `core` | Configuración base, home y utilidades comunes. |
| `dashboard` | Panel de indicadores operativos del día. |
| `catalogos` | Catálogos maestros (clientes / generadores de carga). |
| `flota` | Vehículos (mulas), sus estados y alertas. |
| `conductores` | Conductores, estados y documentación asociada. |
| `operaciones` | Operaciones, vehículos de operación, turnos e incidentes. |
| `facturacion` | Facturación y registros de cobro. |
| `nomina` | Nómina, ítems de nómina y anticipos de conductores. |
| `documentos` | **Gestión documental digital**: expediente de documentos por vehículo y conductor, con auditoría, alertas de vencimiento y almacenamiento intercambiable (local / Supabase). |

## Requisitos

- Python 3.12+
- Django 5.2 (ver `requirements.txt`)
- PostgreSQL opcional (para producción); SQLite para desarrollo local.

## Setup local

```bash
# 1. Crear y activar el entorno virtual
python -m venv .venv
.\.venv\Scripts\activate        # Windows PowerShell
# source .venv/bin/activate     # Linux / macOS

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Copiar la configuración de entorno
copy .env.example .env          # Windows
# cp .env.example .env          # Linux / macOS

# 4. Aplicar migraciones y sembrar tipos documentales
python manage.py migrate
python manage.py setup_document_types

# 5. (Opcional) Crear un superusuario
python manage.py createsuperuser

# 6. Levantar el servidor
python manage.py runserver
```

Abre <http://127.0.0.1:8000> en el navegador.

## Variables de entorno

Copiá `.env.example` a `.env` y ajustá los valores.

```ini
DJANGO_SETTINGS_MODULE=config.settings.dev
SECRET_KEY=change-me
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=127.0.0.1,localhost

# Gestión documental
DOCUMENT_STORAGE_BACKEND=local
DOCUMENT_BUCKET=documents
DOCUMENT_MAX_SIZE=10485760
DOCUMENT_ALLOWED_EXTENSIONS=pdf,jpg,jpeg,png
DOCUMENT_ALERT_DAYS=30
DOCUMENT_SIGNED_URL_EXPIRES=300
DOCUMENT_STORAGE_LIMIT=1073741824
# SUPABASE_URL=
# SUPABASE_SERVICE_ROLE_KEY=
```

| Variable | Descripción | Default |
| -------- | ----------- | ------- |
| `DOCUMENT_STORAGE_BACKEND` | `local` (dev/tests) o `supabase` (prod). | `local` |
| `DOCUMENT_BUCKET` | Nombre del bucket de Supabase Storage. | `documents` |
| `DOCUMENT_MAX_SIZE` | Tamaño máximo por archivo (bytes). | `10485760` (10 MB) |
| `DOCUMENT_ALLOWED_EXTENSIONS` | Extensiones permitidas. | `pdf,jpg,jpeg,png` |
| `DOCUMENT_ALERT_DAYS` | Días de anticipación para alertar vencimiento. | `30` |
| `DOCUMENT_SIGNED_URL_EXPIRES` | Vigencia de las signed URLs (segundos). | `300` |
| `DOCUMENT_STORAGE_LIMIT` | Límite de almacenamiento usado por el indicador (bytes). | `1073741824` (1 GB) |
| `SUPABASE_URL` | URL del proyecto Supabase (solo backend `supabase`). | *(vacío)* |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key de Supabase (solo backend `supabase`, nunca en el navegador). | *(vacío)* |

## Configuración de Supabase Storage

Para producción, los archivos se guardan en **Supabase Storage** en un bucket **privado** llamado `documents`.

1. En el panel de Supabase creá un bucket privado con nombre `documents`.
2. Configurá las variables de entorno:

   ```ini
   DOCUMENT_STORAGE_BACKEND=supabase
   DOCUMENT_BUCKET=documents
   SUPABASE_URL=https://TU-PROYECTO.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=TU-SERVICE-ROLE-KEY
   ```

   > La **service role key** solo debe vivir en el servidor (variable de entorno). El módulo nunca la expone al navegador: genera signed URLs de corta duración que el navegador consume.

3. Aplicá las políticas de seguridad (SQL en el SQL Editor):

```sql
-- Bucket privado "documents": denegar acceso público.
-- Los accesos se hacen mediante signed URLs generadas por el servidor
-- con la service role key; las políticas protegen accesos directos no autenticados.

-- 1) Sin políticas "public" en el bucket: por defecto, sin autenticación JWT no hay acceso.
-- 2) La service role key opera como superusuario y esquiva las políticas (acceso del backend).

-- 3) Para el acceso autenticado (usuarios del sistema vía signed URLs), se recomienda
--    limitar las políticas al acceso de lectura sobre objetos ya existentes:

-- Policy: SELECT / GET solo para usuarios autenticados
create policy "documentos: lectura solo usuarios autenticados"
  on storage.objects
  for select
  to authenticated
  using (bucket_id = 'documents');

-- Policy: bloquear escritura directa de usuarios anónimos
create policy "documentos: sin escritura pública"
  on storage.objects
  for insert
  to public
  using (false);
```

Ajustá estas políticas a tu modelo de roles (p. ej. solo `authenticated` para lectura y ninguna escritura pública, ya que la subida/descarga se hace por el backend).

## Backend intercambiable

El módulo documental no depende de un proveedor de almacenamiento en particular: usa una interfaz común (`apps/documentos/storage/`).

- **`local`** — guarda archivos en `media/documents/`. Ideal para desarrollo y tests (sin credenciales, sin red).
- **`supabase`** — guarda archivos en Supabase Storage con signed URLs.

Para cambiar el backend solo se modifica la variable de entorno `DOCUMENT_STORAGE_BACKEND` — sin cambios de código.

## Arquitectura extensible

> ### Arquitectura extensible
>
> El módulo de gestión documental está diseñado sobre un modelo genérico (`Document`) asociado a cualquier entidad del sistema mediante `contenttypes`. Hoy los documentos se asocian a **vehículos** y **conductores**, pero el módulo **ya soporta** asociar documentos a operaciones, boletas, facturas, relaciones de cobro y soportes de pago **simplemente creando un `DocumentType`** para esa entidad (via `contenttypes`) — **sin migraciones de estructura**.
>
> Esto significa que extender el módulo a una nueva entidad es solo configurar un nuevo tipo documental: el modelo de datos, el almacenamiento, la auditoría y las alertas ya funcionan de forma genérica.
>
> **Importante:** esas asociaciones específicas (operaciones, boletas, facturas, relaciones de cobro, soportes de pago) **no se han desarrollado aún**. Son un siguiente paso natural que no requiere rediseñar la arquitectura.

## Tests

```bash
python manage.py test -v 2
```

En dev y tests el módulo documental usa `LocalStorage`, por lo que la suite corre sin credenciales de Supabase.
