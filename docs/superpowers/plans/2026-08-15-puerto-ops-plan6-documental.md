# Plan 6 — Módulo de Gestión Documental

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar el expediente documental digital de vehículos y conductores: tipos documentales configurables, modelo genérico `Document` (GenericForeignKey), auditoría, backend de storage intercambiable (LocalStorage dev/tests + SupabaseStorage prod), subida/ver/descargar/reemplazo seguro, alertas de vencimiento (solo vehículos) y estado NO CARGADO (ambos), panel documental, fichas de vehículo/conductor, y flujo de desactivación de conductor. Migrar `VehicleDocument` al nuevo modelo. **Sin compartición externa** (decisión del cliente).

**Architecture:** Django 5.2 monolítico. Nueva app `apps/documentos`. `DocumentType` (configuración), `Document` (genérico con `GenericForeignKey` sobre contenttypes), `DocumentAudit` (inborrable). Backend de storage definido por interfaz `StorageBackend` con dos implementaciones: `LocalStorage` (carpeta local, dev/tests, sin credenciales) y `SupabaseStorage` (supabase-py, bucket privado `documents`). Servicios en `apps/documentos/services.py` para carga/reemplazo/alertas/desactivación. `alertas_vencimiento()` de `apps.flota` se reimplementa sobre `Document`. Vistas `@login_required`.

**Tech Stack:** Django 5.2, supabase-py v2 (nuevo en requirements), contenttypes (django.contrib.contenttypes, ya activo), HTMX, CSS puro con tokens. Reutiliza `AuditMixin` de `apps.core`, `Vehicle` de `apps.flota`, `Driver` de `apps.conductores`.

**Spec de referencia:** `docs/superpowers/specs/2026-08-15-gestion-documental-design.md`. Planes 1-5 completados (128/128 tests, HEAD aa91618).

## Global Constraints

- Zona `America/Bogota`. Todos los modelos heredan `AuditMixin` (created/updated + history).
- `Document` usa `GenericForeignKey` (contenttypes): `entity_type` FK ContentType + `entity_id` + `entity`.
- Bucket privado `documents`; solo el backend accede con service role key (nunca expuesta).
- **Sin compartición externa**: no hay botón "Compartir", no hay enlaces temporales para terceros. "Ver" abre el PDF en el navegador (lector nativo); "Descargar" genera signed URL breve.
- Signed URLs con expiración configurable por `.env`: `DOCUMENT_SIGNED_URL_EXPIRES` (default 300 s).
- `DOCUMENT_STORAGE_BACKEND=local|supabase` (default local). `LocalStorage` en dev/tests.
- Subida: extensiones `pdf,jpg,jpeg,png`; tamaño ≤ `DOCUMENT_MAX_SIZE` (default 10 MB). Nombre visible generado por la app: `{TIPO}_{identificador}_{año}.{ext}` (ej. `SOAT_ABC123_2027.pdf`); `storage_path` físico con UUID.
- Reemplazo seguro: subir nuevo → confirmar (`existe()`) → registrar nuevo → marcar anterior `reemplazado` → borrar archivo anterior → auditoría. Nunca borrar antes de confirmar la subida.
- Alertas de vencimiento: **solo vehículos**. `DOCUMENT_ALERT_DAYS` (default 30). Estados: VIGENTE 🟢 / PRÓXIMO 🟡 / VENCIDO 🔴. Estado **NO CARGADO** ⚪ para documentos obligatorios faltantes, en vehículos y conductores.
- `DocumentAudit` nunca se elimina; registra `carga`, `reemplazo`, `borrado`.
- Desactivar conductor: confirmación exacta del §15 → `Driver.estado=INACTIVO` → borra del Storage documentos personales según política → conserva historial y auditoría.
- Migración de `VehicleDocument`: data migration crea `Document` vigentes con `storage_path` generado, `tamano=0` y `nombre_archivo` derivado (archivo físico inexistente → se muestran "registrados sin archivo" hasta reemplazo). `alertas_vencimiento()` de flota se reimplementa sobre `Document`.
- No se elimina el modelo `VehicleDocument` (para no romper migraciones históricas); se marca obsoleto en docstring.
- Git SOLO LOCAL (sin remoto). Cada task termina con tests en verde y commit local.
- Idioma español (es-co).

---

### Task 1: App documentos — DocumentType con seed

**Files:**
- Create: `apps/documentos/__init__.py`
- Create: `apps/documentos/apps.py`
- Create: `apps/documentos/models.py`
- Create: `apps/documentos/admin.py`
- Create: `apps/documentos/tests/__init__.py`
- Create: `apps/documentos/tests/test_models.py`
- Create: `apps/documentos/management/__init__.py`
- Create: `apps/documentos/management/commands/__init__.py`
- Create: `apps/documentos/management/commands/setup_document_types.py`
- Create: `apps/documentos/tests/test_commands.py`
- Modify: `config/settings/base.py` (añadir `"apps.documentos"` a INSTALLED_APPS)
- Modify: `requirements.txt` (añadir `supabase==2.13.0` — se instalará en la Task 4)

**Interfaces:**
- Consumes: `apps.core.models.AuditMixin`, `django.contrib.contenttypes.models.ContentType`.
- Produces:
  - `class DocumentType(AuditMixin)`: campos `nombre`, `codigo` (unique), `entity_type` FK ContentType, `requires_expiration`, `requires_issue_date`, `allow_multiple`, `replace_previous`, `keep_history`, `is_required`, `activo`. Constantes de entity: `ENTITY_VEHICLE="vehicle"`, `ENTITY_DRIVER="driver"` (no son campos del modelo — se usan como helpers para resolver ContentType). `__str__` → nombre.
  - Comando `python manage.py setup_document_types` → crea los 6 tipos documentales (soat, tecnomecanica, tarjeta_propiedad, cedula, licencia, curso) idempotente.
  - Helper en models: `def content_type_vehicle()`, `def content_type_driver()` en `apps/documentos/models.py` o en services — decidir en models como funciones módulo para reuso.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/documentos/tests/test_models.py`:

```python
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.documentos.models import (
    DocumentType,
    content_type_driver,
    content_type_vehicle,
)
from apps.conductores.models import Driver
from apps.flota.models import Vehicle


class DocumentTypeTests(TestCase):
    def test_creation_y_str(self):
        ct = content_type_vehicle()
        tipo = DocumentType.objects.create(nombre="SOAT", codigo="soat", entity_type=ct)
        self.assertEqual(str(tipo), "SOAT")
        self.assertTrue(tipo.activo)
        self.assertFalse(tipo.requires_expiration)

    def test_codigo_unique(self):
        from django.db import IntegrityError

        ct = content_type_vehicle()
        DocumentType.objects.create(nombre="SOAT", codigo="soat", entity_type=ct)
        with self.assertRaises(IntegrityError):
            DocumentType.objects.create(nombre="SOAT 2", codigo="soat", entity_type=ct)

    def test_content_type_vehicle_apunta_a_vehicle(self):
        self.assertEqual(content_type_vehicle().model_class(), Vehicle)

    def test_content_type_driver_apunta_a_driver(self):
        self.assertEqual(content_type_driver().model_class(), Driver)
```

Crear `apps/documentos/tests/test_commands.py`:

```python
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
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.documentos.tests -v 2`
Expected: FAIL — `ModuleNotFoundError: apps.documentos.models`.

- [ ] **Step 3: Registrar la app, crear modelo y comando**

En `config/settings/base.py`, añadir `"apps.documentos",` después de `"apps.dashboard",`.

Crear `apps/documentos/__init__.py` (vacío), `apps/documentos/apps.py`:

```python
from django.apps import AppConfig


class DocumentosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.documentos"
```

Crear `apps/documentos/models.py`:

```python
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.models import AuditMixin
from apps.conductores.models import Driver
from apps.flota.models import Vehicle


def content_type_vehicle():
    return ContentType.objects.get_for_model(Vehicle)


def content_type_driver():
    return ContentType.objects.get_for_model(Driver)


class DocumentType(AuditMixin):
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, unique=True)
    entity_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, related_name="document_types"
    )
    requires_expiration = models.BooleanField(default=False)
    requires_issue_date = models.BooleanField(default=False)
    allow_multiple = models.BooleanField(default=False)
    replace_previous = models.BooleanField(default=False)
    keep_history = models.BooleanField(default=True)
    is_required = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tipo de documento"
        verbose_name_plural = "Tipos de documento"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
```

Crear `apps/documentos/admin.py`:

```python
from django.contrib import admin

from apps.documentos.models import DocumentType


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "entity_type", "requires_expiration", "replace_previous", "is_required", "activo")
    list_filter = ("entity_type", "activo")
    search_fields = ("nombre", "codigo")
```

Crear `apps/documentos/management/commands/setup_document_types.py`:

```python
from django.core.management.base import BaseCommand

from apps.documentos.models import DocumentType, content_type_driver, content_type_vehicle


