# Plan 2 — Operaciones y turnos

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear el núcleo operativo del sistema: operaciones portuarias (con tarifas congeladas y asignación de mulas), turnos como unidad central (cálculo de horas reales, cumplimiento, valor de turno), novedades asociadas, cancelación/anulación de turnos y detección de doble turno. Incluye vistas funcionales (listado, creación, detalle, registro de turnos) para que la secretaria pueda operar.

**Architecture:** Django 5.2 monolítico. Nueva app `apps/operaciones` con modelos `Operation`, `OperationVehicle`, `Shift`, `Incident`. Servicios en `apps/operaciones/services.py` para reglas de negocio (asignación de mulas, cálculo de horas, doble turno). Vistas basadas en funciones con HTMX para el registro de turnos. El estado de los vehículos se sincroniza con la asignación/finalización de operaciones. No se elimina nada físicamente: todo usa estados.

**Tech Stack:** Django 5.2, HTMX (ya en base.html), auditación con `AuditMixin` de `apps.core`, `IncidentCategory` de `apps.catalogos`, `Vehicle` de `apps.flota`, `Driver` de `apps.conductores`.

**Spec de referencia:** `docs/superpowers/specs/2026-08-15-puerto-ops-design.md` (secciones 5, 6, 7, 11, 13-19). Plan 1 completado: base con `CargoGenerator`, `Port`, `IncidentCategory`, `Vehicle`, `Driver`, mixins y base visual.

## Global Constraints

- Zona horaria `America/Bogota`; `USE_TZ=True` ya activo. Los turnos se registran con datetimes naive de Bogotá: se usa `timezone.make_aware` con la zona activa al guardar. El turno nocturno 18:00→06:00 cruza medianoche; el turno pertenece a la fecha de inicio.
- Moneda COP: `DecimalField(max_digits=14, decimal_places=0)`.
- Horas: `DecimalField(max_digits=5, decimal_places=2)`; cumplimiento `DecimalField(max_digits=5, decimal_places=1)`.
- Todos los modelos de negocio heredan `AuditMixin` (created/updated + history).
- No eliminación física: estados.
- Reglas de negocio clave:
  - Pago al conductor = valor del turno completo si el turno es **realizado**; **cancelado/anulado = $0**, no genera facturación, queda en historial.
  - Facturación (Plan 4) usará horas reales × tarifa; aquí solo se calculan horas y cumplimiento.
  - Turno con horas < meta exige novedad asociada al guardar (validación en servicio `registrar_turno`).
  - Doble turno: mismo conductor, solape O descanso < 8h entre turnos → alerta.
- Estados `Operation`: `programada | activa | finalizada | cancelada`. Al finalizar/cancelar una operación, sus mulas asignadas vuelven a `disponible` (salvo que estén asignadas a otra operación activa).
- Estados `Shift`: `programado | realizado | cancelado | anulado`.
- Estados de mula: al asignar → `en_operacion`; al liberar → `disponible`.
- `tarifa_hora`, `valor_turno_dia`, `valor_turno_noche`, `meta_horas` se congelan en la operación y se copian al turno al crearlo.
- Git SOLO LOCAL (sin remoto). Cada task termina con tests en verde y commit local.
- Idioma: español (es-co).

---

### Task 1: Modelo Operation con tarifas congeladas

**Files:**
- Create: `apps/operaciones/__init__.py`
- Create: `apps/operaciones/apps.py`
- Create: `apps/operaciones/models.py`
- Create: `apps/operaciones/admin.py`
- Create: `apps/operaciones/tests/__init__.py`
- Create: `apps/operaciones/tests/test_models.py`
- Modify: `config/settings/base.py` (añadir `"apps.operaciones"` a INSTALLED_APPS)

**Interfaces:**
- Consumes: `apps.core.models.AuditMixin`, `apps.catalogos.models.CargoGenerator`, `apps.catalogos.models.Port`.
- Produces:
  - `class Operation(AuditMixin)`:
    - campos: `codigo` (unique), `buque`, `generador_de_carga` FK CargoGenerator (related_name="operaciones"), `puerto` FK Port (related_name="operaciones"), `fecha_inicio` DateField, `fecha_fin_estimada` (null/blank), `fecha_fin_real` (null/blank), `estado` (choices), `meta_horas` Decimal(4,1) default 11, `tarifa_hora` Decimal(14,0), `valor_turno_dia` Decimal(14,0), `valor_turno_noche` Decimal(14,0), `observaciones` TextField blank.
    - constantes `PROGRAMADA/ACTIVA/FINALIZADA/CANCELADA` y `ESTADOS`.
    - `__str__` → `f"{self.codigo} - {self.buque}"`.
  - `@property Operation.total_horas()` — suma de `horas_trabajadas` de sus shifts realizados (Decimal).
  - `@property Operation.estado_activa()` — bool si estado == ACTIVA.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/operaciones/tests/test_models.py`:

```python
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.operaciones.models import Operation


class OperationTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")

    def _crear(self, **kwargs):
        defaults = dict(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )
        defaults.update(kwargs)
        return Operation.objects.create(**defaults)

    def test_operation_creation(self):
        op = self._crear()
        self.assertEqual(str(op), "OP-001 - BUQUE ATLANTIC")
        self.assertEqual(op.estado, Operation.PROGRAMADA)
        self.assertEqual(op.meta_horas, 11)

    def test_operation_codigo_unique(self):
        self._crear()
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            self._crear()

    def test_estado_activa_property(self):
        op = self._crear(estado=Operation.ACTIVA)
        self.assertTrue(op.estado_activa)
        op2 = self._crear(codigo="OP-002", estado=Operation.PROGRAMADA)
        self.assertFalse(op2.estado_activa)

    def test_total_horas_suma_shifts_realizados(self):
        from apps.conductores.models import Driver
        from apps.flota.models import Vehicle
        from apps.operaciones.models import Shift

        op = self._crear(estado=Operation.ACTIVA)
        vehicle = Vehicle.objects.create(placa="ABC123")
        driver = Driver.objects.create(nombre="Juan Pérez", documento="123")
        Shift.objects.create(
            operation=op,
            vehicle=vehicle,
            driver=driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, 10, 6, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, 10, 17, 0)),
            tipo=Shift.DIA,
            meta_horas=op.meta_horas,
            valor_estandar=op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )
        self.assertEqual(op.total_horas, 11.0)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.operaciones.tests -v 2`
Expected: FAIL — `ModuleNotFoundError: apps.operaciones.models`.

- [ ] **Step 3: Registrar la app y crear el modelo**

En `config/settings/base.py`, añadir `"apps.operaciones",` después de `"apps.flota",` (verificar que no se dupliquen apps).

Crear `apps/operaciones/__init__.py` (vacío) y `apps/operaciones/apps.py`:

```python
from django.apps import AppConfig


class OperacionesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.operaciones"
```

Crear `apps/operaciones/models.py`:

```python
from django.db import models

from apps.catalogos.models import CargoGenerator, Port
from apps.core.models import AuditMixin


class Operation(AuditMixin):
    PROGRAMADA = "programada"
    ACTIVA = "activa"
    FINALIZADA = "finalizada"
    CANCELADA = "cancelada"

    ESTADOS = [
        (PROGRAMADA, "Programada"),
        (ACTIVA, "Activa"),
        (FINALIZADA, "Finalizada"),
        (CANCELADA, "Cancelada"),
    ]

    codigo = models.CharField(max_length=20, unique=True)
    buque = models.CharField(max_length=200)
    generador_de_carga = models.ForeignKey(
        CargoGenerator, on_delete=models.PROTECT, related_name="operaciones"
    )
    puerto = models.ForeignKey(Port, on_delete=models.PROTECT, related_name="operaciones")
    fecha_inicio = models.DateField()
    fecha_fin_estimada = models.DateField(null=True, blank=True)
    fecha_fin_real = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=PROGRAMADA)
    meta_horas = models.DecimalField(max_digits=4, decimal_places=1, default=11)
    tarifa_hora = models.DecimalField(max_digits=14, decimal_places=0)
    valor_turno_dia = models.DecimalField(max_digits=14, decimal_places=0)
    valor_turno_noche = models.DecimalField(max_digits=14, decimal_places=0)
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Operación"
        verbose_name_plural = "Operaciones"
        ordering = ["fecha_inicio", "codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.buque}"

    @property
    def estado_activa(self):
        return self.estado == self.ACTIVA

    @property
    def total_horas(self):
        total = sum(
            shift.horas_trabajadas
            for shift in self.shifts.filter(estado="realizado")
        )
        return total
```

Crear `apps/operaciones/admin.py`:

```python
from django.contrib import admin

from apps.operaciones.models import Operation


@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):
    list_display = ("codigo", "buque", "generador_de_carga", "puerto", "fecha_inicio", "estado")
    list_filter = ("estado",)
    search_fields = ("codigo", "buque")
```

- [ ] **Step 4: Generar y aplicar migraciones**

```bash
python manage.py makemigrations operaciones
python manage.py migrate
```

- [ ] **Step 5: Verificar que pasa**

Run: `python manage.py test apps.operaciones.tests -v 2`
Expected: PASS (4 tests). Nota: `test_total_horas` depende de `Shift` que aún no existe — implementar Shift en la Task 3, pero el test se escribirá completo desde aquí; la Task 2 usará un stub temporal SOLO si es imprescindible. **Alternativa:** posponer `test_total_horas` a Task 3 y en Task 1 escribir solo los 3 primeros tests. Ver nota en Task 3.

**Decisión:** escribir en Task 1 SOLO los tests de `test_operation_creation`, `test_operation_codigo_unique`, `test_estado_activa_property` (3 tests). `test_total_horas` se escribe y corre en Task 3 cuando exista `Shift`.

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "feat(operaciones): modelo Operation con tarifas congeladas"
```

---

### Task 2: Asignación de mulas — OperationVehicle y sincronización de estados

**Files:**
- Create: `apps/operaciones/tests/test_operation_vehicle.py`
- Modify: `apps/operaciones/models.py` (añadir OperationVehicle)
- Create: `apps/operaciones/services.py`

**Interfaces:**
- Consumes: `Operation` (Task 1), `apps.flota.models.Vehicle`.
- Produces:
  - `class OperationVehicle(AuditMixin)`: `operation` FK Operation related_name="mulas", `vehicle` FK Vehicle related_name="operaciones", `fecha_asignacion` DateField default timezone.localdate, `activa` bool default True. `unique_together = (("operation", "vehicle"),)`.
  - `def asignar_mulas(operation, vehicles) -> None` — crea OperationVehicle activa por cada vehicle y pone cada vehicle en `en_operacion`. Recibe operación guardada y queryset/lista de Vehicle. Idempotente: si ya existe la relación, no duplica (get_or_create + activa=True).
  - `def liberar_mulas(operation) -> None` — marca `activa=False` en sus OperationVehicle y pone cada vehicle en `disponible` SOLO si el vehicle no está activo en otra operación.
  - `def mulas_disponibles() -> QuerySet[Vehicle]` — vehicles con estado `disponible`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/operaciones/tests/test_operation_vehicle.py`:

```python
from datetime import date

from django.test import TestCase

from apps.catalogos.models import CargoGenerator, Port
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation
from apps.operaciones.services import asignar_mulas, liberar_mulas, mulas_disponibles


class AsignacionMulasTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.v1 = Vehicle.objects.create(placa="ABC123")
        self.v2 = Vehicle.objects.create(placa="DEF456")
        self.op = Operation.objects.create(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )

    def test_asignar_mulas_cambia_estado_y_crea_relaciones(self):
        asignar_mulas(self.op, [self.v1, self.v2])
        self.v1.refresh_from_db()
        self.v2.refresh_from_db()
        self.assertEqual(self.v1.estado, Vehicle.EN_OPERACION)
        self.assertEqual(self.v2.estado, Vehicle.EN_OPERACION)
        self.assertEqual(self.op.mulas.filter(activa=True).count(), 2)

    def test_asignar_mulas_idempotente(self):
        asignar_mulas(self.op, [self.v1])
        asignar_mulas(self.op, [self.v1])
        self.assertEqual(self.op.mulas.filter(activa=True).count(), 1)

    def test_liberar_mulas_libera_si_no_esta_en_otra_operacion(self):
        asignar_mulas(self.op, [self.v1])
        liberar_mulas(self.op)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.estado, Vehicle.DISPONIBLE)
        self.assertFalse(self.op.mulas.get(vehicle=self.v1).activa)

    def test_liberar_mulas_no_libera_vehicle_en_otra_operacion(self):
        op2 = Operation.objects.create(
            codigo="OP-002",
            buque="BUQUE OTRO",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 11),
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )
        asignar_mulas(self.op, [self.v1])
        asignar_mulas(op2, [self.v1])
        liberar_mulas(self.op)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.estado, Vehicle.EN_OPERACION)

    def test_mulas_disponibles_solo_filtra_disponibles(self):
        self.v1.estado = Vehicle.EN_TALLER
        self.v1.save()
        disponibles = list(mulas_disponibles())
        self.assertIn(self.v2, disponibles)
        self.assertNotIn(self.v1, disponibles)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.operaciones.tests.test_operation_vehicle -v 2`
Expected: FAIL — `ModuleNotFoundError: apps.operaciones.services`.

- [ ] **Step 3: Implementación mínima**

Añadir a `apps/operaciones/models.py`:

```python
class OperationVehicle(AuditMixin):
    operation = models.ForeignKey(
        Operation, on_delete=models.CASCADE, related_name="mulas"
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="operaciones"
    )
    fecha_asignacion = models.DateField(default=timezone.localdate)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Mula asignada"
        verbose_name_plural = "Mulas asignadas"
        unique_together = (("operation", "vehicle"),)
```

Nota: importar `Vehicle` de `apps.flota.models` y `from django.utils import timezone` en models.py.

Crear `apps/operaciones/services.py`:

```python
from apps.flota.models import Vehicle


def mulas_disponibles():
    return Vehicle.objects.filter(estado=Vehicle.DISPONIBLE)


def asignar_mulas(operation, vehicles):
    for vehicle in vehicles:
        relation, _ = operation.mulas.get_or_create(vehicle=vehicle)
        relation.activa = True
        relation.fecha_asignacion = timezone.localdate()
        relation.save()
        vehicle.estado = Vehicle.EN_OPERACION
        vehicle.save(update_fields=["estado"])


def liberar_mulas(operation):
    for relation in operation.mulas.filter(activa=True):
        relation.activa = False
        relation.save(update_fields=["activa"])
        en_otra_activa = operation.mulas.exclude(pk=operation.pk).filter(
            vehicle=relation.vehicle, activa=True
        ).exists()
        if not en_otra_activa:
            relation.vehicle.estado = Vehicle.DISPONIBLE
            relation.vehicle.save(update_fields=["estado"])
```

Nota: importar `from django.utils import timezone` en services.py. En `liberar_mulas`, la query para "otra operación" debe ser: `OperationVehicle.objects.filter(vehicle=relation.vehicle, activa=True).exclude(operation=operation).exists()`. Usar la clase `OperationVehicle`.

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.operaciones.tests.test_operation_vehicle -v 2`
Expected: PASS (5 tests). Corregir el filtro de "otra operación" para que el test `test_liberar_mulas_no_libera_vehicle_en_otra_operacion` pase.

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "feat(operaciones): asignacion de mulas con sincronizacion de estados"
```

---

### Task 3: Modelo Shift — cálculo de horas y cumplimiento

**Files:**
- Modify: `apps/operaciones/models.py` (añadir Shift)
- Create: `apps/operaciones/tests/test_shift.py`

**Interfaces:**
- Consumes: `Operation`, `Vehicle`, `Driver`, `IncidentCategory`.
- Produces:
  - `class Shift(AuditMixin)`:
    - campos: `operation` FK related_name="shifts", `vehicle` FK Vehicle related_name="shifts", `driver` FK Driver related_name="shifts", `fecha_inicio` DateTimeField, `fecha_fin` DateTimeField, `horas_trabajadas` Decimal(5,2) default 0, `meta_horas` Decimal(4,1), `cumplimiento_pct` Decimal(5,1) default 0, `tipo` (dia|noche), `valor_estandar` Decimal(14,0), `valor_pagado` Decimal(14,0), `estado` (choices), `motivo_cancelacion` TextField blank, `observaciones` TextField blank.
    - constantes `DIA="dia"`, `NOCHE="noche"`, `PROGRAMADO/REALIZADO/CANCELADO/ANULADO`.
  - `Shift.save()` calcula automáticamente: `horas_trabajadas = (fecha_fin - fecha_inicio).total_seconds() / 3600`, redondeado a 2 decimales; `cumplimiento_pct = round(horas/meta*100, 1)` si meta>0.
  - `@property Shift.valor_es_pagable` — bool: estado == REALIZADO.
  - Añadir test `test_total_horas` de la Task 1 en `apps/operaciones/tests/test_models.py`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/operaciones/tests/test_shift.py`:

```python
from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift


class ShiftTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123")
        self.op = Operation.objects.create(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            meta_horas=11,
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )

    def _crear_shift(self, inicio, fin, **kwargs):
        defaults = dict(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(inicio),
            fecha_fin=timezone.make_aware(fin),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
        )
        defaults.update(kwargs)
        return Shift.objects.create(**defaults)

    def test_horas_calculadas_turno_dia(self):
        shift = self._crear_shift(
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
        )
        self.assertEqual(shift.horas_trabajadas, 11.0)
        self.assertEqual(shift.cumplimiento_pct, 100.0)

    def test_horas_nocturno_cruza_medianoche(self):
        shift = self._crear_shift(
            timezone.datetime(2026, 8, 10, 18, 0),
            timezone.datetime(2026, 8, 11, 6, 0),
            tipo=Shift.NOCHE,
        )
        self.assertEqual(shift.horas_trabajadas, 12.0)
        self.assertEqual(shift.cumplimiento_pct, 109.1)

    def test_cumplimiento_bajo(self):
        shift = self._crear_shift(
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 14, 0),
        )
        self.assertEqual(shift.horas_trabajadas, 8.0)
        self.assertEqual(shift.cumplimiento_pct, 72.7)

    def test_valor_es_pagable_solo_realizado(self):
        shift = self._crear_shift(
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
            estado=Shift.REALIZADO,
        )
        self.assertTrue(shift.valor_es_pagable)
        shift.estado = Shift.CANCELADO
        shift.save()
        self.assertFalse(shift.valor_es_pagable)

    def test_estado_default_programado(self):
        shift = self._crear_shift(
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
        )
        self.assertEqual(shift.estado, Shift.PROGRAMADO)
```

