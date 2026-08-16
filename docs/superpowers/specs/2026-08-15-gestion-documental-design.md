# Gestión Documental — Transportes Renacer

**Fecha:** 2026-08-15
**Estado:** Aprobado por el cliente
**Tipo:** Especificación de diseño / spec de implementación

---

## 1. Resumen

Módulo de **gestión documental digital** para vehículos (mulas) y conductores de Transportes Renacer. Cada entidad tendrá un expediente documental en Supabase Storage (bucket privado) con metadatos en PostgreSQL (Supabase). Soporta carga, consulta (ver en el navegador), descarga y reemplazo seguro de documentos, con auditoría y control del almacenamiento. Sin compartición externa con enlaces temporales.

**Regla de integración:** no modifica ni rediseña los módulos existentes (operaciones, flota, conductores, turnos, nómina, facturación). Solo agrega funcionalidad documental. Única excepción acordada: el modelo `VehicleDocument` (SOAT/tecnomecánica) de `apps.flota` **migra** al nuevo modelo genérico `Document`, y `alertas_vencimiento()` pasa a leer del nuevo modelo. Los registros existentes se migran por data migration.

---

## 2. Decisiones de stack (aprobadas)

| Capa | Decisión |
|---|---|
| Backend | Django 5.2 (continuación del proyecto existente) |
| BD (metadatos) | PostgreSQL vía Supabase (prod) / SQLite (dev) — patrón actual |
| Almacenamiento físico | **Supabase Storage** (prod), bucket privado `documents` |
| Referencia polimórfica | `GenericForeignKey` (contenttypes de Django) |
| Cliente Supabase | `supabase-py` v2 (`supabase` en requirements), envuelto en backend intercambiable |
| Backend de storage | `LocalStorage` (dev/tests, carpeta `media/documents/`) · `SupabaseStorage` (prod). Selección por `settings.DOCUMENT_STORAGE_BACKEND` |
| Signed URLs | Generadas por el backend con expiración configurable por `.env` (ver/descargar 5 min). Nunca almacenadas en BD. **No hay compartición externa con enlace temporal**: "Ver" abre el PDF en el navegador (el lector nativo permite descargar) y "Descargar" genera una URL temporal breve para el usuario autenticado |
| Frontend | Templates Django + HTMX + CSS puro con tokens (patrón existente), JS vanilla mínimo para copiar enlace |

**No se usa:** buckets públicos, URLs públicas permanentes, OCR/IA/extracción automática (fase futura), almacenamiento de binarios en PostgreSQL.

---

## 3. Decisiones de diseño clave

1. **Migración de `VehicleDocument`**: los registros SOAT/tecnomecánica existentes se convierten a `Document` (data migration). El dashboard de vencimientos (`apps.dashboard.views.dashboard_vencimientos`) pasa a leer de `Document`. El modelo `VehicleDocument` queda obsoleto y sus tests se actualizan.
2. **Backend intercambiable**: `DOCUMENT_STORAGE_BACKEND = "local" | "supabase"`. Dev/tests usan LocalStorage (sin credenciales, TDD sin red). Al conectar Supabase se cambia la variable de entorno — sin cambios de código.
3. **Alertas de vencimiento**: solo para vehículos. El estado "NO CARGADO" (documento obligatorio faltante) se muestra para vehículos y conductores.
4. **Reemplazo seguro**: el nuevo archivo se sube y confirma **antes** de borrar el anterior. Nunca se elimina el archivo anterior sin confirmación de la subida.
5. **Auditoría inborrable**: `DocumentAudit` registra cargas, reemplazos, borrados y comparticiones. Sobrevive a la eliminación del PDF anterior y del registro documental.

---

## 4. Modelo de datos

### 4.1 `DocumentType` (configuración, §5)

Hereda de `apps.core.models.AuditMixin`.

| Campo | Tipo | Notas |
|---|---|---|
| `nombre` | CharField(100) | Ej. "SOAT" |
| `codigo` | CharField(50), unique | Slug estable, ej. `soat`, `tecnomecanica`, `tarjeta_propiedad`, `cedula`, `licencia`, `curso` |
| `entity_type` | FK ContentType | Entidad a la que aplica (vehicle / driver) |
| `requires_expiration` | Boolean default False | Si el tipo exige `fecha_vencimiento` |
| `requires_issue_date` | Boolean default False | Si exige `fecha_expedicion` |
| `allow_multiple` | Boolean default False | Si permite varios documentos vigentes del mismo tipo |
| `replace_previous` | Boolean default False | Si reemplaza automáticamente el documento anterior |
| `keep_history` | Boolean default True | Si se conservan versiones históricas (solo relevante si `allow_multiple`) |
| `is_required` | Boolean default False | Obligatorio → entra en estado "NO CARGADO" cuando falta |
| `activo` | Boolean default True | |