class Command(BaseCommand):
    help = "Crea o actualiza los tipos documentales iniciales."

    TIPOS = [
        {
            "codigo": "soat",
            "nombre": "SOAT",
            "entity": content_type_vehicle,
            "requires_expiration": True,
            "requires_issue_date": True,
            "replace_previous": True,
            "allow_multiple": False,
            "keep_history": False,
            "is_required": True,
        },
        {
            "codigo": "tecnomecanica",
            "nombre": "Técnico-mecánica",
            "entity": content_type_vehicle,
            "requires_expiration": True,
            "requires_issue_date": True,
            "replace_previous": True,
            "allow_multiple": False,
            "keep_history": False,
            "is_required": True,
        },
        {
            "codigo": "tarjeta_propiedad",
            "nombre": "Tarjeta de propiedad",
            "entity": content_type_vehicle,
            "requires_expiration": False,
            "requires_issue_date": True,
            "replace_previous": True,
            "allow_multiple": False,
            "keep_history": False,
            "is_required": True,
        },
        {
            "codigo": "cedula",
            "nombre": "Cédula",
            "entity": content_type_driver,
            "requires_expiration": False,
            "requires_issue_date": True,
            "replace_previous": True,
            "allow_multiple": False,
            "keep_history": False,
            "is_required": True,
        },
        {
            "codigo": "licencia",
            "nombre": "Licencia de conducción",
            "entity": content_type_driver,
            "requires_expiration": True,
            "requires_issue_date": True,
            "replace_previous": True,
            "allow_multiple": False,
            "keep_history": False,
            "is_required": True,
        },
        {
            "codigo": "curso",
            "nombre": "Curso",
            "entity": content_type_driver,
            "requires_expiration": False,
            "requires_issue_date": True,
            "replace_previous": False,
            "allow_multiple": True,
            "keep_history": True,
            "is_required": False,
        },
    ]

    def handle(self, *args, **options):
        for data in self.TIPOS:
            entity = data["entity"]()
            defaults = {k: v for k, v in data.items() if k not in ("codigo", "entity")}
            obj, created = DocumentType.objects.update_or_create(
                codigo=data["codigo"], entity_type=entity, defaults=defaults
            )
            action = "creado" if created else "actualizado"
            self.stdout.write(self.style.SUCCESS(f"Tipo '{obj.codigo}' {action}"))
```

- [ ] **Step 4: Migraciones y verificación**

```bash
python manage.py makemigrations documentos
python manage.py migrate
python manage.py test apps.documentos.tests -v 2
```

Expected: PASS (8 tests). Nota: `requires_issue_date` y `allow_multiple` con valores por defecto se pasan en defaults; verificar que `curso.keep_history=True` pase.

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "feat(documentos): tipos documentales configurables con seed"
```

---

### Task 2: Modelos Document y DocumentAudit

**Files:**
- Modify: `apps/documentos/models.py` (añadir Document, DocumentAudit)
- Create: `apps/documentos/tests/test_document.py`

**Interfaces:**
- Consumes: `DocumentType` (Task 1), `Vehicle`, `Driver`, `django.contrib.contenttypes.fields.GenericForeignKey/GenericRelation`.
- Produces:
  - `class Document(AuditMixin)`:
    - `entity_type` FK ContentType, `entity_id` PositiveIntegerField, `entity` GenericForeignKey.
    - `tipo` FK DocumentType related_name="documentos", `nombre_archivo` CharField(255), `storage_path` CharField(500, unique), `extension` CharField(10), `mime_type` CharField(100), `tamano` PositiveBigIntegerField default 0, `fecha_expedicion` DateField null/blank, `fecha_vencimiento` DateField null/blank, `estado` CharField(20) choices (`vigente`/`reemplazado`, default `vigente`), `cargado_por` FK auth.User (SET_NULL, null), `cargado_en` DateTimeField auto_now_add.
    - `__str__` → nombre_archivo.
    - `@property es_personal` → bool: `entity_type == content_type_driver()` (para el flujo de desactivación).
  - `class DocumentAudit(AuditMixin)`:
    - `usuario` FK auth.User (SET_NULL, null), `accion` CharField(20) choices (`carga`/`reemplazo`/`borrado`), `entity_type` FK ContentType, `entity_id` PositiveIntegerField, `tipo` CharField(100) (snapshot), `archivo_anterior` CharField(500) blank, `archivo_nuevo` CharField(500) blank, `detalle` TextField blank.
    - `__str__` → `f"{accion} {tipo}"`.
  - `GenericRelation` en Vehicle y Driver: en `Vehicle` añadir `documentos_doc = GenericRelation("documentos.Document", related_query_name="vehicle_doc")` y en `Driver` similar (`related_query_name="driver_doc"`). Esto permite `vehicle.documentos_doc.all()`.
  - Helper `def documentos_vigentes_entidad(entidad, tipo=None) -> QuerySet[Document]` en services (se define aquí o en Task 3 — definir en services en Task 3; aquí solo los modelos).

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/documentos/tests/test_document.py`:

```python
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from apps.documentos.models import Document, DocumentAudit, DocumentType
from apps.conductores.models import Driver
from apps.flota.models import Vehicle


class DocumentTests(TestCase):
    def setUp(self):
        from apps.documentos.management.commands.setup_document_types import Command as C

        C().handle()
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123456789")
        self.soat = DocumentType.objects.get(codigo="soat")
        self.cedula = DocumentType.objects.get(codigo="cedula")

    def _doc(self, tipo, entidad, **kwargs):
        defaults = dict(
            tipo=tipo,
            nombre_archivo="SOAT_ABC123_2027.pdf",
            storage_path=f"vehicles/ABC123/soat/{uuid.uuid4()}.pdf",
            extension="pdf",
            mime_type="application/pdf",
            tamano=1024,
            fecha_expedicion=date(2027, 1, 1),
        )
        defaults.update(kwargs)
        return Document.objects.create(entity=entidad, **defaults)

    def test_creacion_con_entity(self):
        doc = self._doc(self.soat, self.vehicle)
        self.assertEqual(doc.entity, self.vehicle)
        self.assertEqual(doc.estado, Document.VIGENTE)
        self.assertEqual(str(doc), "SOAT_ABC123_2027.pdf")

    def test_generic_relation_en_vehicle(self):
        self._doc(self.soat, self.vehicle)
        self.assertEqual(self.vehicle.documentos_doc.count(), 1)

    def test_generic_relation_en_driver(self):
        self._doc(self.cedula, self.driver)
        self.assertEqual(self.driver.documentos_doc.count(), 1)

    def test_es_personal_true_para_driver(self):
        doc = self._doc(self.cedula, self.driver)
        self.assertTrue(doc.es_personal)

    def test_es_personal_false_para_vehicle(self):
        doc = self._doc(self.soat, self.vehicle)
        self.assertFalse(doc.es_personal)

    def test_storage_path_unique(self):
        from django.db import IntegrityError

        path = f"vehicles/ABC123/soat/{uuid.uuid4()}.pdf"
        self._doc(self.soat, self.vehicle, storage_path=path)
        with self.assertRaises(IntegrityError):
            self._doc(self.soat, self.vehicle, storage_path=path)


class DocumentAuditTests(TestCase):
    def test_creacion(self):
        usuario = User.objects.create_user(username="maria", password="x")
        audit = DocumentAudit.objects.create(
            usuario=usuario,
            accion=DocumentAudit.REEMPLAZO,
            tipo="soat",
            archivo_anterior="SOAT_ABC123_2026.pdf",
            archivo_nuevo="SOAT_ABC123_2027.pdf",
            detalle="Reemplazo",
        )
        self.assertEqual(str(audit), "reemplazo soat")
        self.assertEqual(audit.archivo_anterior, "SOAT_ABC123_2026.pdf")
```

Nota: `import uuid` al inicio del test; los tests de auditoría no necesitan entity (campos null/blank permitidos). Ajustar `DocumentAudit` para `entity_type`/`entity_id` null/blank.

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.documentos.tests.test_document -v 2`
Expected: FAIL — `ImportError` / atributos ausentes.

- [ ] **Step 3: Implementación mínima**

Añadir a `apps/documentos/models.py`:

```python
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone


class Document(AuditMixin):
    VIGENTE = "vigente"
    REEMPLAZADO = "reemplazado"

    ESTADOS = [
        (VIGENTE, "Vigente"),
        (REEMPLAZADO, "Reemplazado"),
    ]

    entity_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, related_name="documentos_doc"
    )
    entity_id = models.PositiveIntegerField()
    entity = GenericForeignKey("entity_type", "entity_id")

    tipo = models.ForeignKey(
        DocumentType, on_delete=models.PROTECT, related_name="documentos"
    )
    nombre_archivo = models.CharField(max_length=255)
    storage_path = models.CharField(max_length=500, unique=True)
    extension = models.CharField(max_length=10)
    mime_type = models.CharField(max_length=100)
    tamano = models.PositiveBigIntegerField(default=0)
    fecha_expedicion = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=VIGENTE)
    cargado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documentos_cargados",
    )
    cargado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ["-cargado_en"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
        ]

    def __str__(self):
        return self.nombre_archivo

    @property
    def es_personal(self):
        return self.entity_type_id == content_type_driver().id


class DocumentAudit(AuditMixin):
    CARGA = "carga"
    REEMPLAZO = "reemplazo"
    BORRADO = "borrado"

    ACCIONES = [
        (CARGA, "Carga"),
        (REEMPLAZO, "Reemplazo"),
        (BORRADO, "Borrado"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documentos_audit",
    )
    accion = models.CharField(max_length=20, choices=ACCIONES)
    entity_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL
    )
    entity_id = models.PositiveIntegerField(null=True, blank=True)
    tipo = models.CharField(max_length=100)
    archivo_anterior = models.CharField(max_length=500, blank=True, default="")
    archivo_nuevo = models.CharField(max_length=500, blank=True, default="")
    detalle = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Auditoría documental"
        verbose_name_plural = "Auditorías documentales"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.accion} {self.tipo}"
```

Añadir a `Vehicle` en `apps/flota/models.py`:

```python
from django.contrib.contenttypes.fields import GenericRelation
...
    documentos_doc = GenericRelation(
        "documentos.Document", related_query_name="vehicle_doc"
    )
```

Añadir a `Driver` en `apps/conductores/models.py`:

```python
from django.contrib.contenttypes.fields import GenericRelation
...
    documentos_doc = GenericRelation(
        "documentos.Document", related_query_name="driver_doc"
    )
```

IMPORTANTE: las GenericRelation en Vehicle/Driver **no requieren migración** (no crean columnas), pero el import circular: `apps/documentos/models.py` importa de `apps/conductores` y `apps/flota`; las GenericRelation apuntan por string `"documentos.Document"` (lazy), así que no hay problema. Verificar `makemigrations --check` no detecte cambios.

