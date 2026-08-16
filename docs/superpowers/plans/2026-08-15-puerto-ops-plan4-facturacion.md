# Plan 4 — Facturación y saldos

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar la facturación por horas y el control de saldos: `BillingRecord` (horas reales × tarifa de la operación, independiente del pago al conductor), `ClientPayment` (abonos del generador de carga), cálculo de saldo por operación, exportación CSV de facturación por operación (sin chofer), y vistas funcionales.

**Architecture:** Django 5.2 monolítico. Nueva app `apps/facturacion` con modelos `BillingRecord` y `ClientPayment`. Servicios en `apps/facturacion/services.py` (generación de billing a partir de turnos realizados, saldo por operación, CSV). Vistas basadas en funciones con `@login_required`. El CSV se genera con el módulo `csv` de Python servido como `StreamingHttpResponse`.

**Tech Stack:** Django 5.2, HTMX (base.html), `AuditMixin`, `Operation`/`Shift` de `apps.operaciones`, `CargoGenerator` de `apps.catalogos`.

**Spec de referencia:** `docs/superpowers/specs/2026-08-15-puerto-ops-design.md` (secciones 5, 23-25, 27, 32, 33).

## Global Constraints

- Zona `America/Bogota`. Moneda COP `DecimalField(max_digits=14, decimal_places=0)`.
- Todos los modelos heredan `AuditMixin` (created/updated + history).
- No eliminación física: estados.
- **Separación estricta (§38)**: `billing_records` (cuánto se cobra) es independiente de `payroll` (cuánto se paga) y de `client_payments` (cuánto se ha recibido). Un turno realizado genera valor facturable aunque el conductor se pague distinto.
- Valor facturado por turno = `horas_trabajadas × tarifa_hora` de la operación (regla §23).
- Solo turnos `realizado` (no cancelados/anulados) generan billing.
- Estados `BillingRecord`: `pendiente | incluido | facturado | cobrado`.
- **Saldo de la operación** = Σ(valor de billing) − Σ(client_payments) de la operación.
- Un turno genera un solo `BillingRecord` (unique por shift) → no facturación duplicada.
- CSV de facturación por operación: columnas Fecha, Operación, Mula, Turno, Hora inicio, Hora final, Horas trabajadas + resumen Mula/Horas totales. **No incluye el chofer** (§24).
- El CSV usa el separador `;` (formato regional colombiano) y codificación UTF-8 con BOM para que abra bien en Excel.
- Git SOLO LOCAL (sin remoto). Cada task termina con tests en verde y commit local.
- Idioma español (es-co).

---

### Task 1: Modelos BillingRecord y ClientPayment

**Files:**
- Create: `apps/facturacion/__init__.py`
- Create: `apps/facturacion/apps.py`
- Create: `apps/facturacion/models.py`
- Create: `apps/facturacion/admin.py`
- Create: `apps/facturacion/tests/__init__.py`
- Create: `apps/facturacion/tests/test_models.py`
- Modify: `config/settings/base.py` (añadir `"apps.facturacion"` a INSTALLED_APPS)

**Interfaces:**
- Consumes: `apps.core.models.AuditMixin`, `apps.operaciones.models.Operation`, `apps.operaciones.models.Shift`.
- Produces:
  - `class BillingRecord(AuditMixin)`:
    - `operation` FK Operation related_name="billing_records" (PROTECT), `shift` FK Shift related_name="billing_record" **unique=True** (un turno → un billing), `fecha` DateField default timezone.localdate, `horas` Decimal(5,2), `tarifa_hora` Decimal(14,0), `valor` Decimal(14,0), `estado` (pendiente/incluido/facturado/cobrado, default pendiente), `observaciones` TextField blank.
    - constantes `PENDIENTE/INCLUIDO/FACTURADO/COBRADO`, `ESTADOS`.
    - `__str__` → `f"{operation.codigo} - {shift.vehicle.placa}"`.
  - `class ClientPayment(AuditMixin)`:
    - `operation` FK Operation related_name="client_payments", `fecha` DateField default timezone.localdate, `valor` Decimal(14,0), `observaciones` TextField blank.
    - `__str__` → `f"{operation.codigo} ${valor}"`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/facturacion/tests/test_models.py`:

```python
from datetime import date