**Seed inicial** (data migration / comando):

| codigo | entity | expira | emisión | multiple | reemplaza | historico | obligatorio |
|---|---|---|---|---|---|---|---|
| `soat` | vehicle | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| `tecnomecanica` | vehicle | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| `tarjeta_propiedad` | vehicle | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ |
| `cedula` | driver | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ |
| `licencia` | driver | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| `curso` | driver | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ |

Nota: `licencia` tiene `requires_expiration=True` para registrar la fecha, pero **no genera alerta de vencimiento** (decisión: alertas solo vehículos). Su estado se calcula como vigente/marcado con la fecha, sin semáforo de vencimiento.

### 4.2 `Document` (modelo genérico, §4)

Hereda de `apps.core.models.AuditMixin` (provee `created_at`, `updated_at`, `created_by`, `updated_by`, `history`).

| Campo | Tipo | Notas |
|---|---|---|
| `entity_type` | FK ContentType | |
| `entity_id` | PositiveIntegerField | |
| `entity` | **GenericForeignKey** | Acceso al objeto (vehicle/driver) |
| `tipo` | FK DocumentType | related_name="documentos" |
| `nombre_archivo` | CharField(255) | Nombre visible, ej. `SOAT_ABC123_2027.pdf` (generado por la app, no por el usuario) |
| `storage_path` | CharField(500), unique | Ruta física dentro del bucket, ej. `vehicles/ABC123/soat/9f8a…-uuid.pdf`. Usa UUID para el archivo físico |
| `extension` | CharField(10) | `pdf`, `jpg`, `jpeg`, `png` |
| `mime_type` | CharField(100) | |
| `tamano` | PositiveBigIntegerField | Bytes |
| `fecha_expedicion` | DateField null/blank | Obligatorio si `tipo.requires_issue_date` |
| `fecha_vencimiento` | DateField null/blank | Obligatorio si `tipo.requires_expiration` |
| `estado` | CharField(20) | `vigente` | `reemplazado`. No eliminación física del registro si `keep_history` |
| `cargado_por` | FK auth.User (SET_NULL, null) | |
| `cargado_en` | DateTimeField auto_now_add | |

**Reglas:**
- Si `tipo.replace_previous=True`: como máximo un `Document` **vigente** por (entidad, tipo). Al cargar uno nuevo, el anterior pasa a `estado=reemplazado` y su archivo físico se elimina del Storage.
- Si `tipo.allow_multiple=True`: pueden existir varios vigentes (históricos se conservan).
- Si `tipo.keep_history=True` y `allow_multiple`: no se eliminan archivos de versiones previas.

### 4.3 `DocumentAudit` (§7)

Hereda de `apps.core.models.AuditMixin`. **Nunca se elimina.**

| Campo | Tipo |
|---|---|
| `usuario` | FK auth.User (SET_NULL, null) |
| `accion` | CharField(20): `carga` / `reemplazo` / `borrado` / `consulta` |
| `entity_type` / `entity_id` | ContentType + id |
| `tipo` | CharField(100) (código o nombre del tipo, snapshot) |
| `archivo_anterior` | CharField(500) blank (storage_path o nombre visible anterior) |
| `archivo_nuevo` | CharField(500) blank |
| `detalle` | TextField blank |

---

## 5. Storage

### 5.1 Estructura del bucket

Un solo bucket privado `documents`. Rutas lógicas (UUID para el archivo físico, evita colisiones):

```
documents/
  vehicles/{PLACA_UPPER}/soat/{uuid}.pdf
  vehicles/{PLACA_UPPER}/tecnomecanica/{uuid}.pdf
  vehicles/{PLACA_UPPER}/tarjeta_propiedad/{uuid}.pdf
  drivers/{DOCUMENTO}/cedula/{uuid}.pdf
  drivers/{DOCUMENTO}/licencia/{uuid}.pdf
  drivers/{DOCUMENTO}/curso/{uuid}.pdf
```

