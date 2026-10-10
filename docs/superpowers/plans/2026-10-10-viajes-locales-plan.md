# Módulo Viajes Locales — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar el módulo de viajes locales (fletes ciudad a ciudad) integrado a nómina, facturación y gastos, con UI híbrida en el menú de Operaciones.

**Architecture:** Modelo `Viaje` nuevo en `apps/operaciones`, separado de `Operation`. `PayrollItem`, `OperationExpense` y `BillingRecord` se extienden con FK `viaje` nullable (constraint: exactamente uno de operation/shift o viaje). Servicios con `transaction.atomic()` y `ValidationError` en español. Vistas FBV con `@login_required` y `role_required`. Templates con `base.html` y clases CSS existentes.

**Tech Stack:** Django 5.2, Python 3.13, SQLite/Supabase, django-simple-history, Material Symbols.

## Global Constraints

- IDs únicos de usuario: `admin`/`admin123` (grupo Admin), `secretaria`/`secretaria123` (Secretaria).
- Moneda: `DecimalField(max_digits=14, decimal_places=0)` — COP enteros.
- Fechas: `USE_TZ=True`, `TIME_ZONE="America/Bogota"` — usar `timezone.localdate()`, `timezone.make_aware()`.
- Nombres de URL: `app_name = "operaciones"`, `reverse("operaciones:viaje_lista")` etc.
- Decoradores: `@login_required` para todo; `@role_required("Admin", "Secretaria")` para acciones de estado.
- Mensajes flash: `messages.success` en POST-redirect; `form.add_error` o `error.html` (409) para errores de dominio.
- Auditoría: `created_by=request.user` / `updated_by=request.user` explícitos.
- Tests: `django.test.TestCase`, `setUp` con `Model.objects.create`, fechas congeladas `date(2026, 8, 10)`.
- NO modificar `seed_demo.py` hasta Task 10.

---

### Task 1: Modelo `Viaje` + migración

**Files:**
- Create: `apps/operaciones/tests/test_viaje_model.py`
- Modify: `apps/operaciones/models.py` (agregar clase `Viaje` después de `OperationExpense`)
- Test runner: `python manage.py test apps.operaciones.tests.test_viaje_model -v 2`

**Interfaces:**
- Produces: `Viaje` con constantes `PENDIENTE/EN_VIAJE/FINALIZADO/CANCELADO`, campos listados en spec, método `clean()`.

- [ ] **Step 1: Escribir test fallido**

```python
# apps/operaciones/tests/test_viaje_model.py
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Viaje


class ViajeModelTests(TestCase):
    def setUp(self):
        self.cliente = CargoGenerator.objects.create(nombre="Distribuidora Norte", nit="900111222-3")
        self.vehicle = Vehicle.objects.create(placa="XYZ789", marca="Volvo", modelo="FH", anio=2022)
        self.driver = Driver.objects.create(nombre="Pedro Gómez", documento="987654321")
        self.ahora = timezone.make_aware(datetime(2026, 8, 10, 6, 0))

    def _viaje(self, **kwargs):
        defaults = dict(
            cliente=self.cliente,
            vehicle=self.vehicle,
            driver=self.driver,
            origen="Barranquilla",
            destino="Cartagena",
            fecha_ida=self.ahora,
            fecha_vuelta=self.ahora + timedelta(hours=8),
            valor_cobrado=Decimal("800000"),
            valor_conductor=Decimal("400000"),
        )
        defaults.update(kwargs)
        return Viaje(**defaults)

    def test_estado_inicial_es_pendiente(self):
        v = self._viaje()
        self.assertEqual(v.estado, Viaje.PENDIENTE)

    def test_clean_acepta_fechas_validas(self):
        v = self._viaje()
        v.full_clean()  # no debe lanzar

    def test_clean_rechaza_fecha_vuelta_menor_o_igual(self):
        v = self._viaje(fecha_vuelta=self.ahora)
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_clean_rechaza_valor_cobrado_cero(self):
        v = self._viaje(valor_cobrado=Decimal("0"))
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_clean_rechaza_valor_conductor_negativo(self):
        v = self._viaje(valor_conductor=Decimal("-1000"))
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_codigo_auto_en_save(self):
        v = self._viaje()
        v.save()
        self.assertTrue(v.codigo.startswith("VJ-"))
        self.assertIn(str(v.fecha_ida.year), v.codigo)

    def test_str_muestra_ruta(self):
        v = self._viaje()
        self.assertIn("Barranquilla", str(v))
        self.assertIn("Cartagena", str(v))
```

- [ ] **Step 2: Ejecutar test — debe fallar por ImportError**

Run: `.\.venv\Scripts\python.exe manage.py test apps.operaciones.tests.test_viaje_model -v 2`
Expected: FAIL / ERROR `cannot import name 'Viaje'`

- [ ] **Step 3: Implementar modelo mínimo**

En `apps/operaciones/models.py`, agregar después de `OperationExpense`:

```python
def generar_numero_viaje(anio):
    prefix = f"VJ-{anio}-"
    ultimo = Viaje.objects.filter(codigo__startswith=prefix).order_by("-codigo").first()
    if ultimo is None:
        return f"{prefix}001"
    secuencia = int(ultimo.codigo.rsplit("-", 1)[1]) + 1
    return f"{prefix}{secuencia:03d}"


class Viaje(AuditMixin):
    PENDIENTE = "pendiente"
    EN_VIAJE = "en_viaje"
    FINALIZADO = "finalizado"
    CANCELADO = "cancelado"

    ESTADOS = [
        (PENDIENTE, "Pendiente"),
        (EN_VIAJE, "En viaje"),
        (FINALIZADO, "Finalizado"),
        (CANCELADO, "Cancelado"),
    ]

    codigo = models.CharField(max_length=20, unique=True, blank=True)
    cliente = models.ForeignKey(
        CargoGenerator, on_delete=models.PROTECT, related_name="viajes"
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.PROTECT, related_name="viajes"
    )
    driver = models.ForeignKey(
        Driver, on_delete=models.PROTECT, related_name="viajes"
    )
    origen = models.CharField(max_length=120)
    destino = models.CharField(max_length=120)
    fecha_ida = models.DateTimeField()
    fecha_vuelta = models.DateTimeField()
    valor_cobrado = models.DecimalField(max_digits=14, decimal_places=0)
    valor_conductor = models.DecimalField(max_digits=14, decimal_places=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=PENDIENTE)
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Viaje local"
        verbose_name_plural = "Viajes locales"
        ordering = ["-fecha_ida"]

    def __str__(self):
        return f"{self.codigo} - {self.origen} → {self.destino}"

    def clean(self):
        super().clean()
        if self.fecha_ida and self.fecha_vuelta and self.fecha_vuelta <= self.fecha_ida:
            raise ValidationError({"fecha_vuelta": "La fecha de vuelta debe ser posterior a la de ida."})
        if self.valor_cobrado is not None and self.valor_cobrado <= 0:
            raise ValidationError({"valor_cobrado": "El valor cobrado debe ser mayor a cero."})
        if self.valor_conductor is not None and self.valor_conductor < 0:
            raise ValidationError({"valor_conductor": "El valor del conductor no puede ser negativo."})

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = generar_numero_viaje(self.fecha_ida.year if self.fecha_ida else timezone.localdate().year)
        super().save(*args, **kwargs)
```

- [ ] **Step 4: Crear migración y aplicar**

Run: `.\.venv\Scripts\python.exe manage.py makemigrations operaciones`
Run: `.\.venv\Scripts\python.exe manage.py migrate`
Expected: migración creada y aplicada sin errores.

- [ ] **Step 5: Ejecutar test — debe pasar**

Run: `.\.venv\Scripts\python.exe manage.py test apps.operaciones.tests.test_viaje_model -v 2`
Expected: PASS (todos los tests).

- [ ] **Step 6: Commit**

```bash
git add apps/operaciones/models.py apps/operaciones/tests/test_viaje_model.py apps/operaciones/migrations/
git commit -m "feat(viajes): modelo Viaje con validaciones y código auto"
```

---

### Task 2: `PayrollItem` acepta viaje (nullable shift + FK viaje)