from django.db import IntegrityError
from django.test import TestCase

from apps.catalogos.models import CargoGenerator, Port
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.operaciones.models import Operation


class BillingRecordTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
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

    def test_creation_y_str(self):
        br = BillingRecord.objects.create(
            operation=self.op,
            fecha=date(2026, 8, 10),
            horas=11,
            tarifa_hora=35000,
            valor=385000,
        )
        self.assertEqual(str(br), "OP-001 - None")
        self.assertEqual(br.estado, BillingRecord.PENDIENTE)

    def test_estados_constants(self):
        self.assertEqual(BillingRecord.PENDIENTE, "pendiente")
        self.assertEqual(BillingRecord.COBRADO, "cobrado")


class ClientPaymentTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
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

    def test_creacion_y_str(self):
        cp = ClientPayment.objects.create(operation=self.op, valor=5000000)
        self.assertEqual(str(cp), "OP-001 $5000000")
        self.assertEqual(self.op.client_payments.count(), 1)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.facturacion.tests -v 2`
Expected: FAIL — `ModuleNotFoundError: apps.facturacion.models`.

- [ ] **Step 3: Registrar la app y crear los modelos**

En `config/settings/base.py`, añadir `"apps.facturacion",` después de `"apps.nomina",`.

Crear `apps/facturacion/__init__.py` (vacío), `apps/facturacion/apps.py`:

```python
from django.apps import AppConfig


class FacturacionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.facturacion"
```

Crear `apps/facturacion/models.py`:

```python
from django.db import models
from django.utils import timezone

from apps.core.models import AuditMixin
from apps.operaciones.models import Operation, Shift


class BillingRecord(AuditMixin):
    PENDIENTE = "pendiente"
    INCLUIDO = "incluido"
    FACTURADO = "facturado"
    COBRADO = "cobrado"

    ESTADOS = [
        (PENDIENTE, "Pendiente"),
        (INCLUIDO, "Incluido"),
        (FACTURADO, "Facturado"),
        (COBRADO, "Cobrado"),
    ]

    operation = models.ForeignKey(
        Operation, on_delete=models.PROTECT, related_name="billing_records"
    )
    shift = models.ForeignKey(
        Shift,
        on_delete=models.PROTECT,
        related_name="billing_record",
        null=True,
        blank=True,
        unique=True,
    )
    fecha = models.DateField(default=timezone.localdate)
    horas = models.DecimalField(max_digits=5, decimal_places=2)
    tarifa_hora = models.DecimalField(max_digits=14, decimal_places=0)
    valor = models.DecimalField(max_digits=14, decimal_places=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=PENDIENTE)
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Registro de facturación"
        verbose_name_plural = "Registros de facturación"
        ordering = ["fecha"]

    def __str__(self):
        placa = self.shift.vehicle.placa if self.shift_id else "-"
        return f"{self.operation.codigo} - {placa}"


class ClientPayment(AuditMixin):
    operation = models.ForeignKey(
        Operation, on_delete=models.PROTECT, related_name="client_payments"
    )
    fecha = models.DateField(default=timezone.localdate)
    valor = models.DecimalField(max_digits=14, decimal_places=0)
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Abono del generador de carga"
        verbose_name_plural = "Abonos del generador de carga"
        ordering = ["fecha"]

    def __str__(self):
        return f"{self.operation.codigo} ${self.valor}"
```

Nota: `shift` es nullable para permitir ajustes manuales (§5: "null para ajustes manuales") pero unique para garantizar un solo billing por turno.

Crear `apps/facturacion/admin.py`:

```python
from django.contrib import admin

from apps.facturacion.models import BillingRecord, ClientPayment