### 5.2 Backend de storage (interfaz)

`apps/documentos/storage/base.py`:

```python
class StorageBackend:
    def subir(self, storage_path, archivo, content_type): ...
    def descargar(self, storage_path) -> bytes: ...
    def eliminar(self, storage_path) -> None: ...
    def signed_url(self, storage_path, expira_segundos) -> str: ...
    def existe(self, storage_path) -> bool: ...
```

- `LocalStorage`: raíz en `settings.DOCUMENT_LOCAL_ROOT` (default `media/documents/`). `signed_url` devuelve una URL de vista local protegida (el backend hace de proxy) con expiración simulada — en dev/tests.
- `SupabaseStorage`: usa `supabase-py`. Bucket `documents`. `signed_url` llama `createSignedUrl`. La service role key solo vive en el servidor (variable de entorno).

### 5.3 Seguridad (§10)

- Bucket **privado**. Solo el backend accede con la service role key (nunca expuesta al navegador).
- Flujo ver/descargar:
  1. `@login_required` verifica autenticación.
  2. El backend verifica que el documento existe y pertenece a la entidad pedida.
  3. Genera signed URL con expiración.
  4. El navegador consume la URL temporal.
- **"Ver"** abre el PDF en el navegador (un `<iframe>`/pestaña apuntando a la signed URL; el lector nativo del navegador incluye su propio botón de descarga). **"Descargar"** fuerza la descarga con el nombre amigable.
- RLS / Storage Policies: se documentan en el README como SQL a aplicar en Supabase. La service role key opera como superusuario; las políticas protegen accesos directos no autenticados.

### 5.4 Sin compartición externa

- **No existe botón "Compartir" ni enlace temporal para terceros.** Decisión del cliente.
- Quien tenga acceso al sistema ve el documento con "Ver" (lector de PDF, que permite descargar) o lo descarga con "Descargar".
- Los documentos permanecen siempre privados; solo el backend puede generar signed URLs de corta duración para usuarios autenticados.

---

## 6. Flujos de negocio

### 6.1 Cargar documento (§13, §23)

1. Formulario: tipo (según entidad), archivo, fecha expedición (si aplica), fecha vencimiento (si aplica).
2. Validaciones: entidad existe (GenericForeignKey), tipo aplica a la entidad, extensión permitida (PDF/JPG/JPEG/PNG), tamaño ≤ `DOCUMENT_MAX_SIZE` (default 10 MB), fecha vencimiento requerida si `requires_expiration`, fecha expedición requerida si `requires_issue_date`.
3. `storage_path` = `{ruta_tipo}/{uuid}.{ext}`; `nombre_archivo` = `{TIPO}_{identificador}_{año}.{ext}` (ej. `SOAT_ABC123_2027.pdf`).
4. **Subir a Storage primero**, confirmar éxito (`existe()`).
5. Crear `Document` (estado `vigente`).
6. Si `replace_previous`: marcar el anterior `reemplazado`, **borrar su archivo del Storage**.
7. Auditoría `carga`.

### 6.2 Reemplazar documento (§6, §14)

- Si hay un documento vigente del mismo tipo, la UI muestra: "Este documento reemplazará el SOAT actual de ABC123." → [Cancelar] [Reemplazar].
- Orden transaccional (lo más atómico posible):
  1. Validar archivo.
  2. Subir nuevo a Storage.
  3. Confirmar subida exitosa.
  4. Registrar nuevo `Document` (vigente).
  5. Marcar el anterior `reemplazado`.
  6. Borrar el archivo anterior del Storage.
  7. Auditoría `reemplazo` (archivo_anterior, archivo_nuevo).
- **Nunca** borrar el anterior antes de confirmar la subida del nuevo. Si la subida falla, el anterior queda intacto.

### 6.3 Desactivar conductor (§15)

- Flujo nuevo en el módulo documental: botón "Desactivar conductor".
- Confirmación exacta: "El conductor será marcado como inactivo y sus documentos personales serán eliminados permanentemente del almacenamiento. Su historial operativo y de nómina se conservará." → [Cancelar] [Confirmar].
- Efectos:
  - `Driver.estado` → `INACTIVO`.
  - Elimina del Storage los documentos personales (`cedula`, `licencia`, y otros con política que lo permita) cuyo `tipo.replace_previous=True` o que estén marcados como personales.
  - **Conserva**: el conductor en BD, historial de turnos, nómina, operaciones y toda la auditoría.
  - Registra auditoría `borrado` por documento eliminado.