- [ ] **Step 4: Migraciones y verificación**

```bash
python manage.py makemigrations documentos
python manage.py migrate
python manage.py test apps.documentos.tests -v 2
```

Expected: PASS (14 tests). `python manage.py makemigrations --check --dry-run` → "No changes detected" (las GenericRelation no generan migración).

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "feat(documentos): modelos Document y DocumentAudit con GenericForeignKey"
```

---

### Task 3: Backend de storage — interfaz + LocalStorage

**Files:**
- Create: `apps/documentos/storage/__init__.py`
- Create: `apps/documentos/storage/base.py`
- Create: `apps/documentos/storage/local.py`
- Create: `apps/documentos/storage/supabase.py` (stub que levanta `NotImplementedError` si no está supabase instalado — se completa en Task 4)
- Create: `apps/documentos/tests/test_storage_local.py`

**Interfaces:**
- Consumes: `django.conf.settings`.
- Produces:
  - `class StorageBackend` (base): métodos `subir(storage_path, archivo, content_type)`, `descargar(storage_path) -> bytes`, `eliminar(storage_path)`, `signed_url(storage_path, expira_segundos) -> str`, `existe(storage_path) -> bool`.
  - `class LocalStorage(StorageBackend)`:
    - raíz: `settings.DOCUMENT_LOCAL_ROOT` (default `media/documents`), resuelto respecto a BASE_DIR.
    - `subir`: escribe el archivo en `{raiz}/{storage_path}` (crea directorios).
    - `descargar`: lee y devuelve bytes.
    - `eliminar`: borra el archivo si existe.
    - `existe`: `os.path.exists`.
    - `signed_url`: devuelve una ruta de vista local protegida, p. ej. `/documentos/media/{storage_path}` — se define en Task 7 la vista que sirve el archivo desde LocalStorage con `@login_required`. En dev/tests devuelve esa ruta.
  - `def get_storage_backend() -> StorageBackend` en `apps/documentos/storage/__init__.py` — selecciona según `settings.DOCUMENT_STORAGE_BACKEND`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/documentos/tests/test_storage_local.py`:

```python
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
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.documentos.tests.test_storage_local -v 2`
Expected: FAIL — `ModuleNotFoundError: apps.documentos.storage`.

- [ ] **Step 3: Implementación mínima**

Crear `apps/documentos/storage/__init__.py`:

```python
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
```

Crear `apps/documentos/storage/base.py`:

```python
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
```

Crear `apps/documentos/storage/local.py`:

```python
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
```

Crear `apps/documentos/storage/supabase.py` (stub para Task 3):

```python
from apps.documentos.storage.base import StorageBackend


class SupabaseStorage(StorageBackend):
    def __init__(self):
        raise NotImplementedError(
            "SupabaseStorage se implementa en la Task 4 (requiere supabase-py)."
        )
```

Añadir a `config/settings/base.py`:

```python
DOCUMENT_STORAGE_BACKEND = os.environ.get("DOCUMENT_STORAGE_BACKEND", "local")
DOCUMENT_BUCKET = os.environ.get("DOCUMENT_BUCKET", "documents")
DOCUMENT_MAX_SIZE = int(os.environ.get("DOCUMENT_MAX_SIZE", 10485760))
DOCUMENT_ALLOWED_EXTENSIONS = [
    e.strip()
    for e in os.environ.get("DOCUMENT_ALLOWED_EXTENSIONS", "pdf,jpg,jpeg,png").split(",")
    if e.strip()
]
DOCUMENT_ALERT_DAYS = int(os.environ.get("DOCUMENT_ALERT_DAYS", 30))
DOCUMENT_SIGNED_URL_EXPIRES = int(os.environ.get("DOCUMENT_SIGNED_URL_EXPIRES", 300))
DOCUMENT_STORAGE_LIMIT = int(os.environ.get("DOCUMENT_STORAGE_LIMIT", 1073741824))
DOCUMENT_LOCAL_ROOT = os.environ.get("DOCUMENT_LOCAL_ROOT", "media/documents")
```

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.documentos.tests.test_storage_local -v 2`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "feat(documentos): backend de storage con LocalStorage"
```

---

### Task 4: SupabaseStorage y dependencia supabase-py

**Files:**
- Modify: `requirements.txt` (añadir `supabase==2.13.0`)
- Modify: `apps/documentos/storage/supabase.py` (implementación real)
- Modify: `config/settings/base.py` (añadir SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
- Create: `apps/documentos/tests/test_storage_supabase.py` (mock, sin red)

**Interfaces:**
- Consumes: `supabase.create_client`, `settings.SUPABASE_URL`, `settings.SUPABASE_SERVICE_ROLE_KEY`, `settings.DOCUMENT_BUCKET`.
- Produces: `SupabaseStorage(StorageBackend)`:
  - `__init__`: `self.client = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)`; `self.bucket = self.client.storage.from_(DOCUMENT_BUCKET)`.
  - `subir(storage_path, archivo, content_type)`: `self.bucket.upload(path, archivo, {"content-type": content_type})`.
  - `descargar`: `self.bucket.download(path)` → bytes.
  - `eliminar`: `self.bucket.remove([path])`.
  - `existe`: `self.bucket.get_public_url(path)` no sirve (bucket privado); mejor `self.bucket.info(path)` o envolver `descargar` en try/except → bool. Usar `try: self.descargar(path); return True except: return False`.
  - `signed_url(storage_path, expira_segundos)`: `self.bucket.create_signed_url(path, expira_segundos)` → dict con `signedURL`.
- La URL anónima/service role se pasa como parámetro; el backend solo se instancia si `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` están definidos (si faltan en prod → `ImproperlyConfigured`).

- [ ] **Step 1: Instalar supabase y escribir test con mock**

Instalar:

```bash
pip install supabase==2.13.0
```

Actualizar `requirements.txt`:

```
supabase==2.13.0
```

Crear `apps/documentos/tests/test_storage_supabase.py`:

```python
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
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.documentos.tests.test_storage_supabase -v 2`
Expected: FAIL — `ModuleNotFoundError` / `NotImplementedError` del stub.

- [ ] **Step 3: Implementación mínima**

Reemplazar `apps/documentos/storage/supabase.py`:

```python
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
```

Añadir a `config/settings/base.py`:

```python
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
```

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.documentos.tests.test_storage_supabase -v 2`
Expected: PASS (3 tests). Los tests usan mock, no red.

- [ ] **Step 5: Suite completa**

Run: `python manage.py test -v 2`
Expected: PASS (~136). `python manage.py check` limpio.

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "feat(documentos): SupabaseStorage con signed URLs"
```

---

### Task 5: Servicios documentales — cargar, reemplazar, alertas, desactivar

**Files:**
- Create: `apps/documentos/services.py`
- Create: `apps/documentos/tests/test_services.py`

**Interfaces:**
- Consumes: `Document`, `DocumentType`, `DocumentAudit`, `StorageBackend` (`get_storage_backend`), `Vehicle`, `Driver`, `content_type_vehicle/driver`.
- Produces:
  - `def documentos_vigentes_entidad(entidad, tipo=None) -> QuerySet[Document]`.
  - `def generar_storage_path(tipo: DocumentType, entidad, extension) -> str` — `{ruta_tipo}/{uuid}.{ext}` donde `ruta_tipo = vehicles/{PLACA}/tipo_codigo` o `drivers/{DOCUMENTO}/tipo_codigo`.
  - `def generar_nombre_archivo(tipo, entidad, anio, extension) -> str` — `{TIPO}_{identificador}_{anio}.{ext}` (TIPO en mayúsculas, identificador = placa o documento).
  - `def validar_archivo(tipo, entidad, nombre_archivo, contenido, content_type) -> None` — valida extensión permitida, tamaño ≤ DOCUMENT_MAX_SIZE, tipo aplica a la entidad (entity_type del tipo == ContentType de la entidad), y que las fechas requeridas estén presentes (se valida en la vista/form).
  - `def cargar_documento(tipo, entidad, archivo, content_type, extension, tamano, fecha_expedicion=None, fecha_vencimiento=None, usuario=None) -> Document` — sube a Storage, confirma, crea `Document` vigente, maneja reemplazo (si `replace_previous`), borra anterior, auditoría. Devuelve el nuevo Document.
  - `def reemplazar_documento(documento_anterior, nuevo_archivo, ...) -> Document` — sinónimo de cargar con reemplazo explícito.
  - `def estado_documento(doc) -> str` — `vigente`/`proximo`/`vencido` (solo si `fecha_vencimiento` y entidad es vehicle) → reusa lógica de alertas.
  - `def alertas_vencimiento_documentos() -> list[dict]` — para vehículos: documentos con vencimiento; estados vigente/proximo/vencido.
  - `def documentos_faltantes() -> list[dict]` — tipos obligatorios sin documento vigente por entidad (vehículos y conductores).
  - `def desactivar_conductor(driver, usuario=None) -> int` — marca INACTIVO, borra del Storage los documentos personales vigentes (`es_personal` y `replace_previous` o `estado==vigente`), registra auditoría `borrado`, conserva historial. Devuelve nº de documentos borrados.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/documentos/tests/test_services.py`:

```python
import uuid
from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from apps.documentos.management.commands.setup_document_types import Command as C
from apps.documentos.models import Document, DocumentAudit, DocumentType
from apps.documentos.services import (
    cargar_documento,
    desactivar_conductor,
    documentos_faltantes,
    estado_documento,
    generar_nombre_archivo,
    generar_storage_path,
)
from apps.conductores.models import Driver
from apps.flota.models import Vehicle


@override_settings(DOCUMENT_STORAGE_BACKEND="local")
class CargarDocumentoTests(TestCase):
    def setUp(self):
        C().handle()
        self.usuario = User.objects.create_user(username="maria", password="x")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.soat = DocumentType.objects.get(codigo="soat")

    def test_generar_storage_path(self):
        path = generar_storage_path(self.soat, self.vehicle, "pdf")
        self.assertTrue(path.startswith("vehicles/ABC123/soat/"))
        self.assertTrue(path.endswith(".pdf"))
        self.assertEqual(len(path.split("/")[-1].split(".")[0]), 36)  # uuid

    def test_generar_nombre_archivo(self):
        nombre = generar_nombre_archivo(self.soat, self.vehicle, 2027, "pdf")
        self.assertEqual(nombre, "SOAT_ABC123_2027.pdf")

    def test_cargar_documento_crea_vigente(self):
        doc = cargar_documento(
            tipo=self.soat,
            entidad=self.vehicle,
            archivo=b"%PDF-1.4",
            content_type="application/pdf",
            extension="pdf",
            tamano=1024,
            fecha_expedicion=date(2027, 1, 1),
            fecha_vencimiento=date(2028, 1, 1),
            usuario=self.usuario,
        )
        self.assertEqual(doc.estado, Document.VIGENTE)
        self.assertEqual(doc.cargado_por, self.usuario)
        self.assertEqual(self.vehicle.documentos_doc.count(), 1)
        self.assertTrue(DocumentAudit.objects.filter(accion=DocumentAudit.CARGA).exists())

    def test_cargar_documento_reemplaza_anterior(self):
        doc1 = cargar_documento(
            tipo=self.soat, entidad=self.vehicle, archivo=b"%PDF-1.4 v1",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2026, 1, 1), fecha_vencimiento=date(2027, 1, 1),
            usuario=self.usuario,
        )
        path1 = doc1.storage_path
        doc2 = cargar_documento(
            tipo=self.soat, entidad=self.vehicle, archivo=b"%PDF-1.4 v2",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2027, 1, 1), fecha_vencimiento=date(2028, 1, 1),
            usuario=self.usuario,
        )
        doc1.refresh_from_db()
        self.assertEqual(doc1.estado, Document.REEMPLAZADO)
        self.assertEqual(doc2.estado, Document.VIGENTE)
        self.assertNotEqual(path1, doc2.storage_path)
        audit = DocumentAudit.objects.get(accion=DocumentAudit.REEMPLAZO)
        self.assertEqual(audit.archivo_anterior, path1)
        self.assertEqual(audit.archivo_nuevo, doc2.storage_path)

    def test_estado_documento(self):
        from django.utils import timezone
        from datetime import timedelta

        doc = cargar_documento(
            tipo=self.soat, entidad=self.vehicle, archivo=b"%PDF-1.4",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2027, 1, 1),
            fecha_vencimiento=timezone.localdate() + timedelta(days=10),
            usuario=self.usuario,
        )
        self.assertEqual(estado_documento(doc), "proximo")