@admin.register(BillingRecord)
class BillingRecordAdmin(admin.ModelAdmin):
    list_display = ("operation", "shift", "fecha", "horas", "valor", "estado")
    list_filter = ("estado",)
    search_fields = ("operation__codigo",)


@admin.register(ClientPayment)
class ClientPaymentAdmin(admin.ModelAdmin):
    list_display = ("operation", "fecha", "valor")
    search_fields = ("operation__codigo",)
```

- [ ] **Step 4: Generar y aplicar migraciones**

```bash
python manage.py makemigrations facturacion
python manage.py migrate
```

- [ ] **Step 5: Verificar que pasa**

Run: `python manage.py test apps.facturacion.tests -v 2`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "feat(facturacion): modelos BillingRecord y ClientPayment"
```

---

### Task 2: Servicio de generación de billing por operación

**Files:**
- Create: `apps/facturacion/services.py`
- Create: `apps/facturacion/tests/test_services.py`

**Interfaces:**
- Consumes: `Operation`, `Shift`, `BillingRecord` (Task 1).
- Produces:
  - `def generar_billing_operacion(operation, usuario=None) -> list[BillingRecord]` — para cada shift `realizado` de la operación sin `billing_record` asociado, crea un `BillingRecord` con `horas = shift.horas_trabajadas`, `tarifa_hora = operation.tarifa_hora`, `valor = round(horas × tarifa)`, `fecha = shift.fecha_inicio.date()`, `estado = pendiente`, `created_by/updated_by` si usuario. En `transaction.atomic`. Devuelve la lista creada.
  - `def saldo_operacion(operation) -> Decimal` — Σ(valor de billing_records de la operación) − Σ(valor de client_payments de la operación).
  - `def total_facturado_operacion(operation) -> Decimal` — Σ(valor de billing_records).
  - `def total_abonado_operacion(operation) -> Decimal` — Σ(valor de client_payments).

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/facturacion/tests/test_services.py`:

```python
from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.facturacion.services import (
    generar_billing_operacion,
    saldo_operacion,
    total_abonado_operacion,
    total_facturado_operacion,
)
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift


class GenerarBillingTests(TestCase):
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

    def _shift(self, dia, estado=Shift.REALIZADO, inicio=6, fin=17):
        return Shift.objects.create(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, dia, inicio, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, dia, fin, 0)),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=estado,
        )

    def test_generar_billing_solo_turnos_realizados(self):
        self._shift(10)
        self._shift(11, estado=Shift.CANCELADO)
        creados = generar_billing_operacion(self.op)
        self.assertEqual(len(creados), 1)
        br = creados[0]
        self.assertEqual(br.horas, 11)
        self.assertEqual(br.tarifa_hora, 35000)
        self.assertEqual(br.valor, 385000)

    def test_generar_billing_idempotente(self):
        self._shift(10)
        generar_billing_operacion(self.op)
        segunda = generar_billing_operacion(self.op)
        self.assertEqual(segunda, [])
        self.assertEqual(self.op.billing_records.count(), 1)

    def test_generar_billing_usa_tarifa_congelada_de_la_operacion(self):
        self._shift(10, inicio=6, fin=14)
        creados = generar_billing_operacion(self.op)
        self.assertEqual(creados[0].horas, 8)
        self.assertEqual(creados[0].valor, 280000)


class SaldoOperacionTests(TestCase):
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

    def test_saldo_es_facturado_menos_abonado(self):
        generar_billing_operacion(self.op)
        ClientPayment.objects.create(operation=self.op, valor=200000)
        self.assertEqual(total_facturado_operacion(self.op), 385000)
        self.assertEqual(total_abonado_operacion(self.op), 200000)
        self.assertEqual(saldo_operacion(self.op), 185000)

    def test_saldo_sin_abonos(self):
        generar_billing_operacion(self.op)
        self.assertEqual(saldo_operacion(self.op), 385000)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.facturacion.tests.test_services -v 2`
Expected: FAIL — `ModuleNotFoundError: apps.facturacion.services`.

- [ ] **Step 3: Implementación mínima**

Crear `apps/facturacion/services.py`:

```python
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.facturacion.models import BillingRecord, ClientPayment
from apps.operaciones.models import Shift