- No elimina documentos que la política indique conservar.

### 6.4 Desactivar/retirar vehículo (§16)

- Los documentos reemplazables/actuales pueden eliminarse según política, independiente de la eliminación del vehículo.
- No se borran historiales de operaciones, turnos, facturación, nómina.

### 6.5 Alertas de vencimiento (§17)

- **Solo vehículos.** Estados calculados por documento con `fecha_vencimiento`:
  - 🟢 VIGENTE (vencimiento > `DOCUMENT_ALERT_DAYS` días).
  - 🟡 PRÓXIMO A VENCER (≤ 30 días, configurable `DOCUMENT_ALERT_DAYS`, default 30).
  - 🔴 VENCIDO (vencimiento < hoy).
  - ⚪ NO CARGADO (tipo `is_required=True` sin documento vigente para la entidad) — para vehículos y conductores.
- Mensajes: "⚠️ SOAT ABC123 vence en 24 días.", "🔴 Técnico-mecánica DEF456 vencida.", "⚪ Licencia de Juan Pérez no cargada."
- La fecha de vencimiento se **digita** al cargar el archivo (no OCR).

---

## 7. Vistas y UI

### 7.1 Panel documental (`documentos/`)

- Indicadores: vigentes, próximos a vencer, vencidos, faltantes.
- Filtros: vehículo, conductor, tipo, estado, fecha de vencimiento.
- Tabla de alertas de vencimiento (vehículos) y faltantes (ambos).

### 7.2 Ficha del vehículo (`vehicle/<pk>/`)

- Datos del vehículo + sección DOCUMENTACIÓN con cada tipo:
  - `SOAT` 🟢 Vigente · Vence: 20/09/2027 · [Ver] [Descargar] [Reemplazar]
  - `Técnico-mecánica` 🟡 Próximo a vencer · Vence: 25/08/2026 · [Ver] [Descargar] [Reemplazar]
  - `Tarjeta de propiedad` 🟢 Registrada · [Ver] [Descargar] [Reemplazar]
- Botón "+ Agregar documento" (formulario §23).

### 7.3 Ficha del conductor (`driver/<pk>/`)

- Datos del conductor + sección DOCUMENTACIÓN (cédula, licencia, otros) con las mismas acciones.
- Botón "Desactivar conductor" con la confirmación del §15 (solo si `estado != inactivo`).

### 7.4 URL namespace `documentos`

- `documentos:panel` → panel documental.
- `documentos:vehicle` (`vehicle/<int:pk>/`) y `documentos:driver` (`driver/<int:pk>/`) → fichas.
- `documentos:subir` → POST multipart (entidad+tipo+archivo+ fechas).
- `documentos:descargar` (`<int:pk>/descargar/`) → redirect a signed URL.
- `documentos:ver` (`<int:pk>/ver/`) → redirect a signed URL (abre el PDF en el navegador).
- `documentos:reemplazar` (`<int:pk>/reemplazar/`) → confirmación + POST.
- `documentos:desactivar_conductor` (`driver/<int:pk>/desactivar/`) → POST con confirmación.

---

## 8. Configuración (settings)

Variables de entorno (documentadas en `.env.example` y README):

```
DOCUMENT_STORAGE_BACKEND=local|supabase   (default local)
DOCUMENT_BUCKET=documents                 (default)
DOCUMENT_MAX_SIZE=10485760                (10 MB)
DOCUMENT_ALLOWED_EXTENSIONS=pdf,jpg,jpeg,png
DOCUMENT_ALERT_DAYS=30
DOCUMENT_SIGNED_URL_EXPIRES=300           (5 min, ver/descargar)
DOCUMENT_STORAGE_LIMIT=1073741824         (1 GB, límite para el indicador de almacenamiento)
DOCUMENT_LOCAL_ROOT=media/documents       (solo LocalStorage)
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...             (solo servidor)
SUPABASE_ANON_KEY=...                     (si se necesita anon; la app usa service role)
```

---

## 9. Migración de `VehicleDocument`

