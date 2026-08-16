# Plan 3 — Nómina

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar la nómina semanal: liquidaciones `NOM-YYYY-NNN` por periodo, items que bloquean turnos contra pago duplicado, abonos a conductores, neto por conductor, marcado de pago, y vistas funcionales. Incluye además dos handoffs del Plan 2: refactor de `Shift.save()` para permitir edición manual del valor con auditoría (I6) y el servicio de finalizar operación que libera mulas (I5).

**Architecture:** Django 5.2 monolítico. Nueva app `apps/nomina` con modelos `Payroll`, `PayrollItem`, `DriverAdvance`. Servicios en `apps/nomina/services.py`. Refactor mínimo de `Shift.save()` en `apps/operaciones/models.py` (recalcular `valor_pagado` solo al cambiar de estado). Servicio `finalizar_operacion` añadido a `apps/operaciones/services.py`. Vistas basadas en funciones con `@login_required`.

**Tech Stack:** Django 5.2, HTMX (base.html), `AuditMixin`, `Shift`/`Operation` de `apps.operaciones`, `Driver` de `apps.conductores`.

**Spec de referencia:** `docs/superpowers/specs/2026-08-15-puerto-ops-design.md` (secciones 5, 20-22, 33). Handoffs del Plan 2 (ledger `plan2-operaciones/progress.md`): I6 (Shift.save recálculo incondicional), I5 (liberar_mulas sin llamador).

## Global Constraints

- Zona `America/Bogota`. Moneda COP `DecimalField(max_digits=14, decimal_places=0)`.
- Todos los modelos heredan `AuditMixin` (created/updated + history).
- No eliminación física: estados.
- Número de liquidación: `NOM-YYYY-NNN` secuencial por año (ej. NOM-2026-033). Generación única y atómica.
- Estados `Payroll`: `pendiente | liquidado | pagado`. `fecha_pago` se fija al marcar pagada.
- Un turno puede estar en una sola liquidación (`PayrollItem.shift` unique) → **impide pago duplicado**.
- Solo turnos `realizado` sin liquidación asociada entran en una liquidación, filtrados por `fecha_inicio` dentro del periodo.
- Neto por conductor = Σ valores de sus turnos en la liquidación − Σ abonos del conductor vinculados a esa liquidación.
- `DriverAdvance.payroll` es nullable: si está fijado, descuenta en esa liquidación.
- `Shift.valor_pagado` es editable con auditoría (valor original, nuevo, motivo, usuario, fecha vía simple-history). El `save()` NO debe sobreescribir una edición manual cuando el estado no cambia.
- Git SOLO LOCAL (sin remoto). Cada task termina con tests en verde y commit local.
- Idioma español (es-co).

---

### Task 1: Modelo Payroll y generación del número NOM-YYYY-NNN

**Files:**
- Create: `apps/nomina/__init__.py`
- Create: `apps/nomina/apps.py`
- Create: `apps/nomina/models.py`
- Create: `apps/nomina/admin.py`
- Create: `apps/nomina/tests/__init__.py`
- Create: `apps/nomina/tests/test_models.py`
- Create: `apps/nomina/services.py`
- Modify: `config/settings/base.py` (añadir `"apps.nomina"` a INSTALLED_APPS)

**Interfaces:**
- Consumes: `apps.core.models.AuditMixin`.
- Produces:
  - `class Payroll(AuditMixin)`:
    - `numero` CharField(20, unique), `periodo_inicio` DateField, `periodo_fin` DateField, `estado` (choices: pendiente/liquidado/pagado, default pendiente), `total` Decimal(14,0) default 0, `fecha_pago` DateField null/blank, `observaciones` TextField blank.
    - constantes `PENDIENTE/LIQUIDADO/PAGADO`, `ESTADOS`.
    - `__str__` → `numero`.
  - `def generar_numero_liquidacion(anio) -> str` en `apps/nomina/services.py` — busca el último número con prefijo `NOM-<anio>-`, suma 1 con 3 dígitos; si no existe, `NOM-<anio>-001`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/nomina/tests/test_models.py`:

```python
from datetime import date

from django.test import TestCase

from apps.nomina.models import Payroll
from apps.nomina.services import generar_numero_liquidacion


class PayrollTests(TestCase):
    def test_creation_y_str(self):
        p = Payroll.objects.create(
            numero="NOM-2026-001",
            periodo_inicio=date(2026, 8, 10),
            periodo_fin=date(2026, 8, 16),
        )
        self.assertEqual(str(p), "NOM-2026-001")
        self.assertEqual(p.estado, Payroll.PENDIENTE)
        self.assertIsNone(p.fecha_pago)

    def test_numero_unique(self):
        from django.db import IntegrityError

        Payroll.objects.create(
            numero="NOM-2026-001",
            periodo_inicio=date(2026, 8, 10),
            periodo_fin=date(2026, 8, 16),
        )
        with self.assertRaises(IntegrityError):
            Payroll.objects.create(
                numero="NOM-2026-001",
                periodo_inicio=date(2026, 8, 17),
                periodo_fin=date(2026, 8, 23),
            )

    def test_estado_pagado_fija_fecha_pago(self):
        p = Payroll.objects.create(
            numero="NOM-2026-002",
            periodo_inicio=date(2026, 8, 10),
            periodo_fin=date(2026, 8, 16),
            estado=Payroll.PAGADO,
            fecha_pago=date(2026, 8, 16),
        )
        self.assertEqual(p.fecha_pago, date(2026, 8, 16))