class FaltantesTests(TestCase):
    def setUp(self):
        C().handle()
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123456789")

    def test_vehicle_sin_soat_aparece_faltante(self):
        faltantes = documentos_faltantes()
        soat_vehicles = [f for f in faltantes if f["tipo"].codigo == "soat"]
        self.assertTrue(soat_vehicles)

    def test_driver_sin_cedula_aparece_faltante(self):
        faltantes = documentos_faltantes()
        cedula_drivers = [f for f in faltantes if f["tipo"].codigo == "cedula"]
        self.assertTrue(cedula_drivers)


class DesactivarConductorTests(TestCase):
    def setUp(self):
        C().handle()
        self.usuario = User.objects.create_user(username="maria", password="x")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123456789")
        self.cedula = DocumentType.objects.get(codigo="cedula")

    @override_settings(DOCUMENT_STORAGE_BACKEND="local")
    def test_desactivar_marca_inactivo_y_borra_documentos(self):
        cargar_documento(
            tipo=self.cedula, entidad=self.driver, archivo=b"datos",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2026, 1, 1), usuario=self.usuario,
        )
        self.assertEqual(self.driver.documentos_doc.count(), 1)
        borrados = desactivar_conductor(self.driver, usuario=self.usuario)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.estado, Driver.INACTIVO)
        self.assertEqual(borrados, 1)
        self.assertEqual(self.driver.documentos_doc.count(), 0)
        self.assertTrue(
            DocumentAudit.objects.filter(accion=DocumentAudit.BORRADO).exists()
        )
```

Nota: `documentos_faltantes` requiere iterar vehículos y conductores y comparar contra tipos obligatorios. Para no depender de datos de otros tests, definir su lógica para que el test `test_vehicle_sin_soat_aparece_faltante` sea determinista: `documentos_faltantes()` devuelve dicts con `tipo` (DocumentType) para las entidades existentes (Vehicle y Driver creadas en el test). En el test del dashboard se filtrará por entidad.

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.documentos.tests.test_services -v 2`
Expected: FAIL — `ModuleNotFoundError: apps.documentos.services`.

- [ ] **Step 3: Implementación mínima**

Crear `apps/documentos/services.py`:

```python
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.documentos.models import Document, DocumentAudit, DocumentType
from apps.documentos.storage import get_storage_backend
from apps.conductores.models import Driver
from apps.flota.models import Vehicle


def documentos_vigentes_entidad(entidad, tipo=None):
    qs = Document.objects.filter(entity_id=entidad.pk, estado=Document.VIGENTE)
    if tipo is not None:
        qs = qs.filter(tipo=tipo)
    return qs


def generar_storage_path(tipo, entidad, extension):
    if isinstance(entidad, Vehicle):
        prefijo = f"vehicles/{entidad.placa}/{tipo.codigo}"
    elif isinstance(entidad, Driver):
        prefijo = f"drivers/{entidad.documento}/{tipo.codigo}"
    else:
        raise ValidationError("Entidad no soportada para documentos.")
    return f"{prefijo}/{uuid.uuid4()}.{extension}"


def generar_nombre_archivo(tipo, entidad, anio, extension):
    if isinstance(entidad, Vehicle):
        identificador = entidad.placa
    elif isinstance(entidad, Driver):
        identificador = entidad.documento
    else:
        raise ValidationError("Entidad no soportada para documentos.")
    return f"{tipo.codigo.upper()}_{identificador}_{anio}.{extension}"


def _ruta_tipo_entidad(tipo, entidad):
    if isinstance(entidad, Vehicle):
        return f"vehicles/{entidad.placa}/{tipo.codigo}"
    if isinstance(entidad, Driver):
        return f"drivers/{entidad.documento}/{tipo.codigo}"
    raise ValidationError("Entidad no soportada.")


def validar_archivo(tipo, entidad, nombre, contenido, content_type):
    ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if ext not in settings.DOCUMENT_ALLOWED_EXTENSIONS:
        raise ValidationError(f"Extensión '{ext}' no permitida.")
    if len(contenido) > settings.DOCUMENT_MAX_SIZE:
        raise ValidationError(
            f"El archivo supera el máximo de {settings.DOCUMENT_MAX_SIZE // 1048576} MB."
        )
    entidad_ct = tipo.entity_type
    if not isinstance(entidad, entidad_ct.model_class()):
        raise ValidationError("El tipo documental no aplica a esta entidad.")
    return ext


def cargar_documento(
    tipo,
    entidad,
    archivo,
    content_type,
    extension,
    tamano,
    fecha_expedicion=None,
    fecha_vencimiento=None,
    usuario=None,
):
    if tipo.requires_issue_date and not fecha_expedicion:
        raise ValidationError("Este tipo de documento requiere fecha de expedición.")
    if tipo.requires_expiration and not fecha_vencimiento:
        raise ValidationError("Este tipo de documento requiere fecha de vencimiento.")

    contenido = archivo.read() if hasattr(archivo, "read") else archivo
    extension = extension.lower()
    if extension not in settings.DOCUMENT_ALLOWED_EXTENSIONS:
        raise ValidationError(f"Extensión '{extension}' no permitida.")
    if len(contenido) > settings.DOCUMENT_MAX_SIZE:
        raise ValidationError(
            f"El archivo supera el máximo de {settings.DOCUMENT_MAX_SIZE // 1048576} MB."
        )

    storage = get_storage_backend()
    storage_path = generar_storage_path(tipo, entidad, extension)
    anio = (fecha_vencimiento or fecha_expedicion or timezone.localdate()).year
    nombre_archivo = generar_nombre_archivo(tipo, entidad, anio, extension)

    storage.subir(storage_path, contenido, content_type)
    if not storage.existe(storage_path):
        raise ValidationError("La subida al almacenamiento falló; el documento anterior queda intacto.")

    with transaction.atomic():
        anterior = None
        if tipo.replace_previous:
            anterior = (
                Document.objects.filter(
                    entity_id=entidad.pk,
                    entity_type=tipo.entity_type,
                    tipo=tipo,
                    estado=Document.VIGENTE,
                )
                .exclude(storage_path=storage_path)
                .first()
            )
        doc = Document.objects.create(
            entity=entidad,
            tipo=tipo,
            nombre_archivo=nombre_archivo,
            storage_path=storage_path,
            extension=extension,
            mime_type=content_type,
            tamano=tamano,
            fecha_expedicion=fecha_expedicion,
            fecha_vencimiento=fecha_vencimiento,
            estado=Document.VIGENTE,
            cargado_por=usuario,
        )
        if anterior is not None:
            anterior.estado = Document.REEMPLAZADO
            anterior.save(update_fields=["estado", "updated_by"])
            storage.eliminar(anterior.storage_path)
            DocumentAudit.objects.create(
                usuario=usuario,
                accion=DocumentAudit.REEMPLAZO,
                entity_type=tipo.entity_type,
                entity_id=entidad.pk,
                tipo=tipo.codigo,
                archivo_anterior=anterior.storage_path,
                archivo_nuevo=storage_path,
                detalle=f"Reemplazo de {tipo.nombre} para {entidad}",
            )
        else:
            DocumentAudit.objects.create(
                usuario=usuario,
                accion=DocumentAudit.CARGA,
                entity_type=tipo.entity_type,
                entity_id=entidad.pk,
                tipo=tipo.codigo,
                archivo_nuevo=storage_path,
                detalle=f"Carga de {tipo.nombre} para {entidad}",
            )
    return doc


def estado_documento(doc):
    if not doc.fecha_vencimiento:
        return Document.VIGENTE
    dias = (doc.fecha_vencimiento - timezone.localdate()).days
    if dias < 0:
        return "vencido"
    if dias <= settings.DOCUMENT_ALERT_DAYS:
        return "proximo"
    return Document.VIGENTE


def alertas_vencimiento_documentos():
    alerts = []
    for doc in (
        Document.objects.filter(
            entity_type=content_type_vehicle(), estado=Document.VIGENTE
        )
        .select_related("tipo", "entity")
        .exclude(fecha_vencimiento__isnull=True)
    ):
        estado = estado_documento(doc)
        if estado in ("proximo", "vencido"):
            alerts.append(
                {
                    "documento": doc,
                    "vehiculo": doc.entity,
                    "tipo": doc.tipo.nombre,
                    "fecha_vencimiento": doc.fecha_vencimiento,
                    "dias": (doc.fecha_vencimiento - timezone.localdate()).days,
                    "estado": estado,
                }
            )
    alerts.sort(key=lambda a: a["dias"])
    return alerts


def documentos_faltantes():
    faltantes = []
    tipos_vehicle = DocumentType.objects.filter(
        entity_type=content_type_vehicle(), is_required=True, activo=True
    )
    for vehicle in Vehicle.objects.all():
        codigos = set(
            Document.objects.filter(
                entity_id=vehicle.pk,
                entity_type=content_type_vehicle(),
                estado=Document.VIGENTE,
            ).values_list("tipo__codigo", flat=True)
        )
        for tipo in tipos_vehicle:
            if tipo.codigo not in codigos:
                faltantes.append(
                    {"entidad": vehicle, "tipo": tipo, "es_personal": False}
                )
    tipos_driver = DocumentType.objects.filter(
        entity_type=content_type_driver(), is_required=True, activo=True
    )
    for driver in Driver.objects.filter(estado=Driver.DISPONIBLE):
        codigos = set(
            Document.objects.filter(
                entity_id=driver.pk,
                entity_type=content_type_driver(),
                estado=Document.VIGENTE,
            ).values_list("tipo__codigo", flat=True)
        )
        for tipo in tipos_driver:
            if tipo.codigo not in codigos:
                faltantes.append(
                    {"entidad": driver, "tipo": tipo, "es_personal": True}
                )
    return faltantes


def desactivar_conductor(driver, usuario=None):
    borrados = 0
    for doc in list(
        Document.objects.filter(
            entity_id=driver.pk,
            entity_type=content_type_driver(),
            estado=Document.VIGENTE,
        ).select_related("tipo")
    ):
        if doc.es_personal:
            get_storage_backend().eliminar(doc.storage_path)
            DocumentAudit.objects.create(
                usuario=usuario,
                accion=DocumentAudit.BORRADO,
                entity_type=doc.entity_type,
                entity_id=driver.pk,
                tipo=doc.tipo.codigo,
                archivo_anterior=doc.storage_path,
                detalle=f"Borrado por desactivación del conductor {driver}",
            )
            doc.delete()
            borrados += 1
    driver.estado = Driver.INACTIVO
    driver.save(update_fields=["estado"])
    return borrados
```