- **Data migration**: por cada `VehicleDocument` existente, crear `Document` con `tipo` = DocumentType `soat` o `tecnomecanica` según corresponda, `fecha_vencimiento` copiada, `nombre_archivo`/`storage_path` derivados (el archivo físico no existe aún en Storage → `storage_path` apunta a un path simbólico o se deja vacío con nota). 

**Decisión operativa (fijada)**: como los registros `VehicleDocument` actuales **no tienen archivo físico** (solo fecha de vencimiento), la data migration crea los `Document` con estado `vigente`, `storage_path` generado, `tamano=0` y `nombre_archivo` derivado, y marca un booleano `storage_path` apuntando a un archivo inexistente. El panel mostrará estos documentos como "registrados sin archivo" (con su fecha de vencimiento y semáforo de alerta) hasta que se reemplacen por una subida real vía el flujo normal de subida/reemplazo. Esta decisión se implementa y documenta en el README.

- `alertas_vencimiento()` (apps.flota.services) se reimplementa para leer de `Document` (vehículos), conservando la misma firma y forma de dict que usa `dashboard_vencimientos`, para no romper el dashboard.
- El modelo `VehicleDocument` se deja en `apps.flota` sin uso nuevo (no se elimina para no romper migraciones históricas; se marca obsoleto en docstring).

---

## 10. README

Crear `README.md` en la raíz con:
- Qué es la app y sus módulos.
- Requisitos y setup local (venv, migrate, runserver).
- Variables de entorno (incluidas las documentales).
- **Configuración de Supabase Storage**: crear bucket privado `documents`, variables `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`, SQL de RLS/Storage Policies recomendado.
- Backend intercambiable local/supabase.
- Sección destacada **"Arquitectura extensible"**: el módulo documental ya soporta asociar documentos a operaciones, boletas, facturas, relaciones de cobro y soportes de pago simplemente creando un `DocumentType` para esa entidad (via contenttypes) — sin migraciones de estructura. Enfatizar que esas asociaciones específicas no se han desarrollado aún.

---

## 11. Alcance

**Incluido:**
- Tipos documentales configurables (vehicle/driver), seed inicial.
- `Document` genérico con GenericForeignKey.
- `DocumentAudit`.
- Backend LocalStorage + SupabaseStorage, intercambiable.
- Subida, ver, descargar (signed URLs), reemplazar. **Sin compartición externa** (decisión del cliente).
- Alertas de vencimiento (vehículos) + NO CARGADO (ambos).
- Panel documental + fichas de vehículo/conductor.
- Flujo de desactivación de conductor.
- Migración de `VehicleDocument`.
- Indicador de almacenamiento (suma de `tamano`, % del límite `DOCUMENT_STORAGE_LIMIT` default 1 GB).
- README con RLS y arquitectura extensible.

**Excluido (futuro, documentado en README):**
- Asociaciones reales a operaciones/boletas/facturas/soportes de pago (estructura lista, sin desarrollo).
- OCR / IA / extracción automática de datos.
- Notificaciones por email/WhatsApp.
- Firma electrónica.

---

## 12. Criterios de aceptación

1. Se puede cargar un SOAT a un vehículo (PDF ≤10 MB), verlo en el navegador (el lector de PDF permite descargarlo) y descargarlo con nombre `SOAT_ABC123_2027.pdf`. No existe botón "Compartir" ni enlace temporal para terceros.
2. Cargar un SOAT nuevo reemplaza el anterior: el anterior queda `reemplazado` en BD, su archivo se borra del Storage, y la auditoría registra archivo_anterior/archivo_nuevo.
3. Si la subida falla, el documento anterior permanece intacto.
4. Un vehículo con SOAT a 24 días muestra "⚠️ SOAT ABC123 vence en 24 días."; con técnico-mecánica vencida muestra "🔴 Técnico-mecánica DEF456 vencida."; un conductor sin licencia muestra "⚪ Licencia de Juan Pérez no cargada."
5. Desactivar un conductor muestra la confirmación del §15; al confirmar, el conductor queda INACTIVO, sus documentos personales se borran del Storage, y su historial (turnos, nómina, operaciones) permanece.
6. El dashboard de vencimientos existente sigue funcionando leyendo del nuevo modelo.
7. En dev/tests funciona con LocalStorage sin credenciales de Supabase; en prod usa SupabaseStorage según `.env`.