class GenerarNumeroLiquidacionTests(TestCase):
    def test_primer_numero_del_anio(self):
        self.assertEqual(generar_numero_liquidacion(2026), "NOM-2026-001")

    def test_numero_secuencial(self):
        Payroll.objects.create(
            numero="NOM-2026-001",
            periodo_inicio=date(2026, 8, 10),
            periodo_fin=date(2026, 8, 16),
        )
        Payroll.objects.create(
            numero="NOM-2026-002",
            periodo_inicio=date(2026, 8, 17),
            periodo_fin=date(2026, 8, 23),
        )
        self.assertEqual(generar_numero_liquidacion(2026), "NOM-2026-003")

    def test_anios_separados(self):
        Payroll.objects.create(
            numero="NOM-2025-005",
            periodo_inicio=date(2025, 12, 29),
            periodo_fin=date(2026, 1, 4),
        )
        self.assertEqual(generar_numero_liquidacion(2026), "NOM-2026-001")
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.nomina.tests -v 2`
Expected: FAIL — `ModuleNotFoundError: apps.nomina.models`.

- [ ] **Step 3: Registrar la app y crear modelo + servicio**

En `config/settings/base.py`, añadir `"apps.nomina",` después de `"apps.operaciones",`.

Crear `apps/nomina/__init__.py` (vacío), `apps/nomina/apps.py`:

```python
from django.apps import AppConfig


class NominaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.nomina"
```

Crear `apps/nomina/models.py`:

```python
from django.db import models

from apps.core.models import AuditMixin


class Payroll(AuditMixin):
    PENDIENTE = "pendiente"
    LIQUIDADO = "liquidado"
    PAGADO = "pagado"

    ESTADOS = [
        (PENDIENTE, "Pendiente"),
        (LIQUIDADO, "Liquidado"),
        (PAGADO, "Pagado"),
    ]

    numero = models.CharField(max_length=20, unique=True)
    periodo_inicio = models.DateField()
    periodo_fin = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default=PENDIENTE)
    total = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    fecha_pago = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Liquidación de nómina"
        verbose_name_plural = "Liquidaciones de nómina"
        ordering = ["-periodo_inicio"]

    def __str__(self):
        return self.numero
```

Crear `apps/nomina/services.py`:

```python
from apps.nomina.models import Payroll


def generar_numero_liquidacion(anio):
    prefix = f"NOM-{anio}-"
    ultimo = (
        Payroll.objects.filter(numero__startswith=prefix)
        .order_by("-numero")
        .first()
    )
    if ultimo is None:
        return f"{prefix}001"
    secuencia = int(ultimo.numero.rsplit("-", 1)[1]) + 1
    return f"{prefix}{secuencia:03d}"
```

Crear `apps/nomina/admin.py`:

```python
from django.contrib import admin

from apps.nomina.models import Payroll


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ("numero", "periodo_inicio", "periodo_fin", "estado", "total", "fecha_pago")
    list_filter = ("estado",)
    search_fields = ("numero",)
```

- [ ] **Step 4: Generar y aplicar migraciones**

```bash
python manage.py makemigrations nomina
python manage.py migrate
```

- [ ] **Step 5: Verificar que pasa**

Run: `python manage.py test apps.nomina.tests -v 2`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "feat(nomina): modelo Payroll y generacion de numero NOM-YYYY-NNN"
```

---

### Task 2: PayrollItem — bloqueo de turnos contra pago duplicado

**Files:**
- Modify: `apps/nomina/models.py` (añadir PayrollItem)
- Create: `apps/nomina/tests/test_payroll_item.py`

**Interfaces:**
- Consumes: `Payroll` (Task 1), `apps.operaciones.models.Shift`.
- Produces:
  - `class PayrollItem(AuditMixin)`: `payroll` FK Payroll related_name="items", `shift` FK Shift related_name="payroll_items" con **unique=True** (un turno SOLO en una liquidación → impide pago duplicado), `valor` Decimal(14,0).
  - `@property PayrollItem.es_pagable` — no necesario; el estado lo define `Payroll`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/nomina/tests/test_payroll_item.py`:

```python
from datetime import date, timedelta

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.nomina.models import Payroll, PayrollItem
from apps.operaciones.models import Operation, Shift


class PayrollItemTests(TestCase):
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
        self.shift = Shift.objects.create(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, 10, 6, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, 10, 17, 0)),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )
        self.payroll = Payroll.objects.create(
            numero="NOM-2026-001",
            periodo_inicio=date(2026, 8, 10),
            periodo_fin=date(2026, 8, 16),
        )

    def test_creacion_item(self):
        item = PayrollItem.objects.create(
            payroll=self.payroll, shift=self.shift, valor=180000
        )
        self.assertEqual(item.valor, 180000)
        self.assertEqual(self.payroll.items.count(), 1)

    def test_un_turno_no_puede_estar_en_dos_liquidaciones(self):
        PayrollItem.objects.create(payroll=self.payroll, shift=self.shift, valor=180000)
        otra = Payroll.objects.create(
            numero="NOM-2026-002",
            periodo_inicio=date(2026, 8, 17),
            periodo_fin=date(2026, 8, 23),
        )
        with self.assertRaises(IntegrityError):
            PayrollItem.objects.create(payroll=otra, shift=self.shift, valor=180000)

    def test_relacion_inversa_shift_payroll_items(self):
        PayrollItem.objects.create(payroll=self.payroll, shift=self.shift, valor=180000)
        self.assertEqual(self.shift.payroll_items.count(), 1)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.nomina.tests.test_payroll_item -v 2`
Expected: FAIL — `ModuleNotFoundError: apps.nomina.models` para PayrollItem / field missing.

- [ ] **Step 3: Implementación mínima**

Añadir a `apps/nomina/models.py`:

```python
from apps.operaciones.models import Shift