**Files:**
- Create: `apps/nomina/tests/test_payroll_item_viaje.py`
- Modify: `apps/nomina/models.py` (`PayrollItem`)
- Modify: `apps/nomina/services.py` (`crear_liquidacion`, `resumen_liquidacion`, `viajes_pendientes_pago`)
- Test runner: `python manage.py test apps.nomina.tests.test_payroll_item_viaje apps.nomina.tests.test_services -v 2`

**Interfaces:**
- Consumes: `Viaje` (Task 1)
- Produces: `PayrollItem(shift=None, viaje=viaje, valor=...)`; `viajes_pendientes_pago(desde, hasta)`; `crear_liquidacion` incluye viajes.

- [ ] **Step 1: Escribir test fallido**

```python
# apps/nomina/tests/test_payroll_item_viaje.py
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.nomina.models import Payroll, PayrollItem
from apps.nomina.services import crear_liquidacion, resumen_liquidacion, viajes_pendientes_pago
from apps.operaciones.models import Viaje


class PayrollItemViajeTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username="admin", password="x")
        self.cliente = CargoGenerator.objects.create(nombre="Cliente SA", nit="1")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Carlos", documento="1")
        self.driver2 = Driver.objects.create(nombre="Ana", documento="2")
        self.ahora = timezone.make_aware(datetime(2026, 8, 10, 6, 0))

    def _viaje(self, driver=None, fecha_ida=None, **kwargs):
        defaults = dict(
            cliente=self.cliente,
            vehicle=self.vehicle,
            driver=driver or self.driver,
            origen="Barranquilla",
            destino="Cartagena",
            fecha_ida=fecha_ida or self.ahora,
            fecha_vuelta=(fecha_ida or self.ahora) + timedelta(hours=8),
            valor_cobrado=Decimal("800000"),
            valor_conductor=Decimal("400000"),
            estado=Viaje.FINALIZADO,
        )
        defaults.update(kwargs)
        v = Viaje.objects.create(**defaults)
        return v

    def test_viajes_pendientes_pago_encuentra_finalizados_sin_payroll(self):
        v = self._viaje()
        qs = viajes_pendientes_pago(date(2026, 8, 1), date(2026, 8, 31))
        self.assertIn(v, qs)

    def test_viajes_pendientes_pago_excluye_liquidados(self):
        v = self._viaje()
        payroll = Payroll.objects.create(
            numero="NOM-2026-001", periodo_inicio=date(2026, 8, 1), periodo_fin=date(2026, 8, 31)
        )
        PayrollItem.objects.create(payroll=payroll, viaje=v, valor=Decimal("400000"))
        qs = viajes_pendientes_pago(date(2026, 8, 1), date(2026, 8, 31))
        self.assertNotIn(v, qs)

    def test_crear_liquidacion_incluye_viaje(self):
        self._viaje()
        payroll = crear_liquidacion(date(2026, 8, 1), date(2026, 8, 31), usuario=self.user)
        item = payroll.items.get()
        self.assertIsNotNone(item.viaje)
        self.assertIsNone(item.shift)
        self.assertEqual(item.valor, Decimal("400000"))
        self.assertEqual(payroll.total, Decimal("400000"))

    def test_resumen_liquidacion_agrupa_por_conductor_con_viajes(self):
        self._viaje()
        payroll = crear_liquidacion(date(2026, 8, 1), date(2026, 8, 31))
        resumen = resumen_liquidacion(payroll)
        self.assertEqual(len(resumen), 1)
        self.assertEqual(resumen[0]["driver"], self.driver)
        self.assertEqual(resumen[0]["total"], Decimal("400000"))
        self.assertEqual(resumen[0]["horas"], Decimal("0"))

    def test_crear_liquidacion_sin_nada_lanza_error(self):
        with self.assertRaises(ValidationError):
            crear_liquidacion(date(2026, 8, 1), date(2026, 8, 31))
```

- [ ] **Step 2: Ejecutar test — debe fallar por ImportError (viajes_pendientes_pago no existe)**

Run: `.\.venv\Scripts\python.exe manage.py test apps.nomina.tests.test_payroll_item_viaje -v 2`
Expected: FAIL / ERROR `cannot import name 'viajes_pendientes_pago'`

- [ ] **Step 3: Modificar modelo `PayrollItem`**

En `apps/nomina/models.py`, cambiar `shift` y agregar `viaje`:

```python
class PayrollItem(AuditMixin):
    payroll = models.ForeignKey(
        Payroll, on_delete=models.CASCADE, related_name="items"
    )
    shift = models.ForeignKey(
        Shift, on_delete=models.PROTECT, related_name="payroll_items",
        null=True, blank=True
    )
    viaje = models.ForeignKey(
        "operaciones.Viaje", on_delete=models.PROTECT, related_name="payroll_items",
        null=True, blank=True
    )
    valor = models.DecimalField(max_digits=14, decimal_places=0)
    pagado = models.DecimalField(max_digits=14, decimal_places=0, default=0)

    class Meta:
        verbose_name = "Item de liquidación"
        verbose_name_plural = "Items de liquidación"

    def __str__(self):
        if self.viaje_id:
            return f"{self.payroll.numero} - {self.viaje}"
        return f"{self.payroll.numero} - {self.shift}"

    def clean(self):
        super().clean()
        if bool(self.shift_id) == bool(self.viaje_id):
            raise ValidationError("El item debe tener exactamente un turno o un viaje.")
```

- [ ] **Step 4: Agregar `viajes_pendientes_pago` en services**

En `apps/nomina/services.py`, después de `turnos_pendientes_pago`:

```python
def viajes_pendientes_pago(desde, hasta):
    desde_dt = timezone.make_aware(datetime.combine(desde, time.min))
    hasta_dt = timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min))
    return (
        Viaje.objects.filter(
            estado=Viaje.FINALIZADO,
            fecha_vuelta__gte=desde_dt,
            fecha_vuelta__lt=hasta_dt,
            payroll_items__isnull=True,
        )
        .select_related("driver", "vehicle", "cliente")
        .order_by("fecha_vuelta")
    )
```

(Importar `Viaje` al inicio del archivo.)

- [ ] **Step 5: Modificar `crear_liquidacion`**

Reemplazar el bloque de turnos por:

```python
def crear_liquidacion(desde, hasta, usuario=None):
    turnos = list(turnos_pendientes_pago(desde, hasta))
    viajes = list(viajes_pendientes_pago(desde, hasta))
    if not turnos and not viajes:
        raise ValidationError("No hay turnos ni viajes pendientes de pago en el periodo seleccionado.")
    if Payroll.objects.filter(periodo_inicio__lte=hasta, periodo_fin__gte=desde).exists():
        raise ValidationError("Ya existe una liquidación que solapa con este periodo.")
    with transaction.atomic():
        payroll = Payroll.objects.create(
            numero=generar_numero_liquidacion(desde.year),
            periodo_inicio=desde,
            periodo_fin=hasta,
            estado=Payroll.LIQUIDADO,
            created_by=usuario,
            updated_by=usuario,
        )
        total = Decimal("0")
        for shift in turnos:
            PayrollItem.objects.create(
                payroll=payroll, shift=shift, valor=shift.valor_pagado,
                created_by=usuario, updated_by=usuario,
            )
            total += shift.valor_pagado
        for viaje in viajes:
            PayrollItem.objects.create(
                payroll=payroll, viaje=viaje, valor=viaje.valor_conductor,
                created_by=usuario, updated_by=usuario,
            )
            total += viaje.valor_conductor
        payroll.total = total
        payroll.save(update_fields=["total"])
    conductores = {i.shift.driver if i.shift_id else i.viaje.driver for i in payroll.items.all()}
    for driver in conductores:
        recalcular_fifo(driver)
    return payroll
```

- [ ] **Step 6: Modificar `resumen_liquidacion`**

Cambiar la agrupación para soportar viajes:

```python
def resumen_liquidacion(payroll):
    por_conductor = {}
    for item in payroll.items.select_related("shift__driver", "viaje__driver"):
        driver = item.shift.driver if item.shift_id else item.viaje.driver
        if driver.pk not in por_conductor:
            por_conductor[driver.pk] = {
                "driver": driver,
                "turnos": 0,
                "horas": Decimal("0"),
                "total": Decimal("0"),
                "cubierto": Decimal("0"),
            }
        fila = por_conductor[driver.pk]
        if item.shift_id:
            fila["turnos"] += 1
            fila["horas"] += item.shift.horas_trabajadas
        fila["total"] += item.valor
        fila["cubierto"] += item.pagado
    resumen = []
    for fila in por_conductor.values():
        fila["pendiente"] = fila["total"] - fila["cubierto"]
        fila["estado"] = _estado_periodo(fila["total"], fila["cubierto"])
        resumen.append(fila)
    resumen.sort(key=lambda f: f["driver"].nombre)
    return resumen
```

- [ ] **Step 7: Crear migración y aplicar**

Run: `.\.venv\Scripts\python.exe manage.py makemigrations nomina`
Run: `.\.venv\Scripts\python.exe manage.py migrate`
Expected: OK.

- [ ] **Step 8: Ejecutar tests nuevos + existentes de nómina**

Run: `.\.venv\Scripts\python.exe manage.py test apps.nomina -v 1`
Expected: PASS (los nuevos y los existentes).

- [ ] **Step 9: Commit**

```bash
git add apps/nomina/models.py apps/nomina/services.py apps/nomina/tests/test_payroll_item_viaje.py apps/nomina/migrations/
git commit -m "feat(viajes): PayrollItem soporta viajes; liquidación los incluye"
```

---

### Task 3: `OperationExpense` acepta viaje

**Files:**
- Create: `apps/operaciones/tests/test_expense_viaje.py`
- Modify: `apps/operaciones/models.py` (`OperationExpense`)
- Modify: `apps/operaciones/forms.py` (`OperationExpenseForm` acepta `viaje=`)
- Test runner: `python manage.py test apps.operaciones.tests.test_expense_viaje -v 2`

**Interfaces:**
- Consumes: `Viaje` (Task 1)
- Produces: `OperationExpense(operation=None, viaje=viaje, vehicle=..., ...)`; `OperationExpenseForm(..., viaje=viaje)`.

- [ ] **Step 1: Escribir test fallido**

```python
# apps/operaciones/tests/test_expense_viaje.py
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import OperationExpense, Viaje


class ExpenseViajeTests(TestCase):
    def setUp(self):
        self.cliente = CargoGenerator.objects.create(nombre="Cliente", nit="1")
        self.vehicle = Vehicle.objects.create(placa="ABC123")
        self.driver = Driver.objects.create(nombre="Juan", documento="1")
        self.ahora = timezone.make_aware(datetime(2026, 8, 10, 6, 0))
        self.viaje = Viaje.objects.create(
            cliente=self.cliente, vehicle=self.vehicle, driver=self.driver,
            origen="Barranquilla", destino="Cartagena",
            fecha_ida=self.ahora, fecha_vuelta=self.ahora + timedelta(hours=8),
            valor_cobrado=Decimal("800000"), valor_conductor=Decimal("400000"),
        )

    def test_crear_gasto_vía_viaje(self):
        gasto = OperationExpense.objects.create(
            viaje=self.viaje, vehicle=self.vehicle,
            categoria=OperationExpense.COMBUSTIBLE,
            fecha=timezone.localdate(), valor=Decimal("450000"), galones=Decimal("120"),
        )
        self.assertEqual(gasto.viaje, self.viaje)
        self.assertIsNone(gasto.operation)

    def test_gasto_sin_viaje_ni_operation_es_invalido(self):
        gasto = OperationExpense(
            vehicle=self.vehicle, categoria=OperationExpense.PEAJE,
            fecha=timezone.localdate(), valor=Decimal("35000"),
        )
        with self.assertRaises(ValidationError):
            gasto.full_clean()

    def test_gasto_con_operation_y_viaje_es_invalido(self):
        from apps.catalogos.models import Port
        from apps.operaciones.models import Operation
        puerto = Port.objects.create(nombre="Puerto")
        op = Operation.objects.create(
            codigo="OP-1", buque="B", generador_de_carga=self.cliente, puerto=puerto,
            fecha_inicio=timezone.localdate(), tarifa_hora=Decimal("35000"),
            valor_turno_dia=Decimal("180000"), valor_turno_noche=Decimal("180000"),
        )
        gasto = OperationExpense(
            operation=op, viaje=self.viaje, vehicle=self.vehicle,
            categoria=OperationExpense.PEAJE, fecha=timezone.localdate(), valor=Decimal("1"),
        )
        with self.assertRaises(ValidationError):
            gasto.full_clean()
```

- [ ] **Step 2: Ejecutar test — debe fallar (viaje no existe en OperationExpense)**

Run: `.\.venv\Scripts\python.exe manage.py test apps.operaciones.tests.test_expense_viaje -v 2`
Expected: FAIL.

- [ ] **Step 3: Modificar `OperationExpense`**

En `apps/operaciones/models.py`, en `OperationExpense`:
- Cambiar `operation = models.ForeignKey(...)` a `null=True, blank=True`.
- Agregar:

```python
    viaje = models.ForeignKey(
        Viaje, on_delete=models.PROTECT, related_name="expenses",
        null=True, blank=True
    )
```

- Agregar método `clean`:

```python
    def clean(self):
        super().clean()
        if bool(self.operation_id) == bool(self.viaje_id):
            raise ValidationError("El gasto debe pertenecer exactamente a una operación o a un viaje.")
```

- [ ] **Step 4: Modificar `OperationExpenseForm`**

En `apps/operaciones/forms.py`:

```python
class OperationExpenseForm(forms.ModelForm):
    class Meta:
        model = OperationExpense
        fields = ["categoria", "vehicle", "proveedor", "fecha", "valor",
                  "galones", "descripcion", "numero_factura", "observaciones"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "descripcion": forms.Textarea(attrs={"rows": 2}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, operation=None, viaje=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].input_formats = ["%Y-%m-%d"]
        if operation is not None:
            self.fields["vehicle"].queryset = Vehicle.objects.filter(
                operaciones__operation=operation, operaciones__activa=True
            )
        elif viaje is not None:
            self.fields["vehicle"].queryset = Vehicle.objects.filter(pk=viaje.vehicle_id)
            self.fields["vehicle"].initial = viaje.vehicle
        self.fields["proveedor"].queryset = Proveedor.objects.filter(activo=True)
        self.fields["proveedor"].required = False
```

- [ ] **Step 5: Crear migración y aplicar**

Run: `.\.venv\Scripts\python.exe manage.py makemigrations operaciones`
Run: `.\.venv\Scripts\python.exe manage.py migrate`

- [ ] **Step 6: Ejecutar test + tests de operaciones existentes**

Run: `.\.venv\Scripts\python.exe manage.py test apps.operaciones -v 1`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/operaciones/models.py apps/operaciones/forms.py apps/operaciones/tests/test_expense_viaje.py apps/operaciones/migrations/
git commit -m "feat(viajes): OperationExpense soporta viajes"
```

---

### Task 4: `BillingRecord` acepta viaje + servicio `finalizar_viaje` crea facturación

**Files:**
- Create: `apps/operaciones/tests/test_viaje_services.py`
- Modify: `apps/facturacion/models.py` (`BillingRecord`)
- Modify: `apps/operaciones/services.py` (agregar services de viaje)
- Test runner: `python manage.py test apps.operaciones.tests.test_viaje_services apps.facturacion -v 1`

**Interfaces:**
- Consumes: `Viaje` (Task 1)
- Produces: `crear_viaje`, `iniciar_viaje`, `finalizar_viaje`, `cancelar_viaje`; `BillingRecord(viaje=viaje, ...)`.

- [ ] **Step 1: Escribir test fallido**

```python
# apps/operaciones/tests/test_viaje_services.py
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import CargoGenerator
from apps.conductores.models import Driver
from apps.facturacion.models import BillingRecord
from apps.flota.models import Vehicle
from apps.operaciones.models import Viaje
from apps.operaciones.services import cancelar_viaje, crear_viaje, finalizar_viaje, iniciar_viaje