Nota: `content_type_vehicle`/`content_type_driver` se importan de `apps.documentos.models`. Ajustar el import al inicio de services.py.

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.documentos.tests.test_services -v 2`
Expected: PASS. Ajustar la firma de `cargar_documento` si el test de reemplazo falla por `entity_type` mismatch (usar `tipo.entity_type` para el filtro).

- [ ] **Step 5: Suite completa**

Run: `python manage.py test -v 2`
Expected: PASS (~143).

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "feat(documentos): servicios de carga, reemplazo, alertas y desactivacion"
```

---

### Task 6: Migración de VehicleDocument y reimplementación de alertas de flota

**Files:**
- Modify: `apps/flota/services.py` (reimplementar `alertas_vencimiento`)
- Modify: `apps/flota/models.py` (docstring obsoleto en VehicleDocument)
- Create: `apps/documentos/migrations/XXXX_migrar_vehicledocument.py` (data migration)
- Modify: `apps/dashboard/views.py` (si `alertas_vencimiento` mantiene la firma, no cambia nada)
- Modify: `apps/flota/tests/test_services.py` y `apps/flota/tests/test_models.py` (adaptar a Document)
- Modify: `apps/dashboard/tests/test_views.py` (adaptar si usa VehicleDocument)

**Interfaces:**
- Consumes: `Document`, `DocumentType`, `VehicleDocument` (solo para la migración de datos), `alertas_vencimiento_documentos` (servicio nuevo).
- Produces:
  - `apps.flota.services.alertas_vencimiento()` → reimplementada sobre `Document` (vehículos), MISMA firma y MISMA forma de dict que antes: `{documento, vehiculo, tipo, fecha_vencimiento, dias, estado}` con `estado` en `normal|proximo|vencido` (constantes `ESTADO_NORMAL/PROXIMO/VENCIDO` se conservan). Esto mantiene `dashboard_vencimientos` funcionando sin cambios.
  - Data migration `migrar_vehicledocument_a_document`: por cada `VehicleDocument`, crear un `Document` (tipo soat/tecnomecanica, estado vigente, storage_path generado, tamano=0, nombre_archivo derivado, fecha_vencimiento copiada). Reversible: borra los `Document` creados.
  - `DocumentType` soat/tecnomecanica deben existir antes de la data migration → la data migration depende de que `setup_document_types` se haya corrido o se invoca dentro de la migración. **Decisión**: la data migration crea los DocumentType si no existen (llama `Command().handle()` dentro de `RunPython`), garantizando orden.

- [ ] **Step 1: Escribir el test que falla**

Modificar `apps/flota/tests/test_services.py` para que use `Document`:

```python
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.documentos.management.commands.setup_document_types import Command as C
from apps.documentos.models import Document, DocumentType
from apps.documentos.services import cargar_documento
from apps.flota.models import Vehicle
from apps.flota.services import (
    ESTADO_NORMAL,
    ESTADO_PROXIMO,
    ESTADO_VENCIDO,
    alertas_vencimiento,
    documento_estado,
)


class DocumentoEstadoTests(TestCase):
    def setUp(self):
        C().handle()
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.soat = DocumentType.objects.get(codigo="soat")

    def _doc(self, vencimiento):
        return cargar_documento(
            tipo=self.soat, entidad=self.vehicle, archivo=b"%PDF-1.4",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=timezone.localdate(),
            fecha_vencimiento=vencimiento,
        )

    def test_normal_cuando_mas_de_30_dias(self):
        doc = self._doc(timezone.localdate() + timedelta(days=31))
        self.assertEqual(documento_estado(doc), ESTADO_NORMAL)

    def test_proximo_dentro_de_30_dias(self):
        doc = self._doc(timezone.localdate() + timedelta(days=10))
        self.assertEqual(documento_estado(doc), ESTADO_PROXIMO)

    def test_vencido(self):
        doc = self._doc(timezone.localdate() - timedelta(days=1))
        self.assertEqual(documento_estado(doc), ESTADO_VENCIDO)


class AlertasVencimientoTests(TestCase):
    def setUp(self):
        C().handle()
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.soat = DocumentType.objects.get(codigo="soat")
        self.tecno = DocumentType.objects.get(codigo="tecnomecanica")

    def _cargar(self, tipo, vencimiento):
        cargar_documento(
            tipo=tipo, entidad=self.vehicle, archivo=b"%PDF-1.4",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=timezone.localdate(),
            fecha_vencimiento=vencimiento,
        )

    def test_alertas_solo_proximo_y_vencido(self):
        self._cargar(self.soat, timezone.localdate() + timedelta(days=60))
        self._cargar(self.tecno, timezone.localdate() + timedelta(days=10))
        alerts = alertas_vencimiento()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["estado"], ESTADO_PROXIMO)

    def test_alertas_ordenadas_por_dias(self):
        self._cargar(self.soat, timezone.localdate() + timedelta(days=15))
        self._cargar(self.tecno, timezone.localdate() - timedelta(days=3))
        alerts = alertas_vencimiento()
        days = [a["dias"] for a in alerts]
        self.assertEqual(days, sorted(days))
        self.assertEqual(alerts[0]["estado"], ESTADO_VENCIDO)
```

Nota: `documento_estado(doc)` en `apps.flota.services` se reimplementa para `doc` de tipo `Document`. Mantener la misma firma.

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.flota.tests.test_services -v 2`
Expected: FAIL — `documento_estado`/`alertas_vencimiento` usan `VehicleDocument`.

- [ ] **Step 3: Reimplementar flota.services**

Reemplazar `apps/flota/services.py`:

```python
from django.utils import timezone

from apps.documentos.models import Document

ALERT_DAYS = 30
ESTADO_NORMAL = "normal"
ESTADO_PROXIMO = "proximo"
ESTADO_VENCIDO = "vencido"


def documento_estado(doc):
    if not doc.fecha_vencimiento:
        return ESTADO_NORMAL
    dias = (doc.fecha_vencimiento - timezone.localdate()).days
    if dias < 0:
        return ESTADO_VENCIDO
    if dias <= ALERT_DAYS:
        return ESTADO_PROXIMO
    return ESTADO_NORMAL