class PayrollItem(AuditMixin):
    payroll = models.ForeignKey(
        Payroll, on_delete=models.CASCADE, related_name="items"
    )
    shift = models.ForeignKey(
        Shift, on_delete=models.PROTECT, related_name="payroll_items", unique=True
    )
    valor = models.DecimalField(max_digits=14, decimal_places=0)

    class Meta:
        verbose_name = "Item de liquidación"
        verbose_name_plural = "Items de liquidación"

    def __str__(self):
        return f"{self.payroll.numero} - {self.shift}"
```

- [ ] **Step 4: Migración y verificación**

```bash
python manage.py makemigrations nomina
python manage.py migrate
python manage.py test apps.nomina.tests -v 2
```

Expected: PASS (9 tests total en apps.nomina).

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "feat(nomina): PayrollItem bloquea turnos contra pago duplicado"
```

---

### Task 3: Modelo DriverAdvance — abonos a conductores

**Files:**
- Modify: `apps/nomina/models.py` (añadir DriverAdvance)
- Create: `apps/nomina/tests/test_driver_advance.py`

**Interfaces:**
- Consumes: `Driver` (apps.conductores), `Payroll` (Task 1).
- Produces:
  - `class DriverAdvance(AuditMixin)`: `driver` FK Driver related_name="abonos", `fecha` DateField default timezone.localdate, `valor` Decimal(14,0), `descripcion` CharField(200) blank, `payroll` FK Payroll null/blank related_name="abonos" (si está fijado, descuenta en esa liquidación).

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/nomina/tests/test_driver_advance.py`:

```python
from datetime import date

from django.test import TestCase

from apps.conductores.models import Driver
from apps.nomina.models import DriverAdvance, Payroll


class DriverAdvanceTests(TestCase):
    def setUp(self):
        self.driver = Driver.objects.create(nombre="Juan Pérez", documento="123")

    def test_creacion_abono_sin_liquidacion(self):
        a = DriverAdvance.objects.create(driver=self.driver, valor=150000)
        self.assertEqual(a.valor, 150000)
        self.assertIsNone(a.payroll)

    def test_abono_vinculado_a_liquidacion(self):
        payroll = Payroll.objects.create(
            numero="NOM-2026-001",
            periodo_inicio=date(2026, 8, 10),
            periodo_fin=date(2026, 8, 16),
        )
        a = DriverAdvance.objects.create(driver=self.driver, valor=150000, payroll=payroll)
        self.assertEqual(a.payroll, payroll)
        self.assertEqual(payroll.abonos.count(), 1)

    def test_str(self):
        a = DriverAdvance.objects.create(driver=self.driver, valor=150000)
        self.assertIn("Juan Pérez", str(a))
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.nomina.tests.test_driver_advance -v 2`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implementación mínima**

Añadir a `apps/nomina/models.py`:

```python
from django.utils import timezone

from apps.conductores.models import Driver


class DriverAdvance(AuditMixin):
    driver = models.ForeignKey(
        Driver, on_delete=models.PROTECT, related_name="abonos"
    )
    fecha = models.DateField(default=timezone.localdate)
    valor = models.DecimalField(max_digits=14, decimal_places=0)
    descripcion = models.CharField(max_length=200, blank=True, default="")
    payroll = models.ForeignKey(
        Payroll, null=True, blank=True, on_delete=models.SET_NULL, related_name="abonos"
    )

    class Meta:
        verbose_name = "Abono a conductor"
        verbose_name_plural = "Abonos a conductores"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.driver.nombre} ${self.valor}"
```

- [ ] **Step 4: Migración y verificación**

```bash
python manage.py makemigrations nomina
python manage.py migrate
python manage.py test apps.nomina.tests -v 2
```

Expected: PASS (12 tests en apps.nomina).

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "feat(nomina): abonos a conductores vinculables a liquidacion"
```

---

### Task 4: Refactor Shift.save() para edición manual del valor (handoff I6)

**Files:**
- Modify: `apps/operaciones/models.py` (`Shift.save`)
- Modify: `apps/operaciones/tests/test_shift.py` (nuevo test)

**Interfaces:**
- Consumes: `Shift` (Plan 2).
- Produces: `Shift.save()` recalcula `horas_trabajadas`/`cumplimiento_pct` siempre, pero **`valor_pagado` SOLO se auto-ajusta cuando el estado cambia** o en creación. Si el estado no cambia (edición manual del valor), respeta el valor ya guardado. Debe mantenerse el comportamiento: crear con estado REALIZADO → valor_pagado = valor_estandar; cancelar/anular → valor_pagado = 0; editar valor sin cambiar estado → respeta el valor editado.