class ViajeServicesTests(TestCase):
    def setUp(self):
        self.cliente = CargoGenerator.objects.create(nombre="Cliente", nit="1")
        self.vehicle = Vehicle.objects.create(placa="ABC123", estado=Vehicle.DISPONIBLE)
        self.driver = Driver.objects.create(nombre="Juan", documento="1")
        self.ahora = timezone.make_aware(datetime(2026, 8, 10, 6, 0))

    def _crear(self, **kwargs):
        defaults = dict(
            cliente=self.cliente, vehicle=self.vehicle, driver=self.driver,
            origen="Barranquilla", destino="Cartagena",
            fecha_ida=self.ahora, fecha_vuelta=self.ahora + timedelta(hours=8),
            valor_cobrado=Decimal("800000"), valor_conductor=Decimal("400000"),
        )
        defaults.update(kwargs)
        return crear_viaje(**defaults)

    def test_crear_viaje_genera_codigo_y_estado_pendiente(self):
        v = self._crear()
        self.assertTrue(v.codigo.startswith("VJ-"))
        self.assertEqual(v.estado, Viaje.PENDIENTE)

    def test_crear_viaje_rechaza_solape_vehiculo(self):
        self._crear()
        with self.assertRaises(ValidationError):
            self._crear(
                driver=Driver.objects.create(nombre="Ana", documento="2"),
                fecha_ida=self.ahora + timedelta(hours=1),
                fecha_vuelta=self.ahora + timedelta(hours=9),
            )

    def test_iniciar_viaje_cambia_estado_y_vehiculo(self):
        v = self._crear()
        iniciar_viaje(v)
        v.refresh_from_db()
        self.assertEqual(v.estado, Viaje.EN_VIAJE)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.estado, Vehicle.EN_OPERACION)

    def test_finalizar_viaje_crea_billing_record(self):
        v = self._crear()
        iniciar_viaje(v)
        finalizar_viaje(v)
        v.refresh_from_db()
        self.assertEqual(v.estado, Viaje.FINALIZADO)
        record = BillingRecord.objects.get(viaje=v)
        self.assertEqual(record.valor, Decimal("800000"))
        self.assertEqual(record.horas, Decimal("0"))
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.estado, Vehicle.DISPONIBLE)

    def test_cancelar_viaje_bloquea_si_payroll_item(self):
        v = self._crear()
        from apps.nomina.models import Payroll, PayrollItem
        payroll = Payroll.objects.create(
            numero="NOM-2026-099", periodo_inicio=timezone.localdate(),
            periodo_fin=timezone.localdate()
        )
        PayrollItem.objects.create(payroll=payroll, viaje=v, valor=Decimal("400000"))
        with self.assertRaises(ValidationError):
            cancelar_viaje(v, "motivo")
```

- [ ] **Step 2: Ejecutar test — debe fallar por ImportError**

Run: `.\.venv\Scripts\python.exe manage.py test apps.operaciones.tests.test_viaje_services -v 2`
Expected: FAIL / ERROR `cannot import name 'crear_viaje'`.

- [ ] **Step 3: Modificar `BillingRecord`**

En `apps/facturacion/models.py`:
- `operation` → `null=True, blank=True`.
- Agregar:

```python
    viaje = models.ForeignKey(
        "operaciones.Viaje", on_delete=models.PROTECT, related_name="billing_records",
        null=True, blank=True
    )
```

- `clean()`:

```python
    def clean(self):
        super().clean()
        if bool(self.operation_id) == bool(self.viaje_id):
            raise ValidationError("El registro debe pertenecer exactamente a una operación o a un viaje.")
```

- `__str__` adaptado:

```python
    def __str__(self):
        if self.viaje_id:
            return f"{self.viaje.codigo} - ${self.valor}"
        placa = self.shift.vehicle.placa if self.shift_id else ""
        return f"{self.operation.codigo} - {placa}"
```

- [ ] **Step 4: Agregar services de viaje en `apps/operaciones/services.py`**

```python
def crear_viaje(*, cliente, vehicle, driver, origen, destino,
                fecha_ida, fecha_vuelta, valor_cobrado, valor_conductor,
                observaciones="", usuario=None):
    if fecha_vuelta <= fecha_ida:
        raise ValidationError("La fecha de vuelta debe ser posterior a la de ida.")
    solape_vehiculo = Viaje.objects.filter(
        vehicle=vehicle, estado__in=[Viaje.PENDIENTE, Viaje.EN_VIAJE],
        fecha_ida__lt=fecha_vuelta, fecha_vuelta__gt=fecha_ida
    ).exists()
    if solape_vehiculo:
        raise ValidationError("La mula ya tiene un viaje en ese horario.")
    solape_driver = Viaje.objects.filter(
        driver=driver, estado__in=[Viaje.PENDIENTE, Viaje.EN_VIAJE],
        fecha_ida__lt=fecha_vuelta, fecha_vuelta__gt=fecha_ida
    ).exists()
    if solape_driver:
        raise ValidationError("El conductor ya tiene un viaje en ese horario.")
    viaje = Viaje(
        cliente=cliente, vehicle=vehicle, driver=driver,
        origen=origen, destino=destino,
        fecha_ida=fecha_ida, fecha_vuelta=fecha_vuelta,
        valor_cobrado=valor_cobrado, valor_conductor=valor_conductor,
        observaciones=observaciones,
        created_by=usuario, updated_by=usuario,
    )
    viaje.full_clean()
    viaje.save()
    return viaje


def iniciar_viaje(viaje, usuario=None):
    if viaje.estado != Viaje.PENDIENTE:
        raise ValidationError("Solo se pueden iniciar viajes pendientes.")
    viaje.estado = Viaje.EN_VIAJE
    viaje.updated_by = usuario
    viaje.save(update_fields=["estado", "updated_by", "updated_at"])
    viaje.vehicle.estado = Vehicle.EN_OPERACION
    viaje.vehicle.save(update_fields=["estado"])
    return viaje


def finalizar_viaje(viaje, usuario=None):
    if viaje.estado != Viaje.EN_VIAJE:
        raise ValidationError("Solo se pueden finalizar viajes en curso.")
    from apps.facturacion.models import BillingRecord
    with transaction.atomic():
        viaje.estado = Viaje.FINALIZADO
        viaje.updated_by = usuario
        viaje.save(update_fields=["estado", "updated_by", "updated_at"])
        viaje.vehicle.estado = Vehicle.DISPONIBLE
        viaje.vehicle.save(update_fields=["estado"])
        BillingRecord.objects.create(
            viaje=viaje, operation=None,
            numero_relacion=f"VJ-{viaje.codigo}",
            fecha=timezone.localdate(),
            horas=Decimal("0"), tarifa_hora=Decimal("0"),
            valor=viaje.valor_cobrado,
            estado=BillingRecord.PENDIENTE,
            created_by=usuario, updated_by=usuario,
        )
    return viaje


def cancelar_viaje(viaje, motivo, usuario=None):
    if viaje.estado in (Viaje.FINALIZADO, Viaje.CANCELADO):
        raise ValidationError("El viaje ya está cerrado.")
    if viaje.payroll_items.exists():
        raise ValidationError("No se puede cancelar un viaje que ya fue liquidado en nómina.")
    with transaction.atomic():
        viaje.estado = Viaje.CANCELADO
        viaje.observaciones = (viaje.observaciones + f"\nCancelado: {motivo}").strip()
        viaje.updated_by = usuario
        viaje.save(update_fields=["estado", "observaciones", "updated_by", "updated_at"])
        if viaje.estado == Viaje.EN_VIAJE:
            viaje.vehicle.estado = Vehicle.DISPONIBLE
            viaje.vehicle.save(update_fields=["estado"])
    return viaje
```

(Nota: en `cancelar_viaje`, verificar el estado ANTES de cambiarlo para decidir si liberar el vehículo: usar `estado_anterior = viaje.estado` antes del `save`.)

- [ ] **Step 5: Crear migración y aplicar**

Run: `.\.venv\Scripts\python.exe manage.py makemigrations facturacion operaciones nomina`
Run: `.\.venv\Scripts\python.exe manage.py migrate`

- [ ] **Step 6: Ejecutar tests nuevos + facturación + operaciones**

Run: `.\.venv\Scripts\python.exe manage.py test apps.operaciones.tests.test_viaje_services apps.facturacion -v 1`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/operaciones/services.py apps/facturacion/models.py apps/operaciones/tests/test_viaje_services.py apps/operaciones/migrations/ apps/facturacion/migrations/
git commit -m "feat(viajes): services crear/iniciar/finalizar/cancelar; BillingRecord soporta viaje"
```