def alertas_vencimiento():
    alerts = []
    for doc in (
        Document.objects.select_related("tipo", "entity")
        .filter(entity_type__model="vehicle", estado=Document.VIGENTE)
        .exclude(fecha_vencimiento__isnull=True)
    ):
        estado = documento_estado(doc)
        if estado in (ESTADO_PROXIMO, ESTADO_VENCIDO):
            alerts.append(
                {
                    "documento": doc,
                    "vehiculo": doc.entity,
                    "tipo": doc.tipo.nombre,
                    "fecha_vencimiento": doc.fecha_vencimiento,
                    "dias": (doc.fecha_vencimiento - timezone.localdate()).days,
                    "estado": estado,
                }
            )
    alerts.sort(key=lambda a: a["dias"])
    return alerts
```

Nota: `entity_type__model="vehicle"` usa el atributo `model` del ContentType (nombre en minúsculas del modelo Django). `Vehicle` tiene `model="vehicle"` por convención (nombre de clase en minúsculas). Si no, usar `entity_type=content_type_vehicle()`. Preferir importar `content_type_vehicle` de `apps.documentos.models` para exactitud.

- [ ] **Step 4: Data migration**

Generar la migración vacía y completarla:

```bash
python manage.py makemigrations documentos --empty -n migrar_vehicledocument_a_document
```

Completar la migración con `RunPython`:

```python
import uuid

from django.db import migrations


def migrar(apps, schema_editor):
    VehicleDocument = apps.get_model("flota", "VehicleDocument")
    Document = apps.get_model("documentos", "Document")
    DocumentType = apps.get_model("documentos", "DocumentType")
    ContentType = apps.get_model("contenttypes", "ContentType")

    # Asegurar tipos documentales
    from apps.documentos.management.commands.setup_document_types import Command as C

    C().handle()

    vt = ContentType.objects.get_for_model(VehicleDocument._meta.get_field("vehicle").related_model)
    vehicle_ct = ContentType.objects.get(app_label="flota", model="vehicle")

    for vd in VehicleDocument.objects.all():
        tipo_codigo = "soat" if vd.tipo == "soat" else "tecnomecanica"
        tipo = DocumentType.objects.get(codigo=tipo_codigo)
        placa = vd.vehicle.placa
        anio = vd.fecha_vencimiento.year if vd.fecha_vencimiento else ""
        Document.objects.create(
            entity_type=vehicle_ct,
            entity_id=vd.vehicle_id,
            tipo=tipo,
            nombre_archivo=f"{tipo_codigo.upper()}_{placa}_{anio}.pdf",
            storage_path=f"vehicles/{placa}/{tipo_codigo}/{uuid.uuid4()}.pdf",
            extension="pdf",
            mime_type="application/pdf",
            tamano=0,
            fecha_vencimiento=vd.fecha_vencimiento,
            estado="vigente",
        )