- [ ] **Step 1: Escribir el test que falla**

Añadir a `apps/operaciones/tests/test_shift.py` dentro de `ShiftTests`:

```python
    def test_edicion_manual_del_valor_no_es_sobreescrita(self):
        shift = self._crear_shift(
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
            estado=Shift.REALIZADO,
        )
        self.assertEqual(shift.valor_pagado, 180000)
        shift.valor_pagado = 200000
        shift.observaciones = "Ajuste manual"
        shift.save()
        shift.refresh_from_db()
        self.assertEqual(shift.valor_pagado, 200000)

    def test_cancelar_resetea_valor_pagado(self):
        shift = self._crear_shift(
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
            estado=Shift.REALIZADO,
        )
        self.assertEqual(shift.valor_pagado, 180000)
        shift.estado = Shift.CANCELADO
        shift.motivo_cancelacion = "Avería"
        shift.save()
        shift.refresh_from_db()
        self.assertEqual(shift.valor_pagado, 0)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.operaciones.tests.test_shift -v 2`
Expected: `test_edicion_manual_del_valor_no_es_sobreescrita` FALLA (el save() actual reajusta a 180000). El segundo test debe pasar ya.

- [ ] **Step 3: Implementación mínima**

En `apps/operaciones/models.py`, reemplazar `Shift.save()`:

```python
    def save(self, *args, **kwargs):
        delta = self.fecha_fin - self.fecha_inicio
        self.horas_trabajadas = round(delta.total_seconds() / 3600, 2)
        if self.meta_horas:
            self.cumplimiento_pct = round(
                float(self.horas_trabajadas) / float(self.meta_horas) * 100, 1
            )
        estado_anterior = None
        if self.pk:
            estado_anterior = (
                Shift.objects.filter(pk=self.pk)
                .values_list("estado", flat=True)
                .first()
            )
        if estado_anterior is None or estado_anterior != self.estado:
            if self.estado == self.REALIZADO:
                self.valor_pagado = self.valor_estandar
            else:
                self.valor_pagado = 0
        super().save(*args, **kwargs)
```

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.operaciones.tests -v 2`
Expected: PASS. Luego suite completa `python manage.py test -v 2` — todos los tests previos (incluidos los de incidentes/cancelación) deben seguir pasando.

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "fix(operaciones): Shift.save no sobreescribe valor pagado en edicion manual"
```

---

### Task 5: Servicios de nómina — liquidar periodo, resumen por conductor, marcar pagada

**Files:**
- Modify: `apps/nomina/services.py` (añadir servicios)
- Create: `apps/nomina/tests/test_services.py`

**Interfaces:**
- Consumes: `Payroll`, `PayrollItem`, `DriverAdvance` (Tasks 1-3), `Shift` (apps.operaciones), `generar_numero_liquidacion`.
- Produces:
  - `def turnos_pendientes_pago(desde, hasta) -> QuerySet[Shift]` — shifts `realizado` sin `payroll_items`, con `fecha_inicio` entre `desde` y `hasta` (fechas).
  - `def crear_liquidacion(desde, hasta, usuario=None) -> Payroll` — en `transaction.atomic`: genera número con `generar_numero_liquidacion(desde.year)`, crea `Payroll` (estado `liquidado`), crea `PayrollItem` por cada turno pendiente con `valor = shift.valor_pagado`, `total = Σ valores`. Si no hay turnos pendientes → `ValidationError`. Fija `created_by`/`updated_by` si hay usuario.
  - `def resumen_liquidacion(payroll) -> list[dict]` — agrupa los items por conductor: `{"driver": Driver, "total": Decimal, "abonos": Decimal, "neto": Decimal}`. `abonos` = Σ DriverAdvance del payroll para ese conductor; `neto = total - abonos`. Ordenado por nombre de conductor.
  - `def marcar_pagada(payroll, usuario=None) -> None` — estado → `pagado`, `fecha_pago = timezone.localdate()`, guarda `updated_by`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/nomina/tests/test_services.py`:

```python
from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.nomina.models import DriverAdvance, Payroll
from apps.nomina.services import (
    crear_liquidacion,
    marcar_pagada,
    resumen_liquidacion,
    turnos_pendientes_pago,
)
from apps.operaciones.models import Operation, Shift