---

### Task 5: Vistas y URLs de viajes

**Files:**
- Create: `apps/operaciones/tests/test_viaje_views.py`
- Modify: `apps/operaciones/views.py` (agregar vistas de viaje)
- Modify: `apps/operaciones/urls.py` (agregar rutas)
- Modify: `apps/operaciones/forms.py` (agregar `ViajeForm`)
- Test runner: `python manage.py test apps.operaciones.tests.test_viaje_views -v 2`

**Interfaces:**
- Consumes: `Viaje` (Task 1), services (Task 4), `ViajeForm`.
- Produces: URLs `operaciones:viaje_lista`, `viaje_nuevo`, `viaje_detalle`, `viaje_iniciar`, `viaje_finalizar`, `viaje_cancelar`, `viaje_gastos`, `viaje_gasto_nuevo`, `viaje_gasto_editar`, `viaje_gasto_eliminar`.

- [ ] **Step 1: Escribir test fallido**

```python
# apps/operaciones/tests/test_viaje_views.py
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import OperationExpense, Viaje


class ViajeViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        self.user.groups.add(admin_group)
        self.cliente = CargoGenerator.objects.create(nombre="Cliente SA", nit="900111222-3")
        self.vehicle = Vehicle.objects.create(placa="ABC123", marca="Kenworth", estado=Vehicle.DISPONIBLE)
        self.driver = Driver.objects.create(nombre="Carlos", documento="1023456789")
        self.ahora = timezone.make_aware(datetime(2026, 8, 10, 6, 0))
        self.viaje = Viaje.objects.create(
            cliente=self.cliente, vehicle=self.vehicle, driver=self.driver,
            origen="Barranquilla", destino="Cartagena",
            fecha_ida=self.ahora, fecha_vuelta=self.ahora + timedelta(hours=8),
            valor_cobrado=Decimal("800000"), valor_conductor=Decimal("400000"),
        )
        self.client.force_login(self.user)

    def test_lista_requiere_login(self):
        self.client.logout()
        resp = self.client.get(reverse("operaciones:viaje_lista"))
        self.assertEqual(resp.status_code, 302)

    def test_lista_muestra_viajes(self):
        resp = self.client.get(reverse("operaciones:viaje_lista"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Barranquilla")

    def test_nuevo_viaje_post_crea(self):
        resp = self.client.post(reverse("operaciones:viaje_nuevo"), {
            "cliente": self.cliente.pk,
            "vehicle": self.vehicle.pk,
            "driver": self.driver.pk,
            "origen": "Barranquilla",
            "destino": "Santa Marta",
            "fecha_ida": "2026-08-15T06:00",
            "fecha_vuelta": "2026-08-15T14:00",
            "valor_cobrado": "900000",
            "valor_conductor": "450000",
            "observaciones": "",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Viaje.objects.filter(destino="Santa Marta").exists())

    def test_detalle_muestra_resumen(self):
        resp = self.client.get(reverse("operaciones:viaje_detalle", args=[self.viaje.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "800.000")

    def test_iniciar_viaje(self):
        resp = self.client.post(reverse("operaciones:viaje_iniciar", args=[self.viaje.pk]))
        self.assertEqual(resp.status_code, 302)
        self.viaje.refresh_from_db()
        self.assertEqual(self.viaje.estado, Viaje.EN_VIAJE)

    def test_finalizar_viaje(self):
        self.viaje.estado = Viaje.EN_VIAJE
        self.viaje.save()
        resp = self.client.post(reverse("operaciones:viaje_finalizar", args=[self.viaje.pk]))
        self.assertEqual(resp.status_code, 302)
        self.viaje.refresh_from_db()
        self.assertEqual(self.viaje.estado, Viaje.FINALIZADO)

    def test_cancelar_viaje(self):
        resp = self.client.post(reverse("operaciones:viaje_cancelar", args=[self.viaje.pk]), {"motivo": "no aplica"})
        self.assertEqual(resp.status_code, 302)
        self.viaje.refresh_from_db()
        self.assertEqual(self.viaje.estado, Viaje.CANCELADO)

    def test_gasto_nuevo_viaje(self):
        resp = self.client.post(reverse("operaciones:viaje_gasto_nuevo", args=[self.viaje.pk]), {
            "categoria": OperationExpense.COMBUSTIBLE,
            "vehicle": self.vehicle.pk,
            "proveedor": "",
            "fecha": "2026-08-10",
            "valor": "450000",
            "galones": "120",
            "descripcion": "ACPM",
            "numero_factura": "FAC-001",
            "observaciones": "",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(OperationExpense.objects.filter(viaje=self.viaje).exists())
```

- [ ] **Step 2: Ejecutar test — debe fallar (URL no resuelve)**

Run: `.\.venv\Scripts\python.exe manage.py test apps.operaciones.tests.test_viaje_views -v 2`
Expected: FAIL `Reverse for 'viaje_lista' not found`.

- [ ] **Step 3: Agregar `ViajeForm` en `apps/operaciones/forms.py`**

```python
class ViajeForm(forms.ModelForm):
    class Meta:
        model = Viaje
        fields = ["cliente", "vehicle", "driver", "origen", "destino",
                  "fecha_ida", "fecha_vuelta", "valor_cobrado",
                  "valor_conductor", "observaciones"]
        widgets = {
            "fecha_ida": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "fecha_vuelta": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehicle"].queryset = Vehicle.objects.filter(estado=Vehicle.DISPONIBLE)
        self.fields["vehicle"].label = "Mula"
        self.fields["cliente"].label = "Cliente"
        self.fields["valor_cobrado"].localize = True
        self.fields["valor_conductor"].localize = True
```

(Importar `Viaje` al inicio del archivo de forms.)

- [ ] **Step 4: Agregar vistas en `apps/operaciones/views.py`**