En `apps/operaciones/tests/test_models.py`, añadir `test_total_horas_suma_shifts_realizados` (el de la Task 1) al final de `OperationTests`.

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.operaciones.tests.test_shift apps.operaciones.tests.test_models -v 2`
Expected: FAIL — `ModuleNotFoundError: apps.operaciones.models` para Shift / `Shift` indefinido.

- [ ] **Step 3: Implementación mínima**

Añadir a `apps/operaciones/models.py`:

```python
class Shift(AuditMixin):
    DIA = "dia"
    NOCHE = "noche"

    TIPOS = [
        (DIA, "Día"),
        (NOCHE, "Noche"),
    ]

    PROGRAMADO = "programado"
    REALIZADO = "realizado"
    CANCELADO = "cancelado"
    ANULADO = "anulado"

    ESTADOS = [
        (PROGRAMADO, "Programado"),
        (REALIZADO, "Realizado"),
        (CANCELADO, "Cancelado"),
        (ANULADO, "Anulado"),
    ]

    operation = models.ForeignKey(
        Operation, on_delete=models.PROTECT, related_name="shifts"
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.PROTECT, related_name="shifts"
    )
    driver = models.ForeignKey(
        Driver, on_delete=models.PROTECT, related_name="shifts"
    )
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    horas_trabajadas = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    meta_horas = models.DecimalField(max_digits=4, decimal_places=1)
    cumplimiento_pct = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    valor_estandar = models.DecimalField(max_digits=14, decimal_places=0)
    valor_pagado = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=PROGRAMADO)
    motivo_cancelacion = models.TextField(blank=True, default="")
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Turno"
        verbose_name_plural = "Turnos"
        ordering = ["fecha_inicio"]

    def __str__(self):
        return f"{self.vehicle.placa} {self.fecha_inicio:%d/%m %H:%M}"

    def save(self, *args, **kwargs):
        delta = self.fecha_fin - self.fecha_inicio
        self.horas_trabajadas = round(delta.total_seconds() / 3600, 2)
        if self.meta_horas:
            self.cumplimiento_pct = round(
                float(self.horas_trabajadas) / float(self.meta_horas) * 100, 1
            )
        if self.estado == self.REALIZADO:
            self.valor_pagado = self.valor_estandar
        else:
            self.valor_pagado = 0
        super().save(*args, **kwargs)

    @property
    def valor_es_pagable(self):
        return self.estado == self.REALIZADO
```

Nota: importar `Driver` y `Vehicle` en models.py.

- [ ] **Step 4: Generar migración y verificar**

```bash
python manage.py makemigrations operaciones
python manage.py migrate
python manage.py test apps.operaciones.tests -v 2
```

Expected: PASS (5 shift + 4 model incl. total_horas + 5 operation_vehicle = 14 tests).

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "feat(operaciones): modelo Shift con calculo de horas y cumplimiento"
```

---

### Task 4: Novedades — Incident y validación de turno corto

**Files:**
- Modify: `apps/operaciones/models.py` (añadir Incident)
- Create: `apps/operaciones/tests/test_incident.py`
- Modify: `apps/operaciones/services.py` (añadir registrar_turno)

**Interfaces:**
- Consumes: `Shift`, `IncidentCategory` (apps.catalogos).
- Produces:
  - `class Incident(AuditMixin)`: `shift` OneToOneField Shift related_name="incidente", `categoria` FK IncidentCategory related_name="incidentes", `descripcion` TextField blank.
  - `def registrar_turno(operation, vehicle, driver, fecha_inicio, fecha_fin, tipo, valor_estandar, meta_horas, novedad_categoria=None, novedad_descripcion="", observaciones="") -> Shift` — crea el Shift en estado `realizado`; si `novedad_categoria` está presente crea el Incident asociado; **valida**: si el turno tendrá horas < meta y no hay novedad_categoria → `ValidationError`. Si hay solape con un turno existente del mismo vehicle → `ValidationError`.
  - `def cancelar_turno(shift, motivo, usuario) -> None` — estado → `cancelado`, `motivo_cancelacion` = motivo, guarda `updated_by` = usuario.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/operaciones/tests/test_incident.py`:

```python
from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift
from apps.operaciones.services import cancelar_turno, registrar_turno


class IncidentTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123")
        self.op = Operation.objects.create(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            meta_horas=11,
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )
        self.lluvia = IncidentCategory.objects.create(nombre="Lluvia")

    def test_registrar_turno_crea_shift_realizado_sin_novedad(self):
        shift = registrar_turno(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.datetime(2026, 8, 10, 6, 0),
            fecha_fin=timezone.datetime(2026, 8, 10, 17, 0),
            tipo=Shift.DIA,
            valor_estandar=self.op.valor_turno_dia,
            meta_horas=self.op.meta_horas,
        )
        self.assertEqual(shift.estado, Shift.REALIZADO)
        self.assertEqual(shift.horas_trabajadas, 11.0)
        self.assertFalse(hasattr(shift, "incidente"))

    def test_registrar_turno_con_novedad_crea_incident(self):
        shift = registrar_turno(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.datetime(2026, 8, 10, 6, 0),
            fecha_fin=timezone.datetime(2026, 8, 10, 17, 0),
            tipo=Shift.DIA,
            valor_estandar=self.op.valor_turno_dia,
            meta_horas=self.op.meta_horas,
            novedad_categoria=self.lluvia,
            novedad_descripcion="Lluvia 09:00-10:00",
        )
        self.assertEqual(shift.incidente.categoria, self.lluvia)
        self.assertEqual(shift.incidente.descripcion, "Lluvia 09:00-10:00")

    def test_turno_corto_exige_novedad(self):
        with self.assertRaises(ValidationError):
            registrar_turno(
                operation=self.op,
                vehicle=self.vehicle,
                driver=self.driver,
                fecha_inicio=timezone.datetime(2026, 8, 10, 6, 0),
                fecha_fin=timezone.datetime(2026, 8, 10, 14, 0),
                tipo=Shift.DIA,
                valor_estandar=self.op.valor_turno_dia,
                meta_horas=self.op.meta_horas,
            )

    def test_turno_corto_con_novedad_es_valido(self):
        shift = registrar_turno(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.datetime(2026, 8, 10, 6, 0),
            fecha_fin=timezone.datetime(2026, 8, 10, 14, 0),
            tipo=Shift.DIA,
            valor_estandar=self.op.valor_turno_dia,
            meta_horas=self.op.meta_horas,
            novedad_categoria=self.lluvia,
        )
        self.assertEqual(shift.cumplimiento_pct, 72.7)

    def test_cancelar_turno_estado_y_motivo(self):
        shift = registrar_turno(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.datetime(2026, 8, 10, 6, 0),
            fecha_fin=timezone.datetime(2026, 8, 10, 17, 0),
            tipo=Shift.DIA,
            valor_estandar=self.op.valor_turno_dia,
            meta_horas=self.op.meta_horas,
        )
        cancelar_turno(shift, "Avería mecánica", usuario=None)
        shift.refresh_from_db()
        self.assertEqual(shift.estado, Shift.CANCELADO)
        self.assertEqual(shift.motivo_cancelacion, "Avería mecánica")
        self.assertEqual(shift.valor_pagado, 0)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.operaciones.tests.test_incident -v 2`
Expected: FAIL — `ValidationError` en registrar_turno no definido / funciones ausentes.

- [ ] **Step 3: Implementación mínima**

Añadir a `apps/operaciones/models.py`:

```python
class Incident(AuditMixin):
    shift = models.OneToOneField(
        Shift, on_delete=models.CASCADE, related_name="incidente"
    )
    categoria = models.ForeignKey(
        IncidentCategory, on_delete=models.PROTECT, related_name="incidentes"
    )
    descripcion = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Novedad"
        verbose_name_plural = "Novedades"

    def __str__(self):
        return f"{self.get_categoria_display()} - {self.shift}"
```

Nota: `categoria` no tiene `get_categoria_display` (no es choices); usar `self.categoria.nombre`. Importar `IncidentCategory`.

Añadir a `apps/operaciones/services.py`:

```python
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.operaciones.models import Incident, OperationVehicle, Shift


def registrar_turno(
    operation,
    vehicle,
    driver,
    fecha_inicio,
    fecha_fin,
    tipo,
    valor_estandar,
    meta_horas,
    novedad_categoria=None,
    novedad_descripcion="",
    observaciones="",
):
    inicio = timezone.make_aware(fecha_inicio)
    fin = timezone.make_aware(fecha_fin)
    horas = (fin - inicio).total_seconds() / 3600

    if horas < float(meta_horas) and novedad_categoria is None:
        raise ValidationError(
            "Un turno con menos horas que la meta requiere una novedad."
        )

    overlap = (
        Shift.objects.filter(vehicle=vehicle, estado__in=["programado", "realizado"])
        .filter(fecha_inicio__lt=fin, fecha_fin__gt=inicio)
        .exists()
    )
    if overlap:
        raise ValidationError("El vehículo ya tiene un turno en ese horario.")

    shift = Shift.objects.create(
        operation=operation,
        vehicle=vehicle,
        driver=driver,
        fecha_inicio=inicio,
        fecha_fin=fin,
        tipo=tipo,
        valor_estandar=valor_estandar,
        meta_horas=meta_horas,
        estado=Shift.REALIZADO,
        observaciones=observaciones,
    )
    if novedad_categoria is not None:
        Incident.objects.create(
            shift=shift, categoria=novedad_categoria, descripcion=novedad_descripcion
        )
    return shift


def cancelar_turno(shift, motivo, usuario=None):
    shift.estado = Shift.CANCELADO
    shift.motivo_cancelacion = motivo
    if usuario is not None:
        shift.updated_by = usuario
    shift.save(update_fields=["estado", "motivo_cancelacion", "updated_by"])
```

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.operaciones.tests.test_incident -v 2`
Expected: PASS (5 tests). Ajustar `Shift.save()` si el test de valor_pagado==0 tras cancelar falla: el `save(update_fields=...)` en cancelar_turno no recalcula; verificar que `valor_pagado` se guardó en 0 al cambiar estado. Si no, hacer `shift.save()` completo en cancelar_turno.

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "feat(operaciones): novedades asociadas y validacion de turno corto"
```

---

### Task 5: Detección de doble turno

**Files:**
- Modify: `apps/operaciones/services.py` (añadir detectar_dobles_turnos)
- Create: `apps/operaciones/tests/test_doble_turno.py`

**Interfaces:**
- Consumes: `Shift` (Task 3).
- Produces:
  - `def detectar_dobles_turnos(driver=None, desde=None, hasta=None) -> list[dict]` — para cada conductor, ordena sus turnos `realizados`/`programados` por `fecha_inicio`; detecta pares donde `inicio_b < fin_a` (solape) o `(inicio_b - fin_a) < 8h` (descanso insuficiente). Cada dict: `{"driver": driver, "turno_a": shift_a, "turno_b": shift_b, "tipo": "solape"|"descanso"}`. Si `driver` es None, analiza todos los conductores; si `desde`/`hasta` se dan, filtra por `fecha_inicio`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/operaciones/tests/test_doble_turno.py`:

```python
from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift
from apps.operaciones.services import detectar_dobles_turnos


class DobleTurnoTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.v1 = Vehicle.objects.create(placa="ABC123")
        self.v2 = Vehicle.objects.create(placa="DEF456")
        self.juan = Driver.objects.create(nombre="Juan Pérez", documento="123")
        self.op = Operation.objects.create(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            meta_horas=11,
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
        )

    def _crear(self, driver, vehicle, inicio, fin):
        return Shift.objects.create(
            operation=self.op,
            vehicle=vehicle,
            driver=driver,
            fecha_inicio=timezone.make_aware(inicio),
            fecha_fin=timezone.make_aware(fin),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )

    def test_descanso_insuficiente_detectado(self):
        a = self._crear(
            self.juan, self.v1,
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
        )
        b = self._crear(
            self.juan, self.v2,
            timezone.datetime(2026, 8, 10, 18, 0),
            timezone.datetime(2026, 8, 11, 5, 0),
        )
        result = detectar_dobles_turnos(driver=self.juan)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["turno_a"], a)
        self.assertEqual(result[0]["turno_b"], b)
        self.assertEqual(result[0]["tipo"], "descanso")

    def test_solape_detectado(self):
        self._crear(
            self.juan, self.v1,
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
        )
        self._crear(
            self.juan, self.v2,
            timezone.datetime(2026, 8, 10, 16, 0),
            timezone.datetime(2026, 8, 10, 20, 0),
        )
        result = detectar_dobles_turnos(driver=self.juan)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tipo"], "solape")

    def test_descanso_suficiente_no_detectado(self):
        self._crear(
            self.juan, self.v1,
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
        )
        self._crear(
            self.juan, self.v2,
            timezone.datetime(2026, 8, 11, 6, 0),
            timezone.datetime(2026, 8, 11, 17, 0),
        )
        self.assertEqual(detectar_dobles_turnos(driver=self.juan), [])

    def test_filtro_por_rango_de_fechas(self):
        self._crear(
            self.juan, self.v1,
            timezone.datetime(2026, 8, 1, 6, 0),
            timezone.datetime(2026, 8, 1, 17, 0),
        )
        self._crear(
            self.juan, self.v2,
            timezone.datetime(2026, 8, 1, 18, 0),
            timezone.datetime(2026, 8, 1, 23, 0),
        )
        result = detectar_dobles_turnos(
            driver=self.juan, desde=date(2026, 8, 10), hasta=date(2026, 8, 20)
        )
        self.assertEqual(result, [])
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.operaciones.tests.test_doble_turno -v 2`
Expected: FAIL — `ImportError: cannot import name 'detectar_dobles_turnos'`.

- [ ] **Step 3: Implementación mínima**

Añadir a `apps/operaciones/services.py`:

```python
from datetime import timedelta

from django.utils import timezone

from apps.operaciones.models import Shift

DESCANSO_MINIMO_HORAS = 8


def detectar_dobles_turnos(driver=None, desde=None, hasta=None):
    shifts = Shift.objects.filter(estado__in=["programado", "realizado"])
    if driver is not None:
        shifts = shifts.filter(driver=driver)
    if desde is not None:
        shifts = shifts.filter(fecha_inicio__date__gte=desde)
    if hasta is not None:
        shifts = shifts.filter(fecha_inicio__date__lte=hasta)

    por_driver = {}
    for shift in shifts.order_by("fecha_inicio").select_related("driver"):
        por_driver.setdefault(shift.driver_id, []).append(shift)

    result = []
    for turnos in por_driver.values():
        turnos.sort(key=lambda s: s.fecha_inicio)
        for i in range(len(turnos) - 1):
            a, b = turnos[i], turnos[i + 1]
            if b.fecha_inicio < a.fecha_fin:
                result.append(
                    {"driver": a.driver, "turno_a": a, "turno_b": b, "tipo": "solape"}
                )
            elif (b.fecha_inicio - a.fecha_fin).total_seconds() / 3600 < DESCANSO_MINIMO_HORAS:
                result.append(
                    {"driver": a.driver, "turno_a": a, "turno_b": b, "tipo": "descanso"}
                )
    return result
```

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.operaciones.tests.test_doble_turno -v 2`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "feat(operaciones): deteccion de doble turno por solape o descanso insuficiente"
```

---

### Task 6: Vistas funcionales — listado, detalle y registro de turnos

**Files:**
- Create: `apps/operaciones/urls.py`
- Create: `apps/operaciones/views.py`
- Create: `apps/operaciones/forms.py`
- Create: `templates/operaciones/operacion_list.html`
- Create: `templates/operaciones/operacion_detail.html`
- Create: `templates/operaciones/shift_form.html`
- Create: `apps/operaciones/tests/test_views.py`
- Modify: `config/urls.py` (incluir urls de operaciones bajo prefijo `operaciones/`)

**Interfaces:**
- Consumes: `Operation`, `OperationVehicle`, `Shift`, `registrar_turno`, `cancelar_turno`, `asignar_mulas`, `mulas_disponibles`, `IncidentCategory`.
- Produces:
  - URL namespace `operaciones`:
    - `operaciones:lista` → lista de operaciones activas/programadas.
    - `operaciones:detalle` (`<int:pk>/`) → detalle con mulas, turnos, acciones.
    - `operaciones:nuevo` → formulario de creación (con selección múltiple de mulas disponibles).
    - `operaciones:turno_nuevo` (`<int:pk>/turnos/nuevo/`) → registro de turno (con HTMX para novedad).
    - `operaciones:turno_cancelar` (`turnos/<int:pk>/cancelar/`) → cancelar turno (POST).
  - Requieren autenticación (`LoginRequiredMixin` o `@login_required`). Solo GET visible para Gerencia; escritura requiere Secretaria/Admin (se implementa con permisos por grupo en esta tarea de forma simple: `@login_required`; la granularidad fina se decide en la revisión final con el finding de `setup_groups`).

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/operaciones/tests/test_views.py`:

```python
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation
from apps.operaciones.services import registrar_turno


class OperacionesViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123")
        self.lluvia = IncidentCategory.objects.create(nombre="Lluvia")
        self.op = Operation.objects.create(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            meta_horas=11,
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
            estado=Operation.ACTIVA,
        )
        self.client.force_login(self.user)

    def test_lista_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse("operaciones:lista"))
        self.assertEqual(response.status_code, 302)

    def test_lista_muestra_operaciones(self):
        response = self.client.get(reverse("operaciones:lista"))
        self.assertContains(response, "BUQUE ATLANTIC")

    def test_detalle_muestra_turnos(self):
        registrar_turno(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.datetime(2026, 8, 10, 6, 0),
            fecha_fin=timezone.datetime(2026, 8, 10, 17, 0),
            tipo="dia",
            valor_estandar=self.op.valor_turno_dia,
            meta_horas=self.op.meta_horas,
        )
        response = self.client.get(reverse("operaciones:detalle", args=[self.op.pk]))
        self.assertContains(response, "Juan Pérez")
        self.assertContains(response, "ABC123")

    def test_registrar_turno_via_post(self):
        response = self.client.post(
            reverse("operaciones:turno_nuevo", args=[self.op.pk]),
            {
                "vehicle": self.vehicle.pk,
                "driver": self.driver.pk,
                "fecha_inicio": "2026-08-10 06:00",
                "fecha_fin": "2026-08-10 17:00",
                "tipo": "dia",
                "novedad_categoria": self.lluvia.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.op.shifts.count(), 1)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.operaciones.tests.test_views -v 2`
Expected: FAIL — `NoReverseMatch` para `operaciones:lista`.

- [ ] **Step 3: Implementar vistas y URLs**

Crear `apps/operaciones/urls.py`:

```python
from django.urls import path

from apps.operaciones import views

app_name = "operaciones"

urlpatterns = [
    path("", views.operacion_list, name="lista"),
    path("nueva/", views.operacion_nueva, name="nuevo"),
    path("<int:pk>/", views.operacion_detail, name="detalle"),
    path("<int:pk>/turnos/nuevo/", views.turno_nuevo, name="turno_nuevo"),
    path("turnos/<int:pk>/cancelar/", views.turno_cancelar, name="turno_cancelar"),
]
```

En `config/urls.py`, añadir:

```python
path("operaciones/", include("apps.operaciones.urls")),
```

Crear `apps/operaciones/forms.py`:

```python
from django import forms

from apps.flota.models import Vehicle
from apps.operaciones.models import Operation
from apps.operaciones.services import mulas_disponibles


class OperationForm(forms.ModelForm):
    mulas = forms.ModelMultipleChoiceField(
        queryset=Vehicle.objects.none(), required=False, label="Mulas"
    )

    class Meta:
        model = Operation
        fields = [
            "codigo", "buque", "generador_de_carga", "puerto", "fecha_inicio",
            "fecha_fin_estimada", "meta_horas", "tarifa_hora",
            "valor_turno_dia", "valor_turno_noche", "observaciones",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mulas"].queryset = mulas_disponibles()


class ShiftForm(forms.Form):
    vehicle = forms.ModelChoiceField(queryset=Vehicle.objects.none(), label="Mula")
    driver = forms.ModelChoiceField(
        queryset=Driver.objects.all(), label="Conductor"
    )
    fecha_inicio = forms.DateTimeField(label="Hora de inicio", input_formats=["%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M"])
    fecha_fin = forms.DateTimeField(label="Hora de fin", input_formats=["%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M"])
    tipo = forms.ChoiceField(choices=[("dia", "Día"), ("noche", "Noche")], label="Tipo")
    novedad_categoria = forms.ModelChoiceField(
        queryset=IncidentCategory.objects.filter(activa=True),
        required=False,
        label="Novedad",
    )
    novedad_descripcion = forms.CharField(
        required=False, widget=forms.Textarea, label="Detalle de la novedad"
    )
```

Nota: importar `Driver` e `IncidentCategory` en forms.py; `self.fields["vehicle"].queryset` se limita a las mulas de la operación en la vista.

Crear `apps/operaciones/views.py`:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.operaciones.forms import OperationForm, ShiftForm
from apps.operaciones.models import Operation, Shift
from apps.operaciones.services import asignar_mulas, cancelar_turno, registrar_turno


@login_required
def operacion_list(request):
    operaciones = Operation.objects.filter(
        estado__in=[Operation.PROGRAMADA, Operation.ACTIVA]
    ).order_by("-fecha_inicio")
    return render(request, "operaciones/operacion_list.html", {"operaciones": operaciones})


@login_required
def operacion_detail(request, pk):
    operation = get_object_or_404(Operation.objects.prefetch_related("shifts", "mulas"), pk=pk)
    return render(request, "operaciones/operacion_detail.html", {"operation": operation})


@login_required
def operacion_nueva(request):
    if request.method == "POST":
        form = OperationForm(request.POST)
        if form.is_valid():
            operation = form.save()
            asignar_mulas(operation, form.cleaned_data["mulas"])
            return redirect("operaciones:detalle", pk=operation.pk)
    else:
        form = OperationForm()
    return render(request, "operaciones/operacion_list.html", {"form": form, "creando": True})


@login_required
def turno_nuevo(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    form = ShiftForm(request.POST or None)
    form.fields["vehicle"].queryset = operation.mulas.filter(activa=True).select_related("vehicle")
    form.fields["vehicle"].queryset = Vehicle.objects.filter(pk__in=operation.mulas.filter(activa=True).values("vehicle"))
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        registrar_turno(
            operation=operation,
            vehicle=data["vehicle"],
            driver=data["driver"],
            fecha_inicio=data["fecha_inicio"],
            fecha_fin=data["fecha_fin"],
            tipo=data["tipo"],
            valor_estandar=operation.valor_turno_dia if data["tipo"] == "dia" else operation.valor_turno_noche,
            meta_horas=operation.meta_horas,
            novedad_categoria=data.get("novedad_categoria"),
            novedad_descripcion=data.get("novedad_descripcion", ""),
        )
        return redirect("operaciones:detalle", pk=operation.pk)
    return render(request, "operaciones/shift_form.html", {"form": form, "operation": operation})


@login_required
def turno_cancelar(request, pk):
    shift = get_object_or_404(Shift, pk=pk)
    if request.method == "POST":
        cancelar_turno(shift, request.POST.get("motivo", ""), usuario=request.user)
    return redirect("operaciones:detalle", pk=shift.operation_id)
```

Nota: importar `Vehicle` en views.py y limpiar el queryset de vehicle (una sola asignación correcta).

- [ ] **Step 4: Crear plantillas**

Crear `templates/operaciones/operacion_list.html`:

```html
{% extends "base.html" %}
{% block title %}Operaciones{% endblock %}
{% block content %}
<p class="eyebrow">Transportes Renacer</p>
<h1>Operaciones activas</h1>
{% if creando %}
  <form method="post" class="card">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="btn btn-primary">Crear operación</button>
  </form>
{% else %}
  <a class="btn btn-primary" href="{% url 'operaciones:nuevo' %}">Nueva operación</a>
  <table class="table">
    <thead><tr><th>Código</th><th>Buque</th><th>Generador de carga</th><th>Puerto</th><th>Estado</th></tr></thead>
    <tbody>
    {% for op in operaciones %}
      <tr>
        <td><a href="{% url 'operaciones:detalle' op.pk %}">{{ op.codigo }}</a></td>
        <td>{{ op.buque }}</td>
        <td>{{ op.generador_de_carga }}</td>
        <td>{{ op.puerto }}</td>
        <td>{{ op.get_estado_display }}</td>
      </tr>
    {% empty %}
      <tr><td colspan="5">No hay operaciones activas.</td></tr>
    {% endfor %}
    </tbody>
  </table>
{% endif %}
{% endblock %}
```

Crear `templates/operaciones/operacion_detail.html`:

```html
{% extends "base.html" %}
{% block title %}{{ operation.codigo }}{% endblock %}
{% block content %}
<p class="eyebrow">Operación</p>
<h1>{{ operation.buque }}</h1>
<p><strong>{{ operation.codigo }}</strong> · {{ operation.generador_de_carga }} · {{ operation.puerto }}</p>
<p>Meta: {{ operation.meta_horas }} h · Tarifa: ${{ operation.tarifa_hora }}/h · Turno día: ${{ operation.valor_turno_dia }}</p>
<h2>Mulas asignadas</h2>
<ul>
  {% for mula in operation.mulas.all %}
    <li>{{ mula.vehicle.placa }}{% if mula.activa %} · activa{% endif %}</li>
  {% empty %}
    <li>Sin mulas asignadas.</li>
  {% endfor %}
</ul>
<h2>Turnos</h2>
<a class="btn btn-primary" href="{% url 'operaciones:turno_nuevo' operation.pk %}">Registrar turno</a>
<table class="table">
  <thead><tr><th>Mula</th><th>Conductor</th><th>Inicio</th><th>Fin</th><th>Horas</th><th>Cumpl.</th><th>Estado</th></tr></thead>
  <tbody>
  {% for shift in operation.shifts.all %}
    <tr>
      <td>{{ shift.vehicle.placa }}</td>
      <td>{{ shift.driver }}</td>
      <td>{{ shift.fecha_inicio|date:"d/m/Y H:i" }}</td>
      <td>{{ shift.fecha_fin|date:"d/m/Y H:i" }}</td>
      <td>{{ shift.horas_trabajadas }}</td>
      <td>{{ shift.cumplimiento_pct }}%</td>
      <td>{{ shift.get_estado_display }}</td>
    </tr>
  {% empty %}
    <tr><td colspan="7">Sin turnos registrados.</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
```

Crear `templates/operaciones/shift_form.html`:

```html
{% extends "base.html" %}
{% block title %}Registrar turno{% endblock %}
{% block content %}
<p class="eyebrow">Registrar turno</p>
<h1>{{ operation.buque }}</h1>
<form method="post">
  {% csrf_token %}
  {{ form.as_p }}
  <button type="submit" class="btn btn-primary">Guardar turno</button>
</form>
{% endblock %}
```

Añadir estilos `.card` y `.table` a `static/css/app.css`:

```css
.card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 24px;
  max-width: 640px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}
.table { width: 100%; border-collapse: collapse; margin-top: 16px; background: var(--surface); }
.table th, .table td {
  border: 1px solid var(--line); padding: 8px 12px; text-align: left; font-size: 14px;
}
.table th { background: var(--surface-hover); font-family: "IBM Plex Mono", monospace; font-size: 12px; }
```

- [ ] **Step 5: Verificar que pasa**

Run: `python manage.py test apps.operaciones.tests.test_views -v 2`
Expected: PASS (4 tests). Ajustar el formulario `ShiftForm` (queryset de vehicle) hasta que el POST registre el turno.

- [ ] **Step 6: Suite completa**

Run: `python manage.py test -v 2`
Expected: PASS (tests previos + 4 nuevos de vistas + los de operaciones = ~34).

- [ ] **Step 7: Commit local**

```bash
git add -A
git commit -m "feat(operaciones): vistas funcionales de operaciones y registro de turnos"
```

---

## Self-Review del Plan

**Cobertura del spec (Plan 2):**
- `operations` con código, buque, generador de carga, puerto, fechas, estado, meta, tarifas congeladas: Task 1. ✔
- Estados de operación (programada/activa/finalizada/cancelada) + historial: Task 1. ✔
- `operation_vehicles` + asignación de mulas disponibles + sincronización de estado del vehículo: Task 2. ✔
- `shifts` como unidad central: Task 3. ✔
- Cálculo de horas reales (nocturno cruzando medianoche) + cumplimiento: Task 3. ✔
- Valor de turno copiado de la operación, pagable solo si realizado: Task 3. ✔
- `incidents` + categorías + turno corto exige novedad: Task 4. ✔
- Cancelación de turnos con motivo/usuario/fecha, $0, no pago: Task 4. ✔
- Detección de doble turno (solape / descanso <8h): Task 5. ✔
- Vistas funcionales (listado, detalle, creación con asignación, registro de turno, cancelación): Task 6. ✔
- No eliminación física (estados): Tasks 1-4. ✔

**Fuera de este plan:** nómina (Plan 3), facturación/saldos/CSV (Plan 4), dashboards/Gantt (Plan 5), edición de valor de turno con auditoría de motivo (se añade en Plan 3 junto a nómina, o como mejora), granularidad fina de permisos por grupo (pendiente de decisión del humano en revisión final).

**Placeholders:** ninguno; cada paso contiene código o comandos reales.

**Consistencia de tipos:** `registrar_turno`/`cancelar_turno`/`asignar_mulas`/`liberar_mulas`/`mulas_disponibles`/`detectar_dobles_turnos` definidos en servicios y consumidos por vistas/tests con las mismas firmas. `Shift.save()` recalcula horas/cumplimiento/valor_pagado en cada guardado (incluido cancelar). `Operation.total_horas` usa el related_name `shifts`.