class NominaServicesTests(TestCase):
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

    def _shift(self, driver, vehicle, dia, estado=Shift.REALIZADO, tipo=Shift.DIA):
        return Shift.objects.create(
            operation=self.op,
            vehicle=vehicle,
            driver=driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, dia, 6, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, dia, 17, 0)),
            tipo=tipo,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia if tipo == Shift.DIA else self.op.valor_turno_noche,
            estado=estado,
        )

    def test_turnos_pendientes_filtra_estado_y_periodo(self):
        s1 = self._shift(self.juan, self.v1, 10)
        self._shift(self.juan, self.v2, 20, estado=Shift.REALIZADO)
        self._shift(self.juan, self.v1, 11, estado=Shift.CANCELADO)
        pendientes = turnos_pendientes_pago(date(2026, 8, 10), date(2026, 8, 16))
        self.assertEqual(list(pendientes), [s1])

    def test_turnos_pendientes_excluye_ya_liquidados(self):
        s1 = self._shift(self.juan, self.v1, 10)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        self.assertEqual(payroll.items.count(), 1)
        self.assertEqual(list(turnos_pendientes_pago(date(2026, 8, 10), date(2026, 8, 16))), [])

    def test_crear_liquidacion_numero_y_total(self):
        self._shift(self.juan, self.v1, 10)
        self._shift(self.juan, self.v2, 11)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        self.assertEqual(payroll.numero, "NOM-2026-001")
        self.assertEqual(payroll.estado, Payroll.LIQUIDADO)
        self.assertEqual(payroll.total, 360000)
        self.assertEqual(payroll.items.count(), 2)

    def test_crear_liquidacion_sin_turnos_levanta_error(self):
        with self.assertRaises(ValidationError):
            crear_liquidacion(date(2026, 9, 1), date(2026, 9, 7))

    def test_resumen_liquidacion_con_abonos(self):
        self._shift(self.juan, self.v1, 10)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        DriverAdvance.objects.create(driver=self.juan, valor=150000, payroll=payroll)
        resumen = resumen_liquidacion(payroll)
        self.assertEqual(len(resumen), 1)
        fila = resumen[0]
        self.assertEqual(fila["driver"], self.juan)
        self.assertEqual(fila["total"], 180000)
        self.assertEqual(fila["abonos"], 150000)
        self.assertEqual(fila["neto"], 30000)

    def test_marcar_pagada(self):
        self._shift(self.juan, self.v1, 10)
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        marcar_pagada(payroll)
        payroll.refresh_from_db()
        self.assertEqual(payroll.estado, Payroll.PAGADO)
        self.assertEqual(payroll.fecha_pago, timezone.localdate())
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.nomina.tests.test_services -v 2`
Expected: FAIL — funciones ausentes.

- [ ] **Step 3: Implementación mínima**

Añadir a `apps/nomina/services.py`:

```python
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.nomina.models import DriverAdvance, Payroll, PayrollItem
from apps.operaciones.models import Shift


def turnos_pendientes_pago(desde, hasta):
    return (
        Shift.objects.filter(
            estado=Shift.REALIZADO,
            fecha_inicio__date__gte=desde,
            fecha_inicio__date__lte=hasta,
            payroll_items__isnull=True,
        )
        .select_related("driver", "vehicle", "operation")
        .order_by("fecha_inicio")
    )


def crear_liquidacion(desde, hasta, usuario=None):
    turnos = list(turnos_pendientes_pago(desde, hasta))
    if not turnos:
        raise ValidationError(
            "No hay turnos pendientes de pago en el periodo seleccionado."
        )
    with transaction.atomic():
        payroll = Payroll.objects.create(
            numero=generar_numero_liquidacion(desde.year),
            periodo_inicio=desde,
            periodo_fin=hasta,
            estado=Payroll.LIQUIDADO,
            created_by=usuario,
            updated_by=usuario,
        )
        total = 0
        for shift in turnos:
            total += shift.valor_pagado
            PayrollItem.objects.create(
                payroll=payroll, shift=shift, valor=shift.valor_pagado
            )
        payroll.total = total
        payroll.save(update_fields=["total"])
    return payroll


def resumen_liquidacion(payroll):
    items = (
        payroll.items.select_related("shift__driver")
        .order_by("shift__driver__nombre")
    )
    resumen = {}
    for item in items:
        driver = item.shift.driver
        if driver.pk not in resumen:
            resumen[driver.pk] = {
                "driver": driver,
                "total": 0,
                "abonos": 0,
                "neto": 0,
            }
        resumen[driver.pk]["total"] += item.valor
    abonos = (
        payroll.abonos.select_related("driver")
        .values("driver_id")
        .annotate(total=Sum("valor"))
    )
    for fila in abonos:
        pk = fila["driver_id"]
        if pk in resumen:
            resumen[pk]["abonos"] = fila["total"]
    for fila in resumen.values():
        fila["neto"] = fila["total"] - fila["abonos"]
    return sorted(resumen.values(), key=lambda f: f["driver"].nombre)
```

Nota: añadir `from django.db.models import Sum` en services.py. El total es Decimal(14,0); las sumas de DecimalFields devuelven Decimal, por lo que `total - abonos` es correcto.

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.nomina.tests.test_services -v 2`
Expected: PASS (6 tests). Si `fila["neto"]` falla por tipo (int vs Decimal), ajustar `fila["total"] = Decimal(fila["total"])` o inicializar con Decimal(0).

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "feat(nomina): liquidacion por periodo, resumen por conductor y marcar pagada"
```

---

### Task 6: Vistas funcionales de nómina y abonos

**Files:**
- Create: `apps/nomina/urls.py`
- Create: `apps/nomina/views.py`
- Create: `apps/nomina/forms.py`
- Create: `templates/nomina/payroll_list.html`
- Create: `templates/nomina/payroll_detail.html`
- Create: `templates/nomina/payroll_form.html`
- Create: `apps/nomina/tests/test_views.py`
- Modify: `config/urls.py` (incluir `apps.nomina.urls` bajo prefijo `nomina/`)
- Modify: `static/css/app.css` (estilos `.tag`, `.tag-ok`, `.tag-warn`, `.tag-danger` si no existen)

**Interfaces:**
- Consumes: `crear_liquidacion`, `resumen_liquidacion`, `marcar_pagada`, `DriverAdvance`, `Payroll`.
- Produces:
  - URL namespace `nomina`:
    - `nomina:lista` → listado de liquidaciones.
    - `nomina:nueva` → formulario de periodo (inicio/fin) → crear_liquidacion → redirect detalle.
    - `nomina:detalle` (`<int:pk>/`) → resumen por conductor, items, abonos.
    - `nomina:abono_nuevo` (`<int:pk>/abonos/nuevo/`) → registrar abono vinculado a esa liquidación.
    - `nomina:marcar_pagada` (`<int:pk>/marcar-pagada/`) → POST → marcar_pagada → redirect detalle.
  - Todas `@login_required`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/nomina/tests/test_views.py`:

```python
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.nomina.models import Payroll
from apps.nomina.services import crear_liquidacion
from apps.operaciones.models import Operation, Shift


class NominaViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
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
        Shift.objects.create(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, 10, 6, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, 10, 17, 0)),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )
        self.client.force_login(self.user)

    def test_lista_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse("nomina:lista"))
        self.assertEqual(response.status_code, 302)

    def test_crear_liquidacion_via_post(self):
        response = self.client.post(
            reverse("nomina:nueva"),
            {"periodo_inicio": "10/08/2026", "periodo_fin": "16/08/2026"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Payroll.objects.count(), 1)
        self.assertEqual(Payroll.objects.first().numero, "NOM-2026-001")

    def test_detalle_muestra_conductor_y_neto(self):
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        response = self.client.get(reverse("nomina:detalle", args=[payroll.pk]))
        self.assertContains(response, "Juan Pérez")
        self.assertContains(response, "NOM-2026-001")

    def test_marcar_pagada_via_post(self):
        payroll = crear_liquidacion(date(2026, 8, 10), date(2026, 8, 16))
        response = self.client.post(reverse("nomina:marcar_pagada", args=[payroll.pk]))
        self.assertEqual(response.status_code, 302)
        payroll.refresh_from_db()
        self.assertEqual(payroll.estado, Payroll.PAGADO)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.nomina.tests.test_views -v 2`
Expected: FAIL — `NoReverseMatch` para `nomina:lista`.

- [ ] **Step 3: Implementar vistas y URLs**

Crear `apps/nomina/urls.py`:

```python
from django.urls import path

from apps.nomina import views

app_name = "nomina"

urlpatterns = [
    path("", views.payroll_list, name="lista"),
    path("nueva/", views.payroll_nueva, name="nueva"),
    path("<int:pk>/", views.payroll_detail, name="detalle"),
    path("<int:pk>/abonos/nuevo/", views.abono_nuevo, name="abono_nuevo"),
    path("<int:pk>/marcar-pagada/", views.marcar_pagada, name="marcar_pagada"),
]
```

En `config/urls.py`, añadir:

```python
path("nomina/", include("apps.nomina.urls")),
```

Crear `apps/nomina/forms.py`:

```python
from django import forms

from apps.nomina.models import DriverAdvance


class PeriodoForm(forms.Form):
    periodo_inicio = forms.DateField(label="Inicio del periodo", input_formats=["%d/%m/%Y", "%Y-%m-%d"])
    periodo_fin = forms.DateField(label="Fin del periodo", input_formats=["%d/%m/%Y", "%Y-%m-%d"])

    def clean(self):
        data = super().clean()
        if data.get("periodo_inicio") and data.get("periodo_fin"):
            if data["periodo_fin"] < data["periodo_inicio"]:
                raise forms.ValidationError("El fin del periodo no puede ser anterior al inicio.")
        return data


class DriverAdvanceForm(forms.ModelForm):
    class Meta:
        model = DriverAdvance
        fields = ["driver", "valor", "descripcion", "fecha"]
```

Crear `apps/nomina/views.py`:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.nomina.forms import DriverAdvanceForm, PeriodoForm
from apps.nomina.models import DriverAdvance, Payroll
from apps.nomina.services import crear_liquidacion, marcar_pagada, resumen_liquidacion


@login_required
def payroll_list(request):
    payrolls = Payroll.objects.prefetch_related("items").all()
    return render(request, "nomina/payroll_list.html", {"payrolls": payrolls})


@login_required
def payroll_nueva(request):
    if request.method == "POST":
        form = PeriodoForm(request.POST)
        if form.is_valid():
            payroll = crear_liquidacion(
                form.cleaned_data["periodo_inicio"],
                form.cleaned_data["periodo_fin"],
                usuario=request.user,
            )
            return redirect("nomina:detalle", pk=payroll.pk)
    else:
        form = PeriodoForm()
    return render(request, "nomina/payroll_form.html", {"form": form})


@login_required
def payroll_detail(request, pk):
    payroll = get_object_or_404(Payroll, pk=pk)
    context = {
        "payroll": payroll,
        "resumen": resumen_liquidacion(payroll),
        "abono_form": DriverAdvanceForm(),
    }
    return render(request, "nomina/payroll_detail.html", context)