```python
@login_required
def viaje_lista(request):
    viajes = Viaje.objects.select_related("cliente", "vehicle", "driver").order_by("-fecha_ida")
    return render(request, "operaciones/viaje_list.html", {"viajes": viajes})


@login_required
def viaje_nuevo(request):
    if request.method == "POST":
        form = ViajeForm(request.POST)
        if form.is_valid():
            try:
                viaje = crear_viaje(
                    cliente=form.cleaned_data["cliente"],
                    vehicle=form.cleaned_data["vehicle"],
                    driver=form.cleaned_data["driver"],
                    origen=form.cleaned_data["origen"],
                    destino=form.cleaned_data["destino"],
                    fecha_ida=form.cleaned_data["fecha_ida"],
                    fecha_vuelta=form.cleaned_data["fecha_vuelta"],
                    valor_cobrado=form.cleaned_data["valor_cobrado"],
                    valor_conductor=form.cleaned_data["valor_conductor"],
                    observaciones=form.cleaned_data.get("observaciones", ""),
                    usuario=request.user,
                )
                messages.success(request, f"Viaje {viaje.codigo} creado.")
                return redirect("operaciones:viaje_detalle", pk=viaje.pk)
            except ValidationError as exc:
                form.add_error(None, exc.message)
    else:
        form = ViajeForm()
    return render(request, "operaciones/viaje_form.html", {"form": form, "creando": True})


@login_required
def viaje_detalle(request, pk):
    viaje = get_object_or_404(
        Viaje.objects.select_related("cliente", "vehicle", "driver"), pk=pk
    )
    gastos = viaje.expenses.select_related("vehicle", "proveedor").order_by("-fecha")
    total_gastos = gastos.aggregate(t=models.Sum("valor"))["t"] or Decimal("0")
    resultado = viaje.valor_cobrado - total_gastos
    return render(request, "operaciones/viaje_detail.html", {
        "viaje": viaje,
        "gastos": gastos,
        "total_gastos": total_gastos,
        "resultado": resultado,
    })


@role_required("Admin", "Secretaria")
def viaje_iniciar(request, pk):
    viaje = get_object_or_404(Viaje, pk=pk)
    if request.method == "POST":
        try:
            iniciar_viaje(viaje, usuario=request.user)
            messages.success(request, f"Viaje {viaje.codigo} iniciado.")
        except ValidationError as exc:
            messages.error(request, exc.message)
    return redirect("operaciones:viaje_detalle", pk=pk)


@role_required("Admin", "Secretaria")
def viaje_finalizar(request, pk):
    viaje = get_object_or_404(Viaje, pk=pk)
    if request.method == "POST":
        try:
            finalizar_viaje(viaje, usuario=request.user)
            messages.success(request, f"Viaje {viaje.codigo} finalizado. Se registró el cobro.")
        except ValidationError as exc:
            messages.error(request, exc.message)
    return redirect("operaciones:viaje_detalle", pk=pk)


@role_required("Admin", "Secretaria")
def viaje_cancelar(request, pk):
    viaje = get_object_or_404(Viaje, pk=pk)
    if request.method == "POST":
        motivo = request.POST.get("motivo", "")
        try:
            cancelar_viaje(viaje, motivo, usuario=request.user)
            messages.success(request, f"Viaje {viaje.codigo} cancelado.")
        except ValidationError as exc:
            messages.error(request, exc.message)
    return redirect("operaciones:viaje_detalle", pk=pk)


@login_required
def viaje_gasto_lista(request, pk):
    viaje = get_object_or_404(Viaje, pk=pk)
    gastos = viaje.expenses.select_related("vehicle", "proveedor").order_by("-fecha")
    return render(request, "operaciones/gasto_lista.html", {
        "viaje": viaje, "gastos": gastos, "es_viaje": True,
    })


@login_required
def viaje_gasto_nuevo(request, pk):
    viaje = get_object_or_404(Viaje, pk=pk)
    if request.method == "POST":
        form = OperationExpenseForm(request.POST, viaje=viaje)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.viaje = viaje
            gasto.created_by = request.user
            gasto.save()
            messages.success(request, "Gasto registrado.")
            return redirect("operaciones:viaje_detalle", pk=viaje.pk)
    else:
        form = OperationExpenseForm(viaje=viaje)
    return render(request, "operaciones/expense_form.html", {
        "form": form, "viaje": viaje, "es_viaje": True,
    })


@login_required
def viaje_gasto_editar(request, pk, gasto_pk):
    viaje = get_object_or_404(Viaje, pk=pk)
    gasto = get_object_or_404(OperationExpense, pk=gasto_pk, viaje=viaje)
    if request.method == "POST":
        form = OperationExpenseForm(request.POST, instance=gasto, viaje=viaje)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.viaje = viaje
            gasto.updated_by = request.user
            gasto.save()
            messages.success(request, "Gasto actualizado.")
            return redirect("operaciones:viaje_detalle", pk=viaje.pk)
    else:
        form = OperationExpenseForm(instance=gasto, viaje=viaje)
    return render(request, "operaciones/expense_form.html", {
        "form": form, "viaje": viaje, "es_viaje": True, "editing": True,
    })


@role_required("Admin", "Secretaria")
def viaje_gasto_eliminar(request, pk, gasto_pk):
    viaje = get_object_or_404(Viaje, pk=pk)
    gasto = get_object_or_404(OperationExpense, pk=gasto_pk, viaje=viaje)
    if request.method == "POST":
        gasto.delete()
        messages.success(request, "Gasto eliminado.")
    return redirect("operaciones:viaje_detalle", pk=viaje.pk)
```

(Imports necesarios al inicio de views.py: `Viaje`, `ViajeForm`, `crear_viaje`, `iniciar_viaje`, `finalizar_viaje`, `cancelar_viaje`, `models` de django.db para Sum, `Decimal`.)

- [ ] **Step 5: Agregar URLs en `apps/operaciones/urls.py`**

```python
path("viajes/", views.viaje_lista, name="viaje_lista"),
path("viajes/nuevo/", views.viaje_nuevo, name="viaje_nuevo"),
path("viajes/<int:pk>/", views.viaje_detalle, name="viaje_detalle"),
path("viajes/<int:pk>/iniciar/", views.viaje_iniciar, name="viaje_iniciar"),
path("viajes/<int:pk>/finalizar/", views.viaje_finalizar, name="viaje_finalizar"),
path("viajes/<int:pk>/cancelar/", views.viaje_cancelar, name="viaje_cancelar"),
path("viajes/<int:pk>/gastos/", views.viaje_gasto_lista, name="viaje_gastos"),
path("viajes/<int:pk>/gastos/nuevo/", views.viaje_gasto_nuevo, name="viaje_gasto_nuevo"),
path("viajes/<int:pk>/gastos/<int:gasto_pk>/editar/", views.viaje_gasto_editar, name="viaje_gasto_editar"),
path("viajes/<int:pk>/gastos/<int:gasto_pk>/eliminar/", views.viaje_gasto_eliminar, name="viaje_gasto_eliminar"),
```

- [ ] **Step 6: Ejecutar test — aún puede fallar por templates faltantes; crear templates mínimos**

Crear `templates/operaciones/viaje_list.html`:

```django
{% extends "base.html" %}
{% block title %}Viajes locales{% endblock %}
{% block page_title %}Viajes locales{% endblock %}
{% block content %}
<p class="eyebrow">Transportes Renacer</p>
<h1>Viajes locales</h1>
<p class="meta-update">Fletes ciudad a ciudad</p>

<div class="card">
  <div class="card-title">Nuevo viaje</div>
  <a class="btn-primary" href="{% url 'operaciones:viaje_nuevo' %}">Crear viaje</a>
</div>

<div class="card">
  <div class="card-title">Viajes</div>
  {% if viajes %}
  <table class="table">
    <thead>
      <tr><th>Código</th><th>Ruta</th><th>Cliente</th><th>Mula</th><th>Conductor</th><th>Estado</th><th></th></tr>
    </thead>
    <tbody>
      {% for v in viajes %}
      <tr>
        <td class="mono">{{ v.codigo }}</td>
        <td>{{ v.origen }} → {{ v.destino }}</td>
        <td>{{ v.cliente.nombre }}</td>
        <td>{{ v.vehicle.placa }}</td>
        <td>{{ v.driver.nombre }}</td>
        <td><span class="badge {% if v.estado == 'finalizado' %}badge-ok{% elif v.estado == 'cancelado' %}badge-idle{% else %}badge-idle{% endif %}">{{ v.get_estado_display }}</span></td>
        <td><a class="btn-link" href="{% url 'operaciones:viaje_detalle' v.pk %}">Ver</a></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="empty-txt">No hay viajes registrados.</p>
  {% endif %}
</div>
{% endblock %}
```

Crear `templates/operaciones/viaje_form.html`:

```django
{% extends "base.html" %}
{% block title %}{% if creando %}Nuevo viaje{% else %}Editar viaje{% endif %}{% endblock %}
{% block page_title %}{% if creando %}Nuevo viaje{% else %}Editar viaje{% endif %}{% endblock %}
{% block content %}
<p class="eyebrow">Transportes Renacer</p>
<h1>{% if creando %}Nuevo viaje local{% else %}Editar viaje{% endif %}</h1>

<form method="post" class="card">
  {% csrf_token %}
  {% if form.non_field_errors %}<div class="alerta"><p>{{ form.non_field_errors }}</p></div>{% endif %}
  <div class="form-grid">
    {% for field in form %}
    <div class="form-field">
      {{ field.label_tag }}{{ field }}{{ field.errors }}
    </div>
    {% endfor %}
  </div>
  <button type="submit" class="btn-primary">Guardar viaje</button>
  <a class="btn-secondary" href="{% url 'operaciones:viaje_lista' %}">Cancelar</a>
</form>
{% endblock %}
```

Crear `templates/operaciones/viaje_detail.html`:

```django
{% extends "base.html" %}
{% block title %}Viaje {{ viaje.codigo }}{% endblock %}
{% block page_title %}Viaje {{ viaje.codigo }}{% endblock %}
{% block content %}
<p class="eyebrow">Transportes Renacer</p>
<h1>{{ viaje.origen }} → {{ viaje.destino }}</h1>
<p class="meta-update">{{ viaje.codigo }} · {{ viaje.cliente.nombre }} · {{ viaje.get_estado_display }}</p>

<div class="card">
  <div class="card-title">Acciones</div>
  {% if viaje.estado == 'pendiente' %}
  <form method="post" action="{% url 'operaciones:viaje_iniciar' viaje.pk %}" style="display:inline">{% csrf_token %}
    <button type="submit" class="btn-primary">Iniciar viaje</button>
  </form>
  {% elif viaje.estado == 'en_viaje' %}
  <form method="post" action="{% url 'operaciones:viaje_finalizar' viaje.pk %}" style="display:inline">{% csrf_token %}
    <button type="submit" class="btn-primary">Finalizar viaje</button>
  </form>
  {% endif %}
  {% if viaje.estado == 'pendiente' or viaje.estado == 'en_viaje' %}
  <form method="post" action="{% url 'operaciones:viaje_cancelar' viaje.pk %}" style="display:inline" onsubmit="return confirm('¿Cancelar este viaje?');">{% csrf_token %}
    <input type="hidden" name="motivo" value="Cancelado por el usuario">
    <button type="submit" class="btn-secondary">Cancelar viaje</button>
  </form>
  {% endif %}
</div>

<div class="card">
  <div class="card-title">Datos del viaje</div>
  <div class="form-grid">
    <div class="form-field"><span class="kpi-label">Mula</span><p>{{ viaje.vehicle.placa }} ({{ viaje.vehicle.marca }})</p></div>
    <div class="form-field"><span class="kpi-label">Conductor</span><p>{{ viaje.driver.nombre }}</p></div>
    <div class="form-field"><span class="kpi-label">Ida</span><p>{{ viaje.fecha_ida|date:"d/m/Y H:i" }}</p></div>
    <div class="form-field"><span class="kpi-label">Vuelta</span><p>{{ viaje.fecha_vuelta|date:"d/m/Y H:i" }}</p></div>
    <div class="form-field"><span class="kpi-label">Valor cobrado</span><p class="kpi-value">${{ viaje.valor_cobrado|floatformat:0 }}</p></div>
    <div class="form-field"><span class="kpi-label">Valor conductor</span><p class="kpi-value">${{ viaje.valor_conductor|floatformat:0 }}</p></div>
  </div>
</div>

<div class="card">
  <div class="card-title">Gastos del viaje</div>
  <a class="btn-primary" href="{% url 'operaciones:viaje_gasto_nuevo' viaje.pk %}">+ Agregar gasto</a>
  {% if gastos %}
  <table class="table">
    <thead><tr><th>Fecha</th><th>Categoría</th><th>Valor</th><th>Factura</th><th></th></tr></thead>
    <tbody>
      {% for g in gastos %}
      <tr>
        <td>{{ g.fecha|date:"d/m/Y" }}</td>
        <td>{{ g.get_categoria_display }}</td>
        <td>${{ g.valor|floatformat:0 }}</td>
        <td class="mono">{{ g.numero_factura }}</td>
        <td><a class="btn-link" href="{% url 'operaciones:viaje_gasto_editar' viaje.pk g.pk %}">Editar</a></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="empty-txt">Sin gastos registrados.</p>
  {% endif %}
</div>

<div class="card">
  <div class="card-title">Resumen financiero</div>
  <div class="form-grid">
    <div class="form-field"><span class="kpi-label">Total gastos</span><p class="kpi-value">${{ total_gastos|floatformat:0 }}</p></div>
    <div class="form-field"><span class="kpi-label">Resultado (cobrado - gastos)</span><p class="kpi-value">${{ resultado|floatformat:0 }}</p></div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 7: Ejecutar test de views — debe pasar**

Run: `.\.venv\Scripts\python.exe manage.py test apps.operaciones.tests.test_viaje_views -v 2`
Expected: PASS.

- [ ] **Step 8: Ejecutar tests de operaciones completos**

Run: `.\.venv\Scripts\python.exe manage.py test apps.operaciones -v 1`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add apps/operaciones/views.py apps/operaciones/urls.py apps/operaciones/forms.py apps/operaciones/tests/test_viaje_views.py templates/operaciones/viaje_list.html templates/operaciones/viaje_form.html templates/operaciones/viaje_detail.html
git commit -m "feat(viajes): vistas, URLs, forms y templates del módulo de viajes"
```

---

### Task 6: UI híbrida (selector Portuaria/Local + menú lateral)

**Files:**
- Modify: `templates/base.html` (ítem de menú Viajes)
- Modify: `templates/operaciones/operacion_list.html` (botón híbrido)
- Test manual / smoke test.

- [ ] **Step 1: Agregar ítem de menú en `templates/base.html`**

En el bloque `{% if 'Admin' in user_groups or 'Secretaria' in user_groups %}` que contiene Operaciones, agregar después del enlace de Operaciones:

```django
<a class="nav-link {% if request.resolver_match.url_name == 'viaje_lista' %}active{% endif %}"
   href="{% url 'operaciones:viaje_lista' %}">
  <span class="material-symbols-outlined">local_shipping</span> Viajes
</a>
```

- [ ] **Step 2: Cambiar botón en `operacion_list.html`**

Donde esté el botón de "Nueva operación" o el bloque `topbar_action`, reemplazar por un selector discreto (o dos enlaces):

```django
<div class="card" style="margin-bottom:1rem;">
  <div class="card-title">Nueva operación</div>
  <a class="btn-primary" href="{% url 'operaciones:nuevo' %}">Portuaria (buque/puerto)</a>
  <a class="btn-secondary" href="{% url 'operaciones:viaje_nuevo' %}">Local (flete ciudad a ciudad)</a>
</div>
```

(Adaptar al HTML real existente en ese template — leerlo antes de editar y reemplazar el botón/acción correspondiente sin romper el form inline existente.)

- [ ] **Step 3: Smoke test manual**

Run: `.\.venv\Scripts\python.exe manage.py runserver`
Navegar a `/operaciones/` y `/operaciones/viajes/`, verificar menú y selector.

- [ ] **Step 4: Commit**

```bash
git add templates/base.html templates/operaciones/operacion_list.html
git commit -m "feat(viajes): UI híbrida Portuaria/Local y menú lateral"
```

---

### Task 7: Seed de viajes de ejemplo

**Files:**
- Modify: `seed_demo.py` (agregar bloque de viajes antes del resumen)

- [ ] **Step 1: Agregar bloque de viajes en `seed_demo.py`**

Antes del PASO de Resumen, agregar:

```python
# ─────────────────────────────────────────────────────────────────────
# PASO: Crear viajes locales de ejemplo
# ─────────────────────────────────────────────────────────────────────
from apps.operaciones.services import crear_viaje, iniciar_viaje, finalizar_viaje

# Viaje 1: FINALIZADO (hace ~10 días) con gastos
viaje1 = crear_viaje(
    cliente=generador1, vehicle=jkl, driver=maria,
    origen="Barranquilla", destino="Cartagena",
    fecha_ida=timezone.datetime.combine(hoy - timedelta(days=10), timezone.datetime.min.time().replace(hour=6)),
    fecha_vuelta=timezone.datetime.combine(hoy - timedelta(days=10), timezone.datetime.min.time().replace(hour=16)),
    valor_cobrado=Decimal("1200000"), valor_conductor=Decimal("600000"),
    usuario=user,
)
iniciar_viaje(viaje1, usuario=user)
finalizar_viaje(viaje1, usuario=user)
OperationExpense.objects.create(
    viaje=viaje1, vehicle=jkl, proveedor=proveedor_acpm,
    categoria=OperationExpense.COMBUSTIBLE, fecha=hoy - timedelta(days=10),
    valor=Decimal("380000"), galones=Decimal("100"), numero_factura="FV-001",
)
OperationExpense.objects.create(
    viaje=viaje1, vehicle=jkl,
    categoria=OperationExpense.PEAJE, fecha=hoy - timedelta(days=10),
    valor=Decimal("70000"), descripcion="Peaje Barranquilla-Cartagena",
)

# Viaje 2: EN_VIAJE (iniciado hace 2 días)
viaje2 = crear_viaje(
    cliente=generador2, vehicle=pqr, driver=juan,
    origen="Barranquilla", destino="Santa Marta",
    fecha_ida=timezone.datetime.combine(hoy - timedelta(days=2), timezone.datetime.min.time().replace(hour=5)),
    fecha_vuelta=timezone.datetime.combine(hoy - timedelta(days=2), timezone.datetime.min.time().replace(hour=18)),
    valor_cobrado=Decimal("1500000"), valor_conductor=Decimal("750000"),
    usuario=user,
)
iniciar_viaje(viaje2, usuario=user)

# Viaje 3: PENDIENTE (sale mañana)
crear_viaje(
    cliente=generador1, vehicle=jkl, driver=luis,
    origen="Cartagena", destino="Barranquilla",
    fecha_ida=timezone.datetime.combine(hoy + timedelta(days=1), timezone.datetime.min.time().replace(hour=7)),
    fecha_vuelta=timezone.datetime.combine(hoy + timedelta(days=1), timezone.datetime.min.time().replace(hour=17)),
    valor_cobrado=Decimal("1100000"), valor_conductor=Decimal("550000"),
    usuario=user,
)
```