def generar_billing_operacion(operation, usuario=None):
    turnos = operation.shifts.filter(
        estado=Shift.REALIZADO, billing_record__isnull=True
    )
    creados = []
    with transaction.atomic():
        for shift in turnos.select_related("vehicle"):
            valor = Decimal(shift.horas_trabajadas) * operation.tarifa_hora
            br = BillingRecord.objects.create(
                operation=operation,
                shift=shift,
                fecha=shift.fecha_inicio.date(),
                horas=shift.horas_trabajadas,
                tarifa_hora=operation.tarifa_hora,
                valor=valor,
                created_by=usuario,
                updated_by=usuario,
            )
            creados.append(br)
    return creados


def total_facturado_operacion(operation):
    return (
        operation.billing_records.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )


def total_abonado_operacion(operation):
    return (
        operation.client_payments.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )


def saldo_operacion(operation):
    return total_facturado_operacion(operation) - total_abonado_operacion(operation)
```

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.facturacion.tests -v 2`
Expected: PASS (7 tests en apps.facturacion).

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "feat(facturacion): generacion de billing por horas y saldo por operacion"
```

---

### Task 3: CSV de facturación por operación

**Files:**
- Modify: `apps/facturacion/services.py` (añadir generar_csv_facturacion)
- Create: `apps/facturacion/tests/test_csv.py`

**Interfaces:**
- Consumes: `Operation`, `BillingRecord` (Task 1).
- Produces:
  - `def generar_csv_facturacion(operation) -> str` — devuelve el contenido CSV como string con separador `;`, BOM UTF-8, con:
    - Cabecera: `Fecha;Operación;Mula;Turno;Hora inicio;Hora final;Horas trabajadas`
    - Una fila por billing de la operación (turnos realizados; sin chofer).
    - Bloque de resumen: línea en blanco, cabecera `Mula;Horas totales` y una fila por mula con el total de horas facturadas.
    - Fecha en formato `dd/mm/yyyy`; horas con punto decimal (ej. `11.00`, `8.00`).

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/facturacion/tests/test_csv.py`:

```python
import csv
import io
from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.facturacion.services import generar_billing_operacion, generar_csv_facturacion
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift


class CsvFacturacionTests(TestCase):
    def setUp(self):
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.v1 = Vehicle.objects.create(placa="ABC123")
        self.v2 = Vehicle.objects.create(placa="DEF456")
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

    def _shift(self, vehicle, dia, inicio=6, fin=17):
        return Shift.objects.create(
            operation=self.op,
            vehicle=vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, dia, inicio, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, dia, fin, 0)),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )

    def test_csv_contiene_filas_y_no_chofer(self):
        self._shift(self.v1, 10)
        self._shift(self.v2, 11)
        generar_billing_operacion(self.op)
        csv_texto = generar_csv_facturacion(self.op)
        self.assertNotIn("Juan", csv_texto)
        self.assertIn("ABC123", csv_texto)
        self.assertIn("DEF456", csv_texto)
        self.assertIn("11.00", csv_texto)
        self.assertIn("11/08/2026", csv_texto)

    def test_csv_incluye_resumen_por_mula(self):
        self._shift(self.v1, 10)
        self._shift(self.v1, 11)
        generar_billing_operacion(self.op)
        csv_texto = generar_csv_facturacion(self.op)
        self.assertIn("Mula;Horas totales", csv_texto)
        self.assertIn("ABC123;22.00", csv_texto)

    def test_csv_separador_punto_y_coma(self):
        self._shift(self.v1, 10)
        generar_billing_operacion(self.op)
        csv_texto = generar_csv_facturacion(self.op)
        reader = list(csv.reader(io.StringIO(csv_texto), delimiter=";"))
        self.assertEqual(reader[0][0], "Fecha")
        self.assertEqual(len(reader[0]), 7)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.facturacion.tests.test_csv -v 2`