@login_required
def abono_nuevo(request, pk):
    payroll = get_object_or_404(Payroll, pk=pk)
    form = DriverAdvanceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        abono = form.save(commit=False)
        abono.payroll = payroll
        abono.created_by = request.user
        abono.updated_by = request.user
        abono.save()
        return redirect("nomina:detalle", pk=payroll.pk)
    return redirect("nomina:detalle", pk=payroll.pk)


@login_required
def marcar_pagada(request, pk):
    payroll = get_object_or_404(Payroll, pk=pk)
    if request.method == "POST":
        marcar_pagada(payroll, usuario=request.user)
    return redirect("nomina:detalle", pk=payroll.pk)
```

- [ ] **Step 4: Crear plantillas**

Crear `templates/nomina/payroll_list.html`:

```html
{% extends "base.html" %}
{% block title %}Nómina{% endblock %}
{% block content %}
<p class="eyebrow">Transportes Renacer</p>
<h1>Liquidaciones de nómina</h1>
<a class="btn btn-primary" href="{% url 'nomina:nueva' %}">Nueva liquidación</a>
<table class="table">
  <thead><tr><th>Número</th><th>Periodo</th><th>Estado</th><th>Total</th><th>Fecha pago</th></tr></thead>
  <tbody>
  {% for p in payrolls %}
    <tr>
      <td><a href="{% url 'nomina:detalle' p.pk %}">{{ p.numero }}</a></td>
      <td>{{ p.periodo_inicio|date:"d/m/Y" }} – {{ p.periodo_fin|date:"d/m/Y" }}</td>
      <td>{{ p.get_estado_display }}</td>
      <td>${{ p.total }}</td>
      <td>{{ p.fecha_pago|date:"d/m/Y"|default:"—" }}</td>
    </tr>
  {% empty %}
    <tr><td colspan="5">No hay liquidaciones.</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
```

Crear `templates/nomina/payroll_form.html`:

```html
{% extends "base.html" %}
{% block title %}Nueva liquidación{% endblock %}
{% block content %}
<p class="eyebrow">Nómina</p>
<h1>Nueva liquidación</h1>
<form method="post" class="card">
  {% csrf_token %}
  {{ form.as_p }}
  <button type="submit" class="btn btn-primary">Liquidar periodo</button>
</form>
{% endblock %}
```

Crear `templates/nomina/payroll_detail.html`:

```html
{% extends "base.html" %}
{% block title %}{{ payroll.numero }}{% endblock %}
{% block content %}
<p class="eyebrow">Liquidación</p>
<h1>{{ payroll.numero }}</h1>
<p>Periodo: {{ payroll.periodo_inicio|date:"d/m/Y" }} – {{ payroll.periodo_fin|date:"d/m/Y" }}</p>
<p>Estado: <span class="tag">{{ payroll.get_estado_display }}</span></p>
<p>Total: <strong>${{ payroll.total }}</strong></p>
{% if payroll.estado != 'pagado' %}
  <form method="post" action="{% url 'nomina:marcar_pagada' payroll.pk %}">
    {% csrf_token %}
    <button type="submit" class="btn btn-primary">Marcar como pagada</button>
  </form>
{% endif %}
<h2>Resumen por conductor</h2>
<table class="table">
  <thead><tr><th>Conductor</th><th>Total</th><th>Abonos</th><th>Neto</th></tr></thead>
  <tbody>
  {% for fila in resumen %}
    <tr>
      <td>{{ fila.driver.nombre }}</td>
      <td>${{ fila.total }}</td>
      <td>${{ fila.abonos }}</td>
      <td><strong>${{ fila.neto }}</strong></td>
    </tr>
  {% empty %}
    <tr><td colspan="4">Sin turnos en esta liquidación.</td></tr>
  {% endfor %}
  </tbody>
</table>
<h2>Registrar abono a conductor</h2>
<form method="post" action="{% url 'nomina:abono_nuevo' payroll.pk %}" class="card">
  {% csrf_token %}
  {{ abono_form.as_p }}
  <button type="submit" class="btn btn-primary">Registrar abono</button>
</form>
{% endblock %}
```

Añadir estilos `.tag` a `static/css/app.css`:

```css
.tag {
  display: inline-block; padding: 3px 10px; border-radius: 20px;
  font-size: 12px; font-weight: 600;
  background: var(--surface-hover); color: var(--ink-dim);
}
```

- [ ] **Step 5: Verificar que pasa**

Run: `python manage.py test apps.nomina.tests.test_views -v 2`
Expected: PASS (4 tests). Ajustar `PeriodoForm` si el parseo de fechas `%d/%m/%Y` falla con el input del test.

- [ ] **Step 6: Suite completa**

Run: `python manage.py test -v 2`
Expected: PASS (tests previos + nuevos = ~80). `python manage.py check` limpio.

- [ ] **Step 7: Commit local**

```bash
git add -A
git commit -m "feat(nomina): vistas funcionales de liquidaciones y abonos"
```

---

### Task 7: Servicio finalizar_operacion (handoff I5) — libera mulas y pasa a historial

**Files:**
- Modify: `apps/operaciones/services.py` (añadir finalizar_operacion)
- Create: `apps/operaciones/tests/test_finalizar.py`

**Interfaces:**
- Consumes: `Operation`, `liberar_mulas` (Plan 2), `asignar_mulas`.
- Produces:
  - `def finalizar_operacion(operation, usuario=None) -> None` — si la operación está `activa` o `programada`: estado → `finalizada`, `fecha_fin_real = timezone.localdate()`, `updated_by = usuario`, guarda; luego `liberar_mulas(operation)`. Si ya está finalizada o cancelada → no-op (idempotente).
  - `def cancelar_operacion(operation, usuario=None) -> None` — estado → `cancelada`, `fecha_fin_real = timezone.localdate()`, `updated_by = usuario`, guarda; luego `liberar_mulas(operation)`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/operaciones/tests/test_finalizar.py`:

```python
from datetime import date

from django.test import TestCase

from apps.catalogos.models import CargoGenerator, Port
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation
from apps.operaciones.services import (
    asignar_mulas,
    cancelar_operacion,
    finalizar_operacion,
    liberar_mulas,
)


class FinalizarOperacionTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.v1 = Vehicle.objects.create(placa="ABC123")
        self.op = Operation.objects.create(
            codigo="OP-001",
            buque="BUQUE ATLANTIC",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
            estado=Operation.ACTIVA,
        )

    def test_finalizar_cambia_estado_y_fecha_real(self):
        finalizar_operacion(self.op)
        self.op.refresh_from_db()
        self.assertEqual(self.op.estado, Operation.FINALIZADA)
        self.assertIsNotNone(self.op.fecha_fin_real)

    def test_finalizar_libera_mulas(self):
        asignar_mulas(self.op, [self.v1])
        finalizar_operacion(self.op)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.estado, Vehicle.DISPONIBLE)
        self.assertFalse(self.op.mulas.get(vehicle=self.v1).activa)

    def test_cancelar_operacion(self):
        asignar_mulas(self.op, [self.v1])
        cancelar_operacion(self.op)
        self.op.refresh_from_db()
        self.assertEqual(self.op.estado, Operation.CANCELADA)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.estado, Vehicle.DISPONIBLE)

    def test_finalizar_es_idempotente(self):
        finalizar_operacion(self.op)
        finalizar_operacion(self.op)
        self.assertEqual(self.op.estado, Operation.FINALIZADA)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.operaciones.tests.test_finalizar -v 2`
Expected: FAIL — `ImportError: cannot import name 'finalizar_operacion'`.

- [ ] **Step 3: Implementación mínima**

Añadir a `apps/operaciones/services.py`:

```python
def finalizar_operacion(operation, usuario=None):
    if operation.estado in (Operation.FINALIZADA, Operation.CANCELADA):
        return
    operation.estado = Operation.FINALIZADA
    operation.fecha_fin_real = timezone.localdate()
    if usuario is not None:
        operation.updated_by = usuario
    operation.save()
    liberar_mulas(operation)


def cancelar_operacion(operation, usuario=None):
    if operation.estado in (Operation.FINALIZADA, Operation.CANCELADA):
        return
    operation.estado = Operation.CANCELADA
    operation.fecha_fin_real = timezone.localdate()
    if usuario is not None:
        operation.updated_by = usuario
    operation.save()
    liberar_mulas(operation)
```

Nota: importar `Operation` en services.py (ya no está importado; añadir `from apps.operaciones.models import ... Operation`).

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.operaciones.tests.test_finalizar -v 2`
Expected: PASS (4 tests). Luego suite completa `python manage.py test -v 2` (~84 tests) y `python manage.py check`.

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "feat(operaciones): servicios de finalizar y cancelar operacion con liberacion de mulas"
```

---

## Self-Review del Plan

**Cobertura del spec (Plan 3):**
- `payrolls` con número NOM-YYYY-NNN único, periodo, estado, total, fecha_pago: Task 1. ✔
- Estados pendiente/liquidado/pagado + no eliminación: Task 1. ✔
- `payroll_items` con turno unique → impide pago duplicado: Task 2. ✔
- `driver_advances` con payroll nullable (descuenta en esa liquidación): Task 3. ✔
- Nómina por periodo (solo turnos realizados sin pagar): Task 5. ✔
- Neto por conductor = total − abonos: Task 5. ✔
- Marcar liquidación pagada (fecha_pago): Task 5 + vista Task 6. ✔
- Vistas funcionales (lista, nueva por periodo, detalle con resumen, registrar abono, marcar pagada): Task 6. ✔
- §14 edición de valor con auditoría → refactor Shift.save (Task 4) habilita que la edición manual no se sobreescriba; la auditoría del cambio queda en simple-history. ✔
- §11 estados de mula al finalizar operación → Task 7 (handoff I5). ✔

**Fuera de este plan:** facturación/saldos/CSV (Plan 4), dashboards/Gantt (Plan 5), edición de valor de turno con formulario/motivo dedicado (mejora posterior; la infraestructura de auditoría ya existe), granularidad de permisos por grupo (decisión del humano pendiente).

**Placeholders:** ninguno; cada paso contiene código o comandos reales.

**Consistencia de tipos:** `crear_liquidacion`/`resumen_liquidacion`/`marcar_pagada`/`turnos_pendientes_pago`/`generar_numero_liquidacion` definidos en servicios y consumidos por vistas/tests con las mismas firmas. `PayrollItem.shift` unique garantiza la restricción de pago duplicado a nivel BD. `Shift.save()` refactorizado respeta la edición manual cuando el estado no cambia y mantiene el comportamiento al cancelar/crear.