(Importar `Decimal` y `Viaje` si no están; `crear_viaje` etc. desde services.)

- [ ] **Step 2: Ejecutar seed limpio y verificar**

Run: `cmd /c ".\.venv\Scripts\python.exe manage.py shell < clear_demo.py"` (o limpiar)
Run: `.\.venv\Scripts\python.exe manage.py shell -c "exec(open('seed_demo.py', encoding='utf-8').read())"`
Expected: resumen incluye 3 viajes; verificar `Viaje.objects.count() == 3`.

- [ ] **Step 3: Commit**

```bash
git add seed_demo.py
git commit -m "feat(viajes): seed agrega viajes locales de ejemplo"
```

---

### Task 8: Tests end-to-end del módulo (agente de pruebas)

**Files:**
- Create: `apps/operaciones/tests/test_viaje_e2e.py`
- Dispatch: subagente `general` con instrucciones de ejecutar la suite completa y reportar.

- [ ] **Step 1: Escribir test E2E que cubra el flujo completo**

```python
# apps/operaciones/tests/test_viaje_e2e.py
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator
from apps.conductores.models import Driver
from apps.facturacion.models import BillingRecord
from apps.flota.models import Vehicle
from apps.nomina.models import Payroll
from apps.nomina.services import crear_liquidacion
from apps.operaciones.models import OperationExpense, Viaje
from apps.operaciones.services import cancelar_viaje, crear_viaje, finalizar_viaje, iniciar_viaje


class ViajeE2ETests(TestCase):
    """Flujo completo: crear → iniciar → gastos → finalizar → facturación → nómina → cancelar bloqueado."""

    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="x")
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        self.user.groups.add(admin_group)
        self.cliente = CargoGenerator.objects.create(nombre="Comercial El Éxito", nit="900111222-3")
        self.vehicle = Vehicle.objects.create(placa="XYZ789", marca="Volvo", estado=Vehicle.DISPONIBLE)
        self.driver = Driver.objects.create(nombre="Luis Pérez", documento="1099887766")
        self.ahora = timezone.make_aware(datetime(2026, 8, 10, 6, 0))

    def test_flujo_completo_viaje_local(self):
        # 1. Crear viaje
        viaje = crear_viaje(
            cliente=self.cliente, vehicle=self.vehicle, driver=self.driver,
            origen="Barranquilla", destino="Cartagena",
            fecha_ida=self.ahora, fecha_vuelta=self.ahora + timedelta(hours=10),
            valor_cobrado=Decimal("1200000"), valor_conductor=Decimal("600000"),
            usuario=self.user,
        )
        self.assertEqual(viaje.estado, Viaje.PENDIENTE)
        self.assertTrue(viaje.codigo.startswith("VJ-"))

        # 2. Iniciar
        iniciar_viaje(viaje, usuario=self.user)
        viaje.refresh_from_db()
        self.assertEqual(viaje.estado, Viaje.EN_VIAJE)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.estado, Vehicle.EN_OPERACION)

        # 3. Cargar gastos vía formulario
        self.client.force_login(self.user)
        resp = self.client.post(reverse("operaciones:viaje_gasto_nuevo", args=[viaje.pk]), {
            "categoria": OperationExpense.COMBUSTIBLE,
            "vehicle": self.vehicle.pk,
            "proveedor": "",
            "fecha": "2026-08-10",
            "valor": "450000",
            "galones": "120",
            "descripcion": "ACPM viaje",
            "numero_factura": "FV-100",
            "observaciones": "",
        })
        self.assertEqual(resp.status_code, 302)
        resp = self.client.post(reverse("operaciones:viaje_gasto_nuevo", args=[viaje.pk]), {
            "categoria": OperationExpense.PEAJE,
            "vehicle": self.vehicle.pk,
            "proveedor": "",
            "fecha": "2026-08-10",
            "valor": "70000",
            "galones": "",
            "descripcion": "Peaje",
            "numero_factura": "",
            "observaciones": "",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(viaje.expenses.count(), 2)

        # 4. Finalizar
        finalizar_viaje(viaje, usuario=self.user)
        viaje.refresh_from_db()
        self.assertEqual(viaje.estado, Viaje.FINALIZADO)
        record = BillingRecord.objects.get(viaje=viaje)
        self.assertEqual(record.valor, Decimal("1200000"))
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.estado, Vehicle.DISPONIBLE)

        # 5. Detalle muestra resumen
        resp = self.client.get(reverse("operaciones:viaje_detalle", args=[viaje.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "1.200.000")
        self.assertContains(resp, "520.000")  # gastos: 450k + 70k

        # 6. Nómina incluye el viaje
        payroll = crear_liquidacion(date(2026, 8, 1), date(2026, 8, 31), usuario=self.user)
        item = payroll.items.get()
        self.assertEqual(item.viaje, viaje)
        self.assertEqual(item.valor, Decimal("600000"))
        self.assertEqual(payroll.total, Decimal("600000"))

        # 7. Cancelar tras liquidar debe fallar
        with self.assertRaises(Exception):
            cancelar_viaje(viaje, "intento")
```

(Agregar `from datetime import date` al inicio.)

- [ ] **Step 2: Ejecutar test E2E**

Run: `.\.venv\Scripts\python.exe manage.py test apps.operaciones.tests.test_viaje_e2e -v 2`
Expected: PASS.

- [ ] **Step 3: Ejecutar suite completa del proyecto**

Run: `.\.venv\Scripts\python.exe manage.py test -v 1`
Expected: PASS (sin regresiones).

- [ ] **Step 4: Dispatch agente de pruebas end-to-end de la página**

Lanzar subagente `general` con prompt: levantar `runserver` en segundo plano, usar `urllib` o `requests` para hacer login con `admin/admin123` y verificar que las páginas `/operaciones/`, `/operaciones/viajes/`, `/operaciones/viajes/nuevo/` y el dashboard responden 200 y contienen texto esperado; reportar hallazgos.

- [ ] **Step 5: Commit final**

```bash
git add apps/operaciones/tests/test_viaje_e2e.py
git commit -m "test(viajes): E2E del flujo completo de viaje local"
```

---

## Self-Review

1. **Spec coverage:**
   - Modelo Viaje ✓ Task 1
   - PayrollItem ✓ Task 2
   - OperationExpense ✓ Task 3
   - BillingRecord + finalizar_viaje ✓ Task 4
   - Vistas/URLs/forms/templates ✓ Task 5
   - UI híbrida ✓ Task 6
   - Seed ✓ Task 7
   - E2E + agente de pruebas ✓ Task 8
   - Dashboard KPIs: NO cubierto (decisión: fase 2, documentado en spec)

2. **Placeholder scan:** sin TBD/TODO; todos los pasos tienen código o comandos concretos.

3. **Type consistency:** `crear_viaje` siempre con kwargs; `Viaje.codigo` auto; `BillingRecord.viaje` FK; `PayrollItem.viaje` FK — consistente entre tasks.