Expected: FAIL — `ImportError: cannot import name 'generar_csv_facturacion'`.

- [ ] **Step 3: Implementación mínima**

Añadir a `apps/facturacion/services.py`:

```python
import csv
import io


def generar_csv_facturacion(operation):
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")

    writer.writerow(
        [
            "Fecha",
            "Operación",
            "Mula",
            "Turno",
            "Hora inicio",
            "Hora final",
            "Horas trabajadas",
        ]
    )
    for br in operation.billing_records.select_related("shift__vehicle").order_by(
        "fecha", "shift__fecha_inicio"
    ):
        if br.shift_id is None:
            continue
        shift = br.shift
        writer.writerow(
            [
                br.fecha.strftime("%d/%m/%Y"),
                operation.codigo,
                shift.vehicle.placa,
                shift.get_tipo_display(),
                shift.fecha_inicio.strftime("%H:%M"),
                shift.fecha_fin.strftime("%H:%M"),
                f"{br.horas:.2f}",
            ]
        )

    writer.writerow([])
    writer.writerow(["Mula", "Horas totales"])
    totales = {}
    for br in operation.billing_records.select_related("shift__vehicle").filter(
        shift__isnull=False
    ):
        placa = br.shift.vehicle.placa
        totales[placa] = totales.get(placa, Decimal(0)) + br.horas
    for placa in sorted(totales):
        writer.writerow([placa, f"{totales[placa]:.2f}"])

    return buffer.getvalue()
```

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.facturacion.tests.test_csv -v 2`
Expected: PASS (3 tests). Nota: los totales se suman como Decimal; `f"{Decimal('22.00'):.2f}"` → "22.00".

- [ ] **Step 5: Suite completa**

Run: `python manage.py test -v 2`
Expected: PASS (~101 tests).

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "feat(facturacion): CSV de facturacion por operacion sin chofer"
```

---

### Task 4: Vistas funcionales de facturación

**Files:**
- Create: `apps/facturacion/urls.py`
- Create: `apps/facturacion/views.py`
- Create: `apps/facturacion/forms.py`
- Create: `templates/facturacion/facturacion_detail.html`
- Create: `apps/facturacion/tests/test_views.py`
- Modify: `config/urls.py` (incluir `apps.facturacion.urls` bajo prefijo `facturacion/`)
- Modify: `static/css/app.css` (estilos `.tag-ok/.tag-warn/.tag-danger` si no existen — en Plan 3 solo se añadieron `.tag` y el revisor notó `.tag-ok` etc. sin usar; añadirlos ahora con uso real)

**Interfaces:**
- Consumes: `generar_billing_operacion`, `saldo_operacion`, `total_facturado_operacion`, `total_abonado_operacion`, `generar_csv_facturacion`, `ClientPayment`, `Operation`.
- Produces:
  - URL namespace `facturacion`:
    - `facturacion:detalle` (`<int:pk>/`) → resumen de facturación de una operación (total facturado, abonos, saldo), tabla de billing, formulario de abono.
    - `facturacion:generar` (`<int:pk>/generar/`) → POST → generar_billing_operacion → redirect detalle.
    - `facturacion:abono` (`<int:pk>/abonos/nuevo/`) → POST → crear ClientPayment → redirect detalle.
    - `facturacion:csv` (`<int:pk>/csv/`) → GET → StreamingHttpResponse/HttpResponse con el CSV (content-type text/csv, nombre `facturacion_<codigo>.csv`).
  - Todas `@login_required`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/facturacion/tests/test_views.py`:

```python
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift


class FacturacionViewsTests(TestCase):
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

    def test_detalle_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse("facturacion:detalle", args=[self.op.pk]))
        self.assertEqual(response.status_code, 302)

    def test_generar_billing_via_post(self):
        response = self.client.post(reverse("facturacion:generar", args=[self.op.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BillingRecord.objects.count(), 1)
        self.assertEqual(BillingRecord.objects.first().valor, 385000)

    def test_registrar_abono_via_post(self):
        response = self.client.post(
            reverse("facturacion:abono", args=[self.op.pk]),
            {"valor": 200000, "fecha": "15/08/2026"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ClientPayment.objects.count(), 1)

    def test_csv_endpoint(self):
        response = self.client.post(reverse("facturacion:generar", args=[self.op.pk]))
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse("facturacion:csv", args=[self.op.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("ABC123", response.content.decode("utf-8-sig"))
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.facturacion.tests.test_views -v 2`
Expected: FAIL — `NoReverseMatch` para `facturacion:detalle`.

- [ ] **Step 3: Implementar vistas y URLs**

Crear `apps/facturacion/urls.py`:

```python
from django.urls import path

from apps.facturacion import views

app_name = "facturacion"

urlpatterns = [
    path("<int:pk>/", views.facturacion_detail, name="detalle"),
    path("<int:pk>/generar/", views.generar_billing, name="generar"),
    path("<int:pk>/abonos/nuevo/", views.abono_nuevo, name="abono"),
    path("<int:pk>/csv/", views.csv_facturacion, name="csv"),
]
```

En `config/urls.py`, añadir:

```python
path("facturacion/", include("apps.facturacion.urls")),
```

Crear `apps/facturacion/forms.py`:

```python
from django import forms

from apps.facturacion.models import ClientPayment


class ClientPaymentForm(forms.ModelForm):
    class Meta:
        model = ClientPayment
        fields = ["valor", "fecha", "observaciones"]
```

Crear `apps/facturacion/views.py`:

```python
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.facturacion.forms import ClientPaymentForm
from apps.facturacion.models import ClientPayment
from apps.facturacion.services import (
    generar_billing_operacion,
    generar_csv_facturacion,
    saldo_operacion,
    total_abonado_operacion,
    total_facturado_operacion,
)
from apps.operaciones.models import Operation


@login_required
def facturacion_detail(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    context = {
        "operation": operation,
        "facturado": total_facturado_operacion(operation),
        "abonado": total_abonado_operacion(operation),
        "saldo": saldo_operacion(operation),
        "abono_form": ClientPaymentForm(),
    }
    return render(request, "facturacion/facturacion_detail.html", context)


@login_required
def generar_billing(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    if request.method == "POST":
        generar_billing_operacion(operation, usuario=request.user)
    return redirect("facturacion:detalle", pk=operation.pk)


@login_required
def abono_nuevo(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    form = ClientPaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        abono = form.save(commit=False)
        abono.operation = operation
        abono.created_by = request.user
        abono.updated_by = request.user
        abono.save()
    return redirect("facturacion:detalle", pk=operation.pk)


@login_required
def csv_facturacion(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    content = generar_csv_facturacion(operation)
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="facturacion_{operation.codigo}.csv"'
    )
    return response
```

- [ ] **Step 4: Crear plantilla**

Crear `templates/facturacion/facturacion_detail.html`:

```html
{% extends "base.html" %}
{% block title %}Facturación {{ operation.codigo }}{% endblock %}
{% block content %}
<p class="eyebrow">Facturación</p>
<h1>{{ operation.buque }}</h1>
<p><strong>{{ operation.codigo }}</strong> · Tarifa: ${{ operation.tarifa_hora }}/h</p>

<form method="post" action="{% url 'facturacion:generar' operation.pk %}">
  {% csrf_token %}
  <button type="submit" class="btn btn-primary">Generar facturación desde turnos</button>
</form>
<a class="btn" href="{% url 'facturacion:csv' operation.pk %}">Descargar CSV</a>

<h2>Totales</h2>
<table class="table">
  <tbody>
    <tr><th>Facturado</th><td>${{ facturado }}</td></tr>
    <tr><th>Abonado</th><td>${{ abonado }}</td></tr>
    <tr><th>Saldo</th><td><strong>${{ saldo }}</strong></td></tr>
  </tbody>
</table>

<h2>Registros de facturación</h2>
<table class="table">
  <thead><tr><th>Fecha</th><th>Mula</th><th>Turno</th><th>Horas</th><th>Valor</th><th>Estado</th></tr></thead>
  <tbody>
  {% for br in operation.billing_records.all %}
    <tr>
      <td>{{ br.fecha|date:"d/m/Y" }}</td>
      <td>{{ br.shift.vehicle.placa|default:"—" }}</td>
      <td>{{ br.shift.get_tipo_display|default:"—" }}</td>
      <td>{{ br.horas }}</td>
      <td>${{ br.valor }}</td>
      <td><span class="tag">{{ br.get_estado_display }}</span></td>
    </tr>
  {% empty %}
    <tr><td colspan="6">Sin registros de facturación. Genere la facturación desde los turnos realizados.</td></tr>
  {% endfor %}
  </tbody>
</table>

<h2>Abonos del generador de carga</h2>
<form method="post" action="{% url 'facturacion:abono' operation.pk %}" class="card">
  {% csrf_token %}
  {{ abono_form.as_p }}
  <button type="submit" class="btn btn-primary">Registrar abono</button>
</form>
<table class="table">
  <thead><tr><th>Fecha</th><th>Valor</th><th>Observaciones</th></tr></thead>
  <tbody>
  {% for abono in operation.client_payments.all %}
    <tr>
      <td>{{ abono.fecha|date:"d/m/Y" }}</td>
      <td>${{ abono.valor }}</td>
      <td>{{ abono.observaciones }}</td>
    </tr>
  {% empty %}
    <tr><td colspan="3">Sin abonos registrados.</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
```

Añadir a `static/css/app.css` (si no existen ya):

```css
.btn { border: 1px solid var(--line); }
```

El botón "Descargar CSV" usa la clase `.btn` sin variante primaria — verificar que `.btn` base existe y tiene borde/fondo coherente; si `.btn` no tiene variante neutra, usar un estilo inline coherente con la paleta (fondo `--surface`, borde `--line`).

- [ ] **Step 5: Verificar que pasa**

Run: `python manage.py test apps.facturacion.tests.test_views -v 2`
Expected: PASS (4 tests). Ajustar el formato de fecha del form si `%d/%m/%Y` no parsea.

- [ ] **Step 6: Suite completa**

Run: `python manage.py test -v 2`
Expected: PASS (tests previos + nuevos = ~105). `python manage.py check` limpio.

- [ ] **Step 7: Commit local**

```bash
git add -A
git commit -m "feat(facturacion): vistas de facturacion, abonos y descarga CSV"
```

---

## Self-Review del Plan

**Cobertura del spec (Plan 4):**
- `billing_records` con operation/shift/valor/estado: Task 1. ✔
- `client_payments`: Task 1. ✔
- Valor facturado = horas × tarifa (§23), independiente del pago al conductor: Task 2. ✔
- Un turno → un billing (unique): Task 1/2. ✔
- Saldo = facturado − abonado (§25): Task 2. ✔
- CSV por operación sin chofer, con resumen por mula (§24): Task 3. ✔
- Estados de billing (pendiente/incluido/facturado/cobrado): Task 1. ✔
- Vistas funcionales + descarga CSV: Task 4. ✔
- Separación estricta (§38): facturacion no toca payroll ni payments. ✔

**Fuera de este plan:** dashboards/Gantt (Plan 5), estados de billing avanzados (incluido/facturado/cobrado gestionados desde la UI — en MVP se registran como pendiente y el CSV los usa), evolución de facturación con Chart.js (Plan 5), granularidad de permisos por grupo (decisión del humano pendiente).

**Placeholders:** ninguno; cada paso contiene código o comandos reales.

**Consistencia de tipos:** `generar_billing_operacion`/`saldo_operacion`/`total_facturado_operacion`/`total_abonado_operacion`/`generar_csv_facturacion` definidos en servicios y consumidos por vistas/tests con las mismas firmas. `BillingRecord.shift` unique garantiza un billing por turno a nivel BD. `Shift.billing_record` related_name 1:1 se usa en el filtro `billing_record__isnull=True` para idempotencia.