def revertir(apps, schema_editor):
    Document = apps.get_model("documentos", "Document")
    Document.objects.filter(
        entity_type__app_label="flota", entity_type__model="vehicle"
    ).filter(tipo__codigo__in=["soat", "tecnomecanica"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("documentos", "XXXX_anterior"),
        ("flota", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(migrar, revertir),
    ]
```

Nota: el import de `C()` dentro de la migración rompe el patrón "migraciones sin imports de app" (best practice), pero es aceptable aquí dado el alcance; alternativa: duplicar la lógica de seed dentro de la migración. **Preferir duplicar la lógica de seed** (crear los 6 DocumentType con get_or_create) dentro de la migración para evitar imports de app en migraciones. El implementador decide siguiendo las mejores prácticas y documenta.

- [ ] **Step 5: Adaptar tests existentes**

- `apps/flota/tests/test_models.py`: eliminar/adaptar `VehicleDocumentTests` (el modelo queda obsoleto). Sustituir por tests que verifiquen que `VehicleDocument` sigue existiendo (para no romper migraciones) o eliminar la clase y dejar solo `VehicleTests`. **Decisión**: mantener una clase mínima `VehicleDocumentLegacyTests` que crea un `VehicleDocument` y verifica `dias_restantes()` — documenta que es legado.
- `apps/dashboard/tests/test_views.py` `VencimientosDashboardTests`: adaptar para crear `Document` (soat/tecnomecanica) vía `cargar_documento` en vez de `VehicleDocument`.

- [ ] **Step 6: Verificar que pasa**

Run: `python manage.py test apps.flota.tests apps.documentos.tests apps.dashboard.tests.test_views -v 2`
Expected: PASS. Luego suite completa `python manage.py test -v 2`.

- [ ] **Step 7: Commit local**

```bash
git add -A
git commit -m "feat(documentos): migrar VehicleDocument y reimplementar alertas de flota"
```

---

### Task 7: Vistas documentales — fichas, panel, subida, ver, descargar, reemplazo, desactivación

**Files:**
- Create: `apps/documentos/views.py`
- Create: `apps/documentos/urls.py`
- Create: `apps/documentos/forms.py`
- Create: `templates/documentos/panel.html`
- Create: `templates/documentos/ficha_vehicle.html`
- Create: `templates/documentos/ficha_driver.html`
- Create: `templates/documentos/documento_form.html`
- Create: `templates/documentos/reemplazo_confirm.html`
- Create: `templates/documentos/desactivar_confirm.html`
- Create: `apps/documentos/tests/test_views.py`
- Modify: `config/urls.py` (incluir `apps.documentos.urls` bajo prefijo `documentos/`)
- Modify: `templates/base.html` (añadir enlaces de navegación a DOCUMENTOS si aplica — opcional)
- Modify: `static/css/app.css` (estilos de expediente)

**Interfaces:**
- Consumes: `cargar_documento`, `documentos_vigentes_entidad`, `alertas_vencimiento_documentos`, `documentos_faltantes`, `desactivar_conductor`, `get_storage_backend`, `Vehicle`, `Driver`, `DocumentType`.
- Produces:
  - URL namespace `documentos`:
    - `documentos:panel` → panel documental (indicadores, alertas vencimiento, faltantes).
    - `documentos:vehicle` (`vehicle/<int:pk>/`) y `documentos:driver` (`driver/<int:pk>/`) → fichas.
    - `documentos:subir` (`subir/?vehicle=<pk>|driver=<pk>`) → formulario de carga (POST multipart).
    - `documentos:ver` (`<int:pk>/ver/`) → redirect a signed URL (o servir archivo local en dev).
    - `documentos:descargar` (`<int:pk>/descargar/`) → redirect a signed URL con nombre.
    - `documentos:reemplazar` (`<int:pk>/reemplazar/`) → confirmación + POST (usa cargar_documento con el tipo del anterior).
    - `documentos:desactivar_conductor` (`driver/<int:pk>/desactivar/`) → confirmación + POST.
    - `documentos:media` (`media/<path:storage_path>`) → sirve archivo local con `@login_required` (solo LocalStorage, dev/tests).
  - Todas `@login_required`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/documentos/tests/test_views.py`:

```python
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.documentos.management.commands.setup_document_types import Command as C
from apps.documentos.models import Document
from apps.documentos.services import cargar_documento
from apps.conductores.models import Driver
from apps.flota.models import Vehicle


@override_settings(DOCUMENT_STORAGE_BACKEND="local")
class DocumentosViewsTests(TestCase):
    def setUp(self):
        C().handle()
        self.user = User.objects.create_user(username="ana", password="x")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123456789")
        self.client.force_login(self.user)

    def test_panel_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse("documentos:panel"))
        self.assertEqual(response.status_code, 302)

    def test_panel_renderiza(self):
        response = self.client.get(reverse("documentos:panel"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Documentos")

    def test_ficha_vehicle_muestra_documentos(self):
        from apps.documentos.models import DocumentType

        soat = DocumentType.objects.get(codigo="soat")
        cargar_documento(
            tipo=soat, entidad=self.vehicle, archivo=b"%PDF-1.4",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2027, 1, 1), fecha_vencimiento=date(2028, 1, 1),
            usuario=self.user,
        )
        response = self.client.get(reverse("documentos:vehicle", args=[self.vehicle.pk]))
        self.assertContains(response, "ABC123")
        self.assertContains(response, "SOAT")

    def test_subir_documento_via_post(self):
        import io

        soat = self.client.post(
            reverse("documentos:subir") + "?vehicle=" + str(self.vehicle.pk),
            {
                "tipo": "soat",
                "archivo": io.BytesIO(b"%PDF-1.4 datos"),
                "fecha_expedicion": "01/01/2027",
                "fecha_vencimiento": "01/01/2028",
            },
        )
        self.assertEqual(soat.status_code, 302)
        self.assertEqual(self.vehicle.documentos_doc.count(), 1)

    def test_descargar_redirige_a_url(self):
        from apps.documentos.models import DocumentType

        soat = DocumentType.objects.get(codigo="soat")
        doc = cargar_documento(
            tipo=soat, entidad=self.vehicle, archivo=b"%PDF-1.4",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2027, 1, 1), fecha_vencimiento=date(2028, 1, 1),
            usuario=self.user,
        )
        response = self.client.get(reverse("documentos:descargar", args=[doc.pk]))
        self.assertEqual(response.status_code, 302)

    def test_reemplazo_confirmacion_y_post(self):
        from apps.documentos.models import DocumentType

        soat = DocumentType.objects.get(codigo="soat")
        doc = cargar_documento(
            tipo=soat, entidad=self.vehicle, archivo=b"%PDF-1.4 v1",
            content_type="application/pdf", extension="pdf", tamano=10,
            fecha_expedicion=date(2026, 1, 1), fecha_vencimiento=date(2027, 1, 1),
            usuario=self.user,
        )
        url = reverse("documentos:reemplazar", args=[doc.pk])
        get = self.client.get(url)
        self.assertContains(get, "reemplazar")
        import io

        post = self.client.post(
            url,
            {
                "archivo": io.BytesIO(b"%PDF-1.4 v2"),
                "fecha_expedicion": "01/01/2027",
                "fecha_vencimiento": "01/01/2028",
            },
        )
        self.assertEqual(post.status_code, 302)
        doc.refresh_from_db()
        self.assertEqual(doc.estado, "reemplazado")

    def test_desactivar_conductor_via_post(self):
        url = reverse("documentos:desactivar_conductor", args=[self.driver.pk])
        get = self.client.get(url)
        self.assertContains(get, "será marcado como inactivo")
        post = self.client.post(url)
        self.assertEqual(post.status_code, 302)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.estado, Driver.INACTIVO)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.documentos.tests.test_views -v 2`
Expected: FAIL — `NoReverseMatch` para `documentos:panel`.

- [ ] **Step 3: Implementar forms, views y urls**

Crear `apps/documentos/forms.py`:

```python
from django import forms

from apps.documentos.models import DocumentType


class DocumentoForm(forms.Form):
    tipo = forms.ModelChoiceField(
        queryset=DocumentType.objects.filter(activo=True), label="Tipo de documento"
    )
    archivo = forms.FileField(label="Archivo")
    fecha_expedicion = forms.DateField(
        required=False, label="Fecha de expedición",
        input_formats=["%d/%m/%Y", "%Y-%m-%d"],
    )
    fecha_vencimiento = forms.DateField(
        required=False, label="Fecha de vencimiento",
        input_formats=["%d/%m/%Y", "%Y-%m-%d"],
    )

    def __init__(self, *args, **kwargs):
        self.entidad = kwargs.pop("entidad", None)
        super().__init__(*args, **kwargs)
        if self.entidad is not None:
            self.fields["tipo"].queryset = DocumentType.objects.filter(
                entity_type__model=self.entidad.__class__.__name__.lower(),
                activo=True,
            )
```

Nota: el filtro por `entity_type__model` usa el nombre del modelo en minúsculas (`vehicle`, `driver`).

Crear `apps/documentos/views.py`:

```python
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.documentos.forms import DocumentoForm
from apps.documentos.models import Document, DocumentType
from apps.documentos.services import (
    alertas_vencimiento_documentos,
    cargar_documento,
    desactivar_conductor,
    documentos_faltantes,
    documentos_vigentes_entidad,
    generar_nombre_archivo,
)
from apps.documentos.storage import get_storage_backend
from apps.conductores.models import Driver
from apps.flota.models import Vehicle


@login_required
def panel(request):
    vigentes = Document.objects.filter(estado=Document.VIGENTE).count()
    proximos = len([a for a in alertas_vencimiento_documentos() if a["estado"] == "proximo"])
    vencidos = len([a for a in alertas_vencimiento_documentos() if a["estado"] == "vencido"])
    faltantes = documentos_faltantes()
    context = {
        "indicadores": {
            "vigentes": vigentes,
            "proximos": proximos,
            "vencidos": vencidos,
            "faltantes": len(faltantes),
        },
        "alertas": alertas_vencimiento_documentos(),
        "faltantes": faltantes,
    }
    return render(request, "documentos/panel.html", context)


@login_required
def ficha_vehicle(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    context = {
        "vehicle": vehicle,
        "documentos": documentos_vigentes_entidad(vehicle).select_related("tipo"),
    }
    return render(request, "documentos/ficha_vehicle.html", context)


@login_required
def ficha_driver(request, pk):
    driver = get_object_or_404(Driver, pk=pk)
    context = {
        "driver": driver,
        "documentos": documentos_vigentes_entidad(driver).select_related("tipo"),
    }
    return render(request, "documentos/ficha_driver.html", context)


@login_required
def subir(request):
    vehicle = request.GET.get("vehicle")
    driver = request.GET.get("driver")
    entidad = None
    if vehicle:
        entidad = get_object_or_404(Vehicle, pk=vehicle)
    elif driver:
        entidad = get_object_or_404(Driver, pk=driver)

    form = DocumentoForm(request.POST or None, request.FILES or None, entidad=entidad)
    if request.method == "POST" and form.is_valid():
        archivo = form.cleaned_data["archivo"]
        try:
            cargar_documento(
                tipo=form.cleaned_data["tipo"],
                entidad=entidad,
                archivo=archivo,
                content_type=archivo.content_type or "application/octet-stream",
                extension=archivo.name.rsplit(".", 1)[-1].lower(),
                tamano=archivo.size,
                fecha_expedicion=form.cleaned_data.get("fecha_expedicion"),
                fecha_vencimiento=form.cleaned_data.get("fecha_vencimiento"),
                usuario=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            if isinstance(entidad, Vehicle):
                return redirect("documentos:vehicle", pk=entidad.pk)
            return redirect("documentos:driver", pk=entidad.pk)
    return render(request, "documentos/documento_form.html", {"form": form, "entidad": entidad})


@login_required
def ver(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if settings.DOCUMENT_STORAGE_BACKEND == "local":
        return HttpResponseRedirect(
            reverse("documentos:media", kwargs={"storage_path": doc.storage_path})
        )
    url = get_storage_backend().signed_url(doc.storage_path, settings.DOCUMENT_SIGNED_URL_EXPIRES)
    return HttpResponseRedirect(url)


@login_required
def descargar(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if settings.DOCUMENT_STORAGE_BACKEND == "local":
        response = HttpResponse(
            get_storage_backend().descargar(doc.storage_path),
            content_type=doc.mime_type,
        )
        response["Content-Disposition"] = f'attachment; filename="{doc.nombre_archivo}"'
        return response
    url = get_storage_backend().signed_url(doc.storage_path, settings.DOCUMENT_SIGNED_URL_EXPIRES)
    return HttpResponseRedirect(url)


@login_required
def reemplazar(request, pk):
    anterior = get_object_or_404(Document, pk=pk)
    form = DocumentoForm(
        request.POST or None, request.FILES or None, entidad=anterior.entity
    )
    if request.method == "POST" and form.is_valid():
        archivo = form.cleaned_data["archivo"]
        try:
            cargar_documento(
                tipo=anterior.tipo,
                entidad=anterior.entity,
                archivo=archivo,
                content_type=archivo.content_type or "application/octet-stream",
                extension=archivo.name.rsplit(".", 1)[-1].lower(),
                tamano=archivo.size,
                fecha_expedicion=form.cleaned_data.get("fecha_expedicion")
                or anterior.fecha_expedicion,
                fecha_vencimiento=form.cleaned_data.get("fecha_vencimiento")
                or anterior.fecha_vencimiento,
                usuario=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            if isinstance(anterior.entity, Vehicle):
                return redirect("documentos:vehicle", pk=anterior.entity.pk)
            return redirect("documentos:driver", pk=anterior.entity.pk)
    return render(
        request,
        "documentos/reemplazo_confirm.html",
        {"documento": anterior, "form": form},
    )


@login_required
def desactivar_conductor(request, pk):
    driver = get_object_or_404(Driver, pk=pk)
    if request.method == "POST":
        desactivar_conductor(driver, usuario=request.user)
        return redirect("documentos:driver", pk=driver.pk)
    return render(request, "documentos/desactivar_confirm.html", {"driver": driver})


@login_required
def media(request, storage_path):
    if settings.DOCUMENT_STORAGE_BACKEND != "local":
        raise Http404
    storage = get_storage_backend()
    if not storage.existe(storage_path):
        raise Http404
    return HttpResponse(
        storage.descargar(storage_path),
        content_type="application/octet-stream",
    )
```

Crear `apps/documentos/urls.py`:

```python
from django.urls import path

from apps.documentos import views

app_name = "documentos"

urlpatterns = [
    path("", views.panel, name="panel"),
    path("vehicle/<int:pk>/", views.ficha_vehicle, name="vehicle"),
    path("driver/<int:pk>/", views.ficha_driver, name="driver"),
    path("subir/", views.subir, name="subir"),
    path("<int:pk>/ver/", views.ver, name="ver"),
    path("<int:pk>/descargar/", views.descargar, name="descargar"),
    path("<int:pk>/reemplazar/", views.reemplazar, name="reemplazar"),
    path("driver/<int:pk>/desactivar/", views.desactivar_conductor, name="desactivar_conductor"),
    path("media/<path:storage_path>", views.media, name="media"),
]
```

En `config/urls.py`, añadir:

```python
path("documentos/", include("apps.documentos.urls")),
```

- [ ] **Step 4: Crear plantillas**

Crear `templates/documentos/panel.html`:

```html
{% extends "base.html" %}
{% block title %}Gestión documental{% endblock %}
{% block content %}
<p class="eyebrow">Gestión documental</p>
<h1>Documentos</h1>

<div class="kpi-grid">
  <div class="kpi"><span class="kpi-value">{{ indicadores.vigentes }}</span><span class="kpi-label">Vigentes</span></div>
  <div class="kpi"><span class="kpi-value">{{ indicadores.proximos }}</span><span class="kpi-label">Próximos a vencer</span></div>
  <div class="kpi"><span class="kpi-value">{{ indicadores.vencidos }}</span><span class="kpi-label">Vencidos</span></div>
  <div class="kpi"><span class="kpi-value">{{ indicadores.faltantes }}</span><span class="kpi-label">Faltantes</span></div>
</div>

<h2>Alertas de vencimiento</h2>
<table class="table">
  <thead><tr><th>Vehículo</th><th>Documento</th><th>Vencimiento</th><th>Días</th><th>Estado</th></tr></thead>
  <tbody>
  {% for a in alertas %}
    <tr>
      <td><a href="{% url 'documentos:vehicle' a.vehiculo.pk %}">{{ a.vehiculo.placa }}</a></td>
      <td>{{ a.tipo }}</td>
      <td>{{ a.fecha_vencimiento|date:"d/m/Y" }}</td>
      <td>{{ a.dias }}</td>
      <td>
        {% if a.estado == "vencido" %}<span class="tag tag-danger">🔴 Vencido</span>
        {% else %}<span class="tag tag-warn">🟡 Próximo</span>{% endif %}
      </td>
    </tr>
  {% empty %}
    <tr><td colspan="5">Sin alertas de vencimiento.</td></tr>
  {% endfor %}
  </tbody>
</table>

<h2>Documentos faltantes</h2>
<table class="table">
  <thead><tr><th>Entidad</th><th>Tipo</th></tr></thead>
  <tbody>
  {% for f in faltantes %}
    <tr>
      <td>{{ f.entidad }}</td>
      <td><span class="tag">⚪ {{ f.tipo.nombre }}</span></td>
    </tr>
  {% empty %}
    <tr><td colspan="2">No hay documentos obligatorios faltantes.</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
```

Crear `templates/documentos/ficha_vehicle.html`:

```html
{% extends "base.html" %}
{% block title %}Expediente {{ vehicle.placa }}{% endblock %}
{% block content %}
<p class="eyebrow">Expediente del vehículo</p>
<h1>{{ vehicle.placa }}</h1>
<p>{{ vehicle.marca }} {{ vehicle.modelo }} · {{ vehicle.get_estado_display }}</p>

<h2>Documentación</h2>
<a class="btn btn-primary" href="{% url 'documentos:subir' %}?vehicle={{ vehicle.pk }}">+ Agregar documento</a>
<table class="table">
  <thead><tr><th>Tipo</th><th>Vencimiento</th><th>Estado</th><th>Acciones</th></tr></thead>
  <tbody>
  {% for doc in documentos %}
    <tr>
      <td>{{ doc.tipo.nombre }}</td>
      <td>{{ doc.fecha_vencimiento|date:"d/m/Y"|default:"—" }}</td>
      <td>
        {% if doc.fecha_vencimiento %}
          {% if doc.fecha_vencimiento < today %}<span class="tag tag-danger">🔴 Vencido</span>
          {% elif doc.fecha_vencimiento <= alerta %}<span class="tag tag-warn">🟡 Próximo a vencer</span>
          {% else %}<span class="tag tag-ok">🟢 Vigente</span>{% endif %}
        {% else %}<span class="tag tag-ok">🟢 Registrado</span>{% endif %}
      </td>
      <td>
        <a href="{% url 'documentos:ver' doc.pk %}">Ver</a> ·
        <a href="{% url 'documentos:descargar' doc.pk %}">Descargar</a> ·
        <a href="{% url 'documentos:reemplazar' doc.pk %}">Reemplazar</a>
      </td>
    </tr>
  {% empty %}
    <tr><td colspan="4">Sin documentos cargados.</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
```

Nota: para mostrar `today` y `alerta` en la plantilla, la vista `ficha_vehicle` debe pasar `today = timezone.localdate()` y `alerta = today + timedelta(days=DOCUMENT_ALERT_DAYS)`. Ajustar la vista. Alternativa: precalcular el estado en la vista y pasarlo en una lista de dicts. **Preferir precalcular en la vista** (lista de dicts con `doc` y `estado_ui`) para mantener la plantilla simple.

Crear `templates/documentos/ficha_driver.html` (similar, con botón "Desactivar conductor" si `driver.estado != inactivo`).

Crear `templates/documentos/documento_form.html` (formulario §23) y `templates/documentos/reemplazo_confirm.html` (mensaje "Este documento reemplazará el X actual de Y." con [Cancelar] [Reemplazar]) y `templates/documentos/desactivar_confirm.html` (confirmación exacta del §15 con [Cancelar] [Confirmar]).

- [ ] **Step 5: Verificar que pasa**

Run: `python manage.py test apps.documentos.tests.test_views -v 2`
Expected: PASS (7 tests). Ajustar el filtro del form (`entity_type__model`) y el pre-cálculo del estado según lo que falle.

- [ ] **Step 6: Suite completa**

Run: `python manage.py test -v 2`
Expected: PASS (~150). `python manage.py check` limpio.

- [ ] **Step 7: Commit local**

```bash
git add -A
git commit -m "feat(documentos): panel, fichas, subida, ver, descargar, reemplazo y desactivacion"
```

---

### Task 8: README, .env.example e indicador de almacenamiento

**Files:**
- Create: `README.md`
- Modify: `.env.example` (añadir variables documentales)
- Modify: `apps/documentos/services.py` (añadir `indicador_almacenamiento`)
- Create: `apps/documentos/tests/test_storage_indicador.py` (o incluir en test_services)
- Modify: `templates/documentos/panel.html` (mostrar indicador)

**Interfaces:**
- Consumes: `Document` (suma de `tamano`), `settings.DOCUMENT_STORAGE_LIMIT`.
- Produces:
  - `def indicador_almacenamiento() -> dict` — `{"usado": bytes, "limite": bytes, "porcentaje": float, "texto": "1.2 GB / 1 GB"}`. Formatea con humanizar (MB/GB). Solo cuenta documentos con `tamano > 0` (los migrados sin archivo no cuentan).
  - README completo con guía Supabase, RLS SQL, backend intercambiable y sección "Arquitectura extensible".
  - `.env.example` actualizado.

- [ ] **Step 1: Escribir el test que falla**

Añadir a `apps/documentos/tests/test_services.py`:

```python
    def test_indicador_almacenamiento(self):
        from apps.documentos.services import indicador_almacenamiento

        data = indicador_almacenamiento()
        self.assertIn("usado", data)
        self.assertIn("limite", data)
        self.assertIn("porcentaje", data)
        self.assertGreaterEqual(data["porcentaje"], 0.0)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.documentos.tests.test_services -v 2`
Expected: FAIL — `ImportError: cannot import name 'indicador_almacenamiento'`.

- [ ] **Step 3: Implementar el indicador**

Añadir a `apps/documentos/services.py`:

```python
def indicador_almacenamiento():
    usado = (
        Document.objects.filter(estado=Document.VIGENTE, tamano__gt=0)
        .aggregate(total=Sum("tamano"))["total"]
        or 0
    )
    limite = settings.DOCUMENT_STORAGE_LIMIT
    porcentaje = round(usado / limite * 100, 1) if limite else 0.0
    return {
        "usado": usado,
        "limite": limite,
        "porcentaje": porcentaje,
        "texto": f"{_fmt_bytes(usado)} / {_fmt_bytes(limite)}",
    }


def _fmt_bytes(b):
    if b >= 1073741824:
        return f"{b / 1073741824:.1f} GB"
    if b >= 1048576:
        return f"{b / 1048576:.1f} MB"
    if b >= 1024:
        return f"{b / 1024:.0f} KB"
    return f"{b} B"
```

Nota: añadir `from django.db.models import Sum` al import de services.py.

En `templates/documentos/panel.html`, añadir la sección ALMACENAMIENTO con `indicador.texto` y un barra de progreso simple (ancho = porcentaje, color según umbral).

Ajustar la vista `panel` para pasar `indicador = indicador_almacenamiento()`.

- [ ] **Step 4: Crear README y .env.example**

Crear `README.md` con las secciones del §10 del spec, incluida la sección destacada "**Arquitectura extensible**".

Modificar `.env.example` añadiendo:

```
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

- [ ] **Step 5: Verificar que pasa**

Run: `python manage.py test apps.documentos.tests -v 2` y suite completa `python manage.py test -v 2`
Expected: PASS (~151).

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "docs(documentos): README con Supabase y arquitectura extensible"
```

---

## Self-Review del Plan

**Cobertura del spec (Plan 6):**
- `DocumentType` configurable + seed (§5): Task 1. ✔
- `Document` genérico con GenericForeignKey (§4) + GenericRelation en Vehicle/Driver: Task 2. ✔
- `DocumentAudit` inborrable (§7): Task 2. ✔
- Backend intercambiable Local/Supabase (§2, §9): Tasks 3-4. ✔
- Signed URLs sin almacenamiento (§10), sin compartición (§5.4 del spec): Task 4 + Task 7. ✔
- Carga, ver, descargar, reemplazo seguro (§6, §12, §13, §14, §23): Tasks 5, 7. ✔
- Alertas de vencimiento (solo vehículos) + NO CARGADO (ambos) (§17): Task 5. ✔
- Panel documental + fichas (§18, §19, §20): Task 7. ✔
- Desactivación de conductor (§15): Task 5 + Task 7. ✔
- Migración de `VehicleDocument` + reimplementación de `alertas_vencimiento` (§9 del spec): Task 6. ✔
- Indicador de almacenamiento (§21): Task 8. ✔
- README con RLS y arquitectura extensible (§10 del spec): Task 8. ✔

**Fuera de este plan:** asociaciones a operaciones/boletas/facturas/soportes (estructura lista, documentado en README), OCR/IA, notificaciones, firma electrónica, desactivación de vehículo con UI (solo conductor; el vehículo conserva historial y sus documentos se gestionan por política en el flujo normal).

**Placeholders:** ninguno; cada paso contiene código o comandos reales.

**Consistencia de tipos:** `cargar_documento`/`desactivar_conductor`/`documentos_faltantes`/`alertas_vencimiento_documentos`/`indicador_almacenamiento` definidos en services y consumidos por vistas/tests con las mismas firmas. `alertas_vencimiento()` de flota conserva la MISMA firma y forma de dict (documento/vehiculo/tipo/fecha_vencimiento/dias/estado) que usaba con `VehicleDocument`, de modo que `dashboard_vencimientos` no cambia. `GenericRelation` apunta por string a `"documentos.Document"` (lazy), evitando import circular. La data migration crea los `DocumentType` con `get_or_create` (duplicando la lógica de seed dentro de la migración) para respetar las buenas prácticas de migraciones sin imports de app.
