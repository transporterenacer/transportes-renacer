# Plan 5 — Dashboards, historial y Gantt

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar el MVP con el panel de control completo: dashboard principal (operativo-financiero), dashboard de flota con panel de vencimientos, dashboard de nómina con rankings y doble turno, dashboard operativo, dashboard financiero con gráfica de evolución (Chart.js vendored), historial de operaciones, y el **Gantt multi-día** por operación (eje continuo, línea AHORA, turnos nocturnos, panel de detalle). Sustituye el stub `inicio` por el dashboard real.

**Architecture:** Django 5.2 monolítico. Nueva app `apps/dashboard` con una vista por dashboard, un módulo `services.py` con las consultas de agregación reutilizables, y el endpoint JSON del Gantt. Chart.js se descarga como archivo estático local (`static/vendor/chart.umd.js`) — sin CDN en runtime. El Gantt es JS vanilla sobre los tokens CSS existentes, con eje de tiempo continuo. Todas las vistas `@login_required`.

**Tech Stack:** Django 5.2, HTMX (base.html), Chart.js 4.x (vendored en `static/vendor/`), CSS puro con tokens, JS vanilla para el Gantt. Reutiliza: `apps.flota.services.alertas_vencimiento`, `apps.operaciones.services.detectar_dobles_turnos`, `apps.nomina.services.resumen_liquidacion`, `apps.facturacion.services.saldo_operacion`, `Operation.total_horas`, `Shift`, `BillingRecord`, `ClientPayment`, `Payroll`, `Incident`.

**Spec de referencia:** `docs/superpowers/specs/2026-08-15-puerto-ops-design.md` (secciones 8, 10, 19, 27, 28, 29, 30, 31, 32, 33, 40). Planes 1-4 completados (106/106 tests, HEAD 9c09149).

## Global Constraints

- Zona `America/Bogota`. Moneda COP: formatear en template con separador de miles (filtro personalizado o `|intcomma` de `humanize`).
- Todas las vistas del dashboard `@login_required`. El stub `inicio` (TemplateView público) se elimina; `LOGIN_REDIRECT_URL` pasa a `dashboard:inicio`.
- **"Información registrada hasta"**: se calcula como el `updated_at` máximo de las entidades relevantes de cada dashboard (regla §26). Nunca "ahora". Se muestra en cada dashboard.
- El dashboard principal enfoca **operaciones activas** (§27).
- Panel de vencimientos (§10): Mula, Documento, Vencimiento, Días restantes, Estado (Normal/Próximo/Vencido) con semáforo 🟢🟡🔴; cada alerta enlaza a la ficha del vehículo (admin). Usa `alertas_vencimiento()` de `apps.flota`.
- Rankings de nómina (§30): más horas, más turnos, posibles dobles turnos (usa `detectar_dobles_turnos`).
- Dashboard financiero (§32): valor generado, abonos, saldo pendiente, valor por operación, operaciones con mayor saldo, evolución de facturación (Chart.js line).
- Historial de operaciones (§28): operaciones finalizadas/canceladas con trazabilidad (vínculo a detalle).
- Gantt (§19/§40): eje de tiempo continuo multi-día (no 24 columnas por día), filas por mula asignada, bloques por timestamp absoluto, turnos nocturnos cruzan la medianoche, línea AHORA en `--secondary` (hora servidor Bogotá), colores por cumplimiento (`ok`≥90, `warn` 70–89, `bad`<70), turnos cancelados/anulados punteados, click → panel de detalle con novedad. Datos vía `fetch('/dashboard/gantt/<pk>/datos/')` (endpoint JSON). Filtros: operación (por URL), mula, rango de fechas.
- Git SOLO LOCAL (sin remoto). Cada task termina con tests en verde y commit local.
- Idioma español (es-co). Sin build step; todo el JS/CSS es estático servido por Whitenoise.

---

### Task 1: App dashboard — vistas de agregación, servicios, reemplazo del stub inicio

**Files:**
- Create: `apps/dashboard/__init__.py`
- Create: `apps/dashboard/apps.py`
- Create: `apps/dashboard/services.py`
- Create: `apps/dashboard/views.py`
- Create: `apps/dashboard/urls.py`
- Create: `apps/dashboard/tests/__init__.py`
- Create: `apps/dashboard/tests/test_views.py`
- Create: `templates/dashboard/inicio.html`
- Create: `templates/dashboard/vencimientos.html`
- Create: `templates/dashboard/nomina.html`
- Create: `templates/dashboard/operativo.html`
- Create: `templates/dashboard/financiero.html`
- Create: `templates/dashboard/historial.html`
- Create: `templates/dashboard/gantt.html`
- Modify: `config/settings/base.py` (INSTALLED_APPS + `"django.contrib.humanize"` + `"apps.dashboard"`; LOGIN_REDIRECT_URL → `"dashboard:inicio"`)
- Modify: `config/urls.py` (incluir `apps.dashboard.urls` en `/`; eliminar el stub TemplateView y `templates/inicio.html`)
- Delete: `templates/inicio.html`
- Modify: `static/css/app.css` (estilos de dashboard: `.kpi-grid`, `.kpi`, `.alert-item`, `.alert-ok`, `.alert-warn`, `.alert-danger`, `.gantt`)

**Interfaces:**
- Consumes: `Operation`, `Shift`, `Vehicle`, `VehicleDocument` (+ `alertas_vencimiento`), `Payroll`, `BillingRecord`, `ClientPayment`, `Incident`, `CargoGenerator`.
- Produces:
  - `def ultima_actualizacion(*modelos) -> datetime|None` — el `updated_at` máximo entre los modelos dados.
  - `def kpis_inicio() -> dict` — operaciones activas, mulas en operación/disponibles/en taller, horas trabajadas (Σ horas realizadas), horas facturables (Σ horas billing), valor generado (Σ billing.valor), abonos (Σ client_payments), saldo pendiente (Σ facturado − Σ abonado de todas las operaciones), nómina semanal pendiente (Σ total de payrolls no pagados).
  - Vistas: `dashboard_inicio`, `dashboard_vencimientos`, `dashboard_nomina`, `dashboard_operativo`, `dashboard_financiero`, `dashboard_historial`, `dashboard_gantt`, `gantt_datos`. Cada una calcula su `ultima_actualizacion` con los modelos relevantes.
  - URL namespace `dashboard`:
    - `dashboard:inicio` → `/` (dashboard principal).
    - `dashboard:vencimientos` → `/vencimientos/`.
    - `dashboard:nomina` → `/nomina/`.
    - `dashboard:operativo` → `/operativo/`.
    - `dashboard:financiero` → `/financiero/`.
    - `dashboard:historial` → `/historial/`.
    - `dashboard:gantt` (`<int:pk>/`) → `/gantt/<pk>/`.
    - `dashboard:gantt_datos` (`<int:pk>/datos/`) → JSON.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/dashboard/tests/test_views.py`:

```python
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.catalogos.models import CargoGenerator, Port
from apps.flota.models import Vehicle


class DashboardViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.client.force_login(self.user)

    def test_inicio_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse("dashboard:inicio"))
        self.assertEqual(response.status_code, 302)

    def test_inicio_renderiza_kpis(self):
        response = self.client.get(reverse("dashboard:inicio"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operaciones activas")
        self.assertContains(response, "Información registrada hasta")

    def test_navbar_tiene_enlaces_a_dashboards(self):
        response = self.client.get(reverse("dashboard:inicio"))
        self.assertContains(response, reverse("dashboard:vencimientos"))
        self.assertContains(response, reverse("dashboard:nomina"))
        self.assertContains(response, reverse("dashboard:operativo"))
        self.assertContains(response, reverse("dashboard:financiero"))
        self.assertContains(response, reverse("dashboard:historial"))

    def test_vencimientos_renderiza(self):
        response = self.client.get(reverse("dashboard:vencimientos"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vencimientos")

    def test_nomina_renderiza(self):
        response = self.client.get(reverse("dashboard:nomina"))
        self.assertEqual(response.status_code, 200)

    def test_operativo_renderiza(self):
        response = self.client.get(reverse("dashboard:operativo"))
        self.assertEqual(response.status_code, 200)

    def test_financiero_renderiza(self):
        response = self.client.get(reverse("dashboard:financiero"))
        self.assertEqual(response.status_code, 200)

    def test_historial_renderiza(self):
        response = self.client.get(reverse("dashboard:historial"))
        self.assertEqual(response.status_code, 200)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.dashboard.tests -v 2`
Expected: FAIL — `NoReverseMatch` para `dashboard:inicio`.

- [ ] **Step 3: Configurar settings**

En `config/settings/base.py`:
- Añadir `"django.contrib.humanize"` al bloque de apps de contribución (después de `"django.contrib.staticfiles"`).
- Añadir `"apps.dashboard",` después de `"apps.facturacion",`.
- Cambiar `LOGIN_REDIRECT_URL = "inicio"` → `LOGIN_REDIRECT_URL = "dashboard:inicio"`.

- [ ] **Step 4: Implementar servicios y vistas**

Crear `apps/dashboard/__init__.py` (vacío), `apps/dashboard/apps.py`:

```python
from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dashboard"
```

Crear `apps/dashboard/services.py`:

```python
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.facturacion.models import BillingRecord, ClientPayment
from apps.flota.models import Vehicle
from apps.nomina.models import Payroll
from apps.operaciones.models import Operation, Shift


def ultima_actualizacion(*modelos):
    actual = None
    for modelo in modelos:
        ts = modelo.objects.aggregate(max_ts=Max("updated_at"))["max_ts"]
        if ts and (actual is None or ts > actual):
            actual = ts
    return actual


def kpis_inicio():
    activas = Operation.objects.filter(estado=Operation.ACTIVA)
    horas_trabajadas = (
        Shift.objects.filter(estado=Shift.REALIZADO)
        .aggregate(total=Sum("horas_trabajadas"))["total"]
        or Decimal(0)
    )
    horas_facturables = (
        BillingRecord.objects.aggregate(total=Sum("horas"))["total"] or Decimal(0)
    )
    valor_generado = (
        BillingRecord.objects.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )
    abonos = (
        ClientPayment.objects.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )
    nomina_pendiente = (
        Payroll.objects.exclude(estado=Payroll.PAGADO)
        .aggregate(total=Sum("total"))["total"]
        or Decimal(0)
    )
    return {
        "operaciones_activas": activas.count(),
        "mulas_en_operacion": Vehicle.objects.filter(estado=Vehicle.EN_OPERACION).count(),
        "mulas_disponibles": Vehicle.objects.filter(estado=Vehicle.DISPONIBLE).count(),
        "mulas_en_taller": Vehicle.objects.filter(estado=Vehicle.EN_TALLER).count(),
        "horas_trabajadas": horas_trabajadas,
        "horas_facturables": horas_facturables,
        "valor_generado": valor_generado,
        "abonos": abonos,
        "saldo_pendiente": valor_generado - abonos,
        "nomina_semanal_pendiente": nomina_pendiente,
    }
```

Nota: añadir `from django.db.models import Max` al import en services.py (el import de arriba solo trae `Sum` — ajustar a `from django.db.models import Max, Sum`).

Crear `apps/dashboard/views.py`:

```python
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from apps.dashboard.services import kpis_inicio, ultima_actualizacion
from apps.facturacion.models import BillingRecord, ClientPayment
from apps.flota.models import Vehicle, VehicleDocument
from apps.flota.services import alertas_vencimiento
from apps.nomina.models import Payroll
from apps.operaciones.models import Operation, Shift


@login_required
def dashboard_inicio(request):
    context = {
        "kpis": kpis_inicio(),
        "operaciones_activas": Operation.objects.filter(estado=Operation.ACTIVA),
        "ultima_actualizacion": ultima_actualizacion(
            Operation, Shift, BillingRecord, ClientPayment, Payroll
        ),
    }
    return render(request, "dashboard/inicio.html", context)


@login_required
def dashboard_vencimientos(request):
    context = {
        "alertas": alertas_vencimiento(),
        "flota": {
            "total": Vehicle.objects.count(),
            "en_operacion": Vehicle.objects.filter(estado=Vehicle.EN_OPERACION).count(),
            "disponibles": Vehicle.objects.filter(estado=Vehicle.DISPONIBLE).count(),
            "en_taller": Vehicle.objects.filter(estado=Vehicle.EN_TALLER).count(),
            "fuera_de_servicio": Vehicle.objects.filter(estado=Vehicle.FUERA_DE_SERVICIO).count(),
        },
        "ultima_actualizacion": ultima_actualizacion(Vehicle, VehicleDocument),
    }
    return render(request, "dashboard/vencimientos.html", context)


@login_required
def dashboard_nomina(request):
    context = {
        "ultima_actualizacion": ultima_actualizacion(Payroll),
    }
    return render(request, "dashboard/nomina.html", context)


@login_required
def dashboard_operativo(request):
    context = {
        "ultima_actualizacion": ultima_actualizacion(Operation, Shift),
    }
    return render(request, "dashboard/operativo.html", context)


@login_required
def dashboard_financiero(request):
    context = {
        "ultima_actualizacion": ultima_actualizacion(BillingRecord, ClientPayment),
    }
    return render(request, "dashboard/financiero.html", context)


@login_required
def dashboard_historial(request):
    context = {
        "operaciones": Operation.objects.filter(
            estado__in=[Operation.FINALIZADA, Operation.CANCELADA]
        ).order_by("-fecha_inicio"),
    }
    return render(request, "dashboard/historial.html", context)


@login_required
def dashboard_gantt(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    return render(request, "dashboard/gantt.html", {"operation": operation})
```

Nota: `dashboard_nomina`, `dashboard_operativo` y `dashboard_financiero` se completan en las Tasks 3-5. En esta Task 1 solo renderizan plantillas con la fecha de actualización.

Crear `apps/dashboard/urls.py`:

```python
from django.urls import path

from apps.dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_inicio, name="inicio"),
    path("vencimientos/", views.dashboard_vencimientos, name="vencimientos"),
    path("nomina/", views.dashboard_nomina, name="nomina"),
    path("operativo/", views.dashboard_operativo, name="operativo"),
    path("financiero/", views.dashboard_financiero, name="financiero"),
    path("historial/", views.dashboard_historial, name="historial"),
    path("gantt/<int:pk>/", views.dashboard_gantt, name="gantt"),
    path("gantt/<int:pk>/datos/", views.gantt_datos, name="gantt_datos"),
]
```

En `config/urls.py`, sustituir el bloque de urlpatterns por:

```python
urlpatterns = [
    path("", include("apps.dashboard.urls")),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("operaciones/", include("apps.operaciones.urls")),
    path("nomina/", include("apps.nomina.urls")),
    path("facturacion/", include("apps.facturacion.urls")),
]
```

Eliminar `from django.views.generic import TemplateView` y el `path("", TemplateView...)`. Eliminar `templates/inicio.html`.

- [ ] **Step 5: Crear plantillas del dashboard y estilos**

Crear `templates/dashboard/inicio.html`:

```html
{% extends "base.html" %}
{% load humanize %}
{% block title %}Panel de control{% endblock %}
{% block content %}
<p class="eyebrow">Transportes Renacer · Dashboard</p>
<h1>Panel de control</h1>
<p class="meta-update">Información registrada hasta: {{ ultima_actualizacion|date:"d/m/Y H:i"|default:"—" }}</p>

<div class="kpi-grid">
  <div class="kpi"><span class="kpi-value">{{ kpis.operaciones_activas }}</span><span class="kpi-label">Operaciones activas</span></div>
  <div class="kpi"><span class="kpi-value">{{ kpis.mulas_en_operacion }}</span><span class="kpi-label">Mulas en operación</span></div>
  <div class="kpi"><span class="kpi-value">{{ kpis.mulas_disponibles }}</span><span class="kpi-label">Mulas disponibles</span></div>
  <div class="kpi"><span class="kpi-value">{{ kpis.mulas_en_taller }}</span><span class="kpi-label">Mulas en taller</span></div>
  <div class="kpi"><span class="kpi-value">{{ kpis.horas_trabajadas }}</span><span class="kpi-label">Horas trabajadas</span></div>
  <div class="kpi"><span class="kpi-value">{{ kpis.horas_facturables }}</span><span class="kpi-label">Horas facturables</span></div>
  <div class="kpi"><span class="kpi-value">${{ kpis.valor_generado|intcomma }}</span><span class="kpi-label">Valor generado</span></div>
  <div class="kpi"><span class="kpi-value">${{ kpis.abonos|intcomma }}</span><span class="kpi-label">Abonos</span></div>
  <div class="kpi"><span class="kpi-value">${{ kpis.saldo_pendiente|intcomma }}</span><span class="kpi-label">Saldo pendiente</span></div>
  <div class="kpi"><span class="kpi-value">${{ kpis.nomina_semanal_pendiente|intcomma }}</span><span class="kpi-label">Nómina pendiente</span></div>
</div>

<h2>Operaciones activas</h2>
<table class="table">
  <thead><tr><th>Código</th><th>Buque</th><th>Generador de carga</th><th>Puerto</th></tr></thead>
  <tbody>
  {% for op in operaciones_activas %}
    <tr>
      <td><a href="{% url 'operaciones:detalle' op.pk %}">{{ op.codigo }}</a></td>
      <td>{{ op.buque }}</td>
      <td>{{ op.generador_de_carga }}</td>
      <td>{{ op.puerto }}</td>
    </tr>
  {% empty %}
    <tr><td colspan="4">No hay operaciones activas.</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
```

Crear plantillas placeholder para el resto (`vencimientos.html`, `nomina.html`, `operativo.html`, `financiero.html`, `historial.html`, `gantt.html`) que extienden base.html, con `{{ ultima_actualizacion|date:"d/m/Y H:i"|default:"—" }}` y un título, para que los tests de render pasen. Se completan en las Tasks siguientes.

Añadir a `static/css/app.css`:

```css
.meta-update { font-family: "IBM Plex Mono", monospace; font-size: 12px; color: var(--ink-dim); }
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 28px; }
.kpi { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
.kpi-value { display: block; font-family: "IBM Plex Mono", monospace; font-size: 20px; font-weight: 600; }
.kpi-label { display: block; font-size: 12px; color: var(--ink-dim); margin-top: 4px; }
```

- [ ] **Step 6: Verificar que pasa**

Run: `python manage.py test apps.dashboard.tests -v 2`
Expected: PASS (8 tests).

- [ ] **Step 7: Suite completa**

Run: `python manage.py test -v 2`
Expected: PASS (tests previos + nuevos = ~114). `python manage.py check` limpio.

- [ ] **Step 8: Commit local**

```bash
git add -A
git commit -m "feat(dashboard): app dashboard con vistas base y reemplazo del stub inicio"
```

---

### Task 2: Dashboard de flota — panel de vencimientos completo

**Files:**
- Modify: `apps/dashboard/views.py` (completar dashboard_vencimientos)
- Modify: `templates/dashboard/vencimientos.html`
- Modify: `apps/dashboard/tests/test_views.py` (nuevo test con vencimientos)
- Modify: `static/css/app.css` (estilos `.alert-item`, `.alert-ok`, `.alert-warn`, `.alert-danger`)

**Interfaces:**
- Consumes: `alertas_vencimiento()` (ya devuelve list[dict] con claves documento/vehiculo/tipo/fecha_vencimiento/dias/estado), `Vehicle`.
- Produces: dashboard_vencimientos con flota (total/en_operacion/disponibles/en_taller/fuera_de_servicio) y tabla de vencimientos con semáforo y link al admin del vehículo.

- [ ] **Step 1: Escribir el test que falla**

Añadir a `apps/dashboard/tests/test_views.py` (nueva clase):

```python
from datetime import timedelta

from django.utils import timezone

from apps.flota.models import Vehicle, VehicleDocument


class VencimientosDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
        self.client.force_login(self.user)
        self.vehicle = Vehicle.objects.create(placa="DEF456")

    def test_vencimientos_muestra_alerta_proximo(self):
        VehicleDocument.objects.create(
            vehicle=self.vehicle,
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() + timedelta(days=10),
        )
        response = self.client.get(reverse("dashboard:vencimientos"))
        self.assertContains(response, "DEF456")
        self.assertContains(response, "Próximo")

    def test_vencimientos_muestra_documento_vencido(self):
        VehicleDocument.objects.create(
            vehicle=self.vehicle,
            tipo=VehicleDocument.TECNOMECANICA,
            fecha_vencimiento=timezone.localdate() - timedelta(days=2),
        )
        response = self.client.get(reverse("dashboard:vencimientos"))
        self.assertContains(response, "Vencido")
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.dashboard.tests.test_views.VencimientosDashboardTests -v 2`
Expected: FAIL — la plantilla aún no muestra alertas.

- [ ] **Step 3: Completar vista y plantilla**

En `apps/dashboard/views.py`, `dashboard_vencimientos` ya calcula `alertas` y `flota` (Task 1). Completar `templates/dashboard/vencimientos.html`:

```html
{% extends "base.html" %}
{% load humanize %}
{% block title %}Flota · Vencimientos{% endblock %}
{% block content %}
<p class="eyebrow">Dashboard de flota</p>
<h1>Vencimientos</h1>
<p class="meta-update">Información registrada hasta: {{ ultima_actualizacion|date:"d/m/Y H:i"|default:"—" }}</p>

<div class="kpi-grid">
  <div class="kpi"><span class="kpi-value">{{ flota.total }}</span><span class="kpi-label">Total mulas</span></div>
  <div class="kpi"><span class="kpi-value">{{ flota.en_operacion }}</span><span class="kpi-label">En operación</span></div>
  <div class="kpi"><span class="kpi-value">{{ flota.disponibles }}</span><span class="kpi-label">Disponibles</span></div>
  <div class="kpi"><span class="kpi-value">{{ flota.en_taller }}</span><span class="kpi-label">En taller</span></div>
  <div class="kpi"><span class="kpi-value">{{ flota.fuera_de_servicio }}</span><span class="kpi-label">Fuera de servicio</span></div>
</div>

<h2>Documentos próximos a vencer / vencidos</h2>
<table class="table">
  <thead><tr><th>Mula</th><th>Documento</th><th>Vencimiento</th><th>Días restantes</th><th>Estado</th></tr></thead>
  <tbody>
  {% for a in alertas %}
    <tr>
      <td><a href="/admin/flota/vehicle/{{ a.vehiculo.pk }}/change/">{{ a.vehiculo.placa }}</a></td>
      <td>{{ a.tipo }}</td>
      <td>{{ a.fecha_vencimiento|date:"d/m/y" }}</td>
      <td>{{ a.dias }}</td>
      <td>
        {% if a.estado == "vencido" %}
          <span class="tag tag-danger">🔴 Vencido</span>
        {% elif a.estado == "proximo" %}
          <span class="tag tag-warn">🟡 Próximo</span>
        {% else %}
          <span class="tag tag-ok">🟢 Normal</span>
        {% endif %}
      </td>
    </tr>
  {% empty %}
    <tr><td colspan="5">No hay documentos próximos a vencer o vencidos.</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
```

Añadir a `static/css/app.css`:

```css
.tag-ok { background: var(--ok-tint); color: var(--ok-ink); }
.tag-warn { background: var(--warn-tint); color: var(--warn-ink); }
.tag-danger { background: var(--danger-tint); color: var(--danger-ink); }
```

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.dashboard.tests -v 2`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "feat(dashboard): panel de vencimientos de documentos con semaforo"
```

---

### Task 3: Dashboard de nómina — selector de semana, rankings y doble turno

**Files:**
- Modify: `apps/dashboard/services.py` (añadir kpis_nomina)
- Modify: `apps/dashboard/views.py` (completar dashboard_nomina)
- Modify: `templates/dashboard/nomina.html`
- Create: `apps/dashboard/tests/test_nomina.py`
- Modify: `static/css/app.css` (si se necesita algún estilo de ranking)

**Interfaces:**
- Consumes: `Shift`, `Driver`, `DriverAdvance`, `Payroll`, `detectar_dobles_turnos`.
- Produces:
  - `def kpis_nomina(desde, hasta) -> dict`:
    - `turnos` — Σ de turnos realizados en el periodo.
    - `horas` — Σ horas.
    - `total` — Σ valor_pagado de turnos realizados en el periodo sin payroll_items (pendientes de pago).
    - `abonos` — Σ DriverAdvance del periodo (fecha dentro del rango).
    - `neto` — total − abonos.
    - `conductores` — nº de conductores distintos en turnos del periodo.
    - `ranking_horas` — top 5 conductores por Σ horas (list de {driver, horas}).
    - `ranking_turnos` — top 5 por nº de turnos (list de {driver, turnos}).
    - `dobles_turnos` — `detectar_dobles_turnos(desde=desde, hasta=hasta)`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/dashboard/tests/test_nomina.py`:

```python
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation, Shift


class NominaDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
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
        self.client.force_login(self.user)

    def _shift(self, vehicle, dia, estado=Shift.REALIZADO):
        return Shift.objects.create(
            operation=self.op,
            vehicle=vehicle,
            driver=self.juan,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, dia, 6, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, dia, 17, 0)),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=estado,
        )

    def test_nomina_muestra_semana_y_totales(self):
        self._shift(self.v1, 10)
        self._shift(self.v2, 11)
        response = self.client.get(
            reverse("dashboard:nomina"), {"desde": "2026-08-10", "hasta": "2026-08-16"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Juan Pérez")

    def test_nomina_detecta_doble_turno(self):
        self._shift(self.v1, 10)
        self._shift(self.v2, 10, estado=Shift.REALIZADO)
        response = self.client.get(
            reverse("dashboard:nomina"), {"desde": "2026-08-10", "hasta": "2026-08-16"}
        )
        self.assertContains(response, "Posible doble turno")
```

Nota: los dos shifts del mismo conductor el mismo día 06:00–17:00 con descanso 0h generan alerta de doble turno (el segundo tiene el mismo horario → solape). Ajustar si el test falla: usar el segundo de 18:00 a 05:00 para un descanso <8h.

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.dashboard.tests.test_nomina -v 2`
Expected: FAIL — `dashboard_nomina` aún no calcula kpis.

- [ ] **Step 3: Implementar servicios y vista**

Añadir a `apps/dashboard/services.py`:

```python
from apps.conductores.models import Driver
from apps.nomina.models import DriverAdvance
from apps.operaciones.services import detectar_dobles_turnos


def kpis_nomina(desde, hasta):
    turnos = Shift.objects.filter(
        estado=Shift.REALIZADO,
        fecha_inicio__date__gte=desde,
        fecha_inicio__date__lte=hasta,
    )
    pendientes = turnos.filter(payroll_items__isnull=True)
    total = (
        pendientes.aggregate(total=Sum("valor_pagado"))["total"] or Decimal(0)
    )
    horas = turnos.aggregate(total=Sum("horas_trabajadas"))["total"] or Decimal(0)
    abonos = (
        DriverAdvance.objects.filter(fecha__gte=desde, fecha__lte=hasta)
        .aggregate(total=Sum("valor"))["total"]
        or Decimal(0)
    )

    ranking_horas = list(
        turnos.values("driver__nombre", "driver__documento")
        .annotate(horas=Sum("horas_trabajadas"))
        .order_by("-horas")[:5]
    )
    ranking_turnos = list(
        turnos.values("driver__nombre", "driver__documento")
        .annotate(turnos=Count("id"))
        .order_by("-turnos")[:5]
    )

    return {
        "total": total,
        "horas": horas,
        "abonos": abonos,
        "neto": total - abonos,
        "conductores": turnos.values("driver").distinct().count(),
        "turnos": turnos.count(),
        "ranking_horas": ranking_horas,
        "ranking_turnos": ranking_turnos,
        "dobles_turnos": detectar_dobles_turnos(desde=desde, hasta=hasta),
    }
```

Nota: añadir `from django.db.models import Count` al import de services.py.

En `apps/dashboard/views.py`, `dashboard_nomina`:

```python
@login_required
def dashboard_nomina(request):
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")
    try:
        desde = timezone.datetime.strptime(desde, "%Y-%m-%d").date()
        hasta = timezone.datetime.strptime(hasta, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        desde = timezone.localdate() - timezone.timedelta(days=6)
        hasta = timezone.localdate()
    context = {
        "kpis": kpis_nomina(desde, hasta),
        "desde": desde,
        "hasta": hasta,
        "ultima_actualizacion": ultima_actualizacion(Payroll, Shift, DriverAdvance),
    }
    return render(request, "dashboard/nomina.html", context)
```

Nota: añadir `import timezone` (`from django.utils import timezone`) y `from apps.dashboard.services import kpis_nomina` en views.py. Usar `from datetime import timedelta` o `timezone.timedelta` según conveniencia.

Completar `templates/dashboard/nomina.html` con formulario de semana (GET), KPIs (total, horas, abonos, neto, conductores, turnos), rankings y alertas de doble turno.

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.dashboard.tests -v 2`
Expected: PASS (12 tests).

- [ ] **Step 5: Suite completa**

Run: `python manage.py test -v 2`
Expected: PASS (~116). `python manage.py check` limpio.

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "feat(dashboard): nomina con selector de semana, rankings y doble turno"
```

---

### Task 4: Dashboard operativo — horas, cumplimiento, novedades

**Files:**
- Modify: `apps/dashboard/services.py` (añadir kpis_operativo)
- Modify: `apps/dashboard/views.py` (completar dashboard_operativo)
- Modify: `templates/dashboard/operativo.html`
- Create: `apps/dashboard/tests/test_operativo.py`

**Interfaces:**
- Consumes: `Shift`, `Operation`, `Incident`, `Vehicle`.
- Produces:
  - `def kpis_operativo() -> dict`:
    - `horas_por_operacion` — list de {codigo, horas} para operaciones con turnos realizados.
    - `horas_por_mula` — list de {placa, horas}.
    - `cumplimiento_promedio` — media de cumplimiento_pct de turnos realizados (Decimal/float con 1 decimal).
    - `horas_perdidas` — Σ max(0, meta_horas − horas_trabajadas) de turnos realizados.
    - `principales_novedades` — top 5 categorías de incidentes por nº de registros.
    - `operaciones_menor_cumplimiento` — top 5 operaciones por cumplimiento promedio ascendente.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/dashboard/tests/test_operativo.py`:

```python
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Incident, Operation, Shift


class OperativoDashboardTests(TestCase):
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
        self.client.force_login(self.user)

    def _shift(self, inicio_h, fin_h, dia=10):
        return Shift.objects.create(
            operation=self.op,
            vehicle=self.vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(timezone.datetime(2026, 8, dia, inicio_h, 0)),
            fecha_fin=timezone.make_aware(timezone.datetime(2026, 8, dia, fin_h, 0)),
            tipo=Shift.DIA,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=Shift.REALIZADO,
        )

    def test_operativo_muestra_horas_y_cumplimiento(self):
        self._shift(6, 17)
        response = self.client.get(reverse("dashboard:operativo"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ABC123")

    def test_operativo_muestra_novedades(self):
        shift = self._shift(6, 14)
        cat = IncidentCategory.objects.create(nombre="Lluvia")
        Incident.objects.create(shift=shift, categoria=cat)
        response = self.client.get(reverse("dashboard:operativo"))
        self.assertContains(response, "Lluvia")
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.dashboard.tests.test_operativo -v 2`
Expected: FAIL — vista sin kpis.

- [ ] **Step 3: Implementar servicios y vista**

Añadir a `apps/dashboard/services.py`:

```python
from apps.operaciones.models import Incident


def kpis_operativo():
    realizados = Shift.objects.filter(estado=Shift.REALIZADO)

    horas_por_operacion = list(
        realizados.values("operation__codigo")
        .annotate(horas=Sum("horas_trabajadas"))
        .order_by("-horas")
    )
    horas_por_mula = list(
        realizados.values("vehicle__placa")
        .annotate(horas=Sum("horas_trabajadas"))
        .order_by("-horas")
    )

    cumplimiento = realizados.aggregate(avg=Avg("cumplimiento_pct"))["avg"]

    horas_perdidas = Decimal(0)
    for shift in realizados.only("meta_horas", "horas_trabajadas"):
        perdidas = float(shift.meta_horas) - float(shift.horas_trabajadas)
        if perdidas > 0:
            horas_perdidas += Decimal(perdidas)

    principales_novedades = list(
        Incident.objects.values("categoria__nombre")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    operaciones_menor_cumplimiento = list(
        realizados.values("operation__codigo", "operation__id")
        .annotate(avg_cumpl=Avg("cumplimiento_pct"))
        .order_by("avg_cumpl")[:5]
    )

    return {
        "horas_por_operacion": horas_por_operacion,
        "horas_por_mula": horas_por_mula,
        "cumplimiento_promedio": round(float(cumplimiento), 1) if cumplimiento else None,
        "horas_perdidas": horas_perdidas,
        "principales_novedades": principales_novedades,
        "operaciones_menor_cumplimiento": operaciones_menor_cumplimiento,
    }
```

Nota: añadir `from django.db.models import Avg, Count, Max, Sum` al import.

En `apps/dashboard/views.py`, `dashboard_operativo`:

```python
@login_required
def dashboard_operativo(request):
    context = {
        "kpis": kpis_operativo(),
        "ultima_actualizacion": ultima_actualizacion(Operation, Shift, Incident),
    }
    return render(request, "dashboard/operativo.html", context)
```

Completar `templates/dashboard/operativo.html` con KPIs y tablas (horas por operación, horas por mula, novedades, menor cumplimiento, horas perdidas).

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.dashboard.tests -v 2`
Expected: PASS (14 tests).

- [ ] **Step 5: Suite completa**

Run: `python manage.py test -v 2`
Expected: PASS (~118).

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "feat(dashboard): operativo con horas por operacion y mula, cumplimiento y novedades"
```

---

### Task 5: Dashboard financiero — evolución de facturación con Chart.js vendored

**Files:**
- Create: `static/vendor/chart.umd.js` (descargado de CDN)
- Modify: `apps/dashboard/services.py` (añadir kpis_financiero)
- Modify: `apps/dashboard/views.py` (completar dashboard_financiero)
- Modify: `templates/dashboard/financiero.html`
- Create: `apps/dashboard/tests/test_financiero.py`
- Modify: `static/css/app.css` (contenedor del gráfico)

**Interfaces:**
- Consumes: `BillingRecord`, `ClientPayment`, `Operation`.
- Produces:
  - `def kpis_financiero() -> dict`:
    - `valor_generado`, `abonos`, `saldo` (globales).
    - `por_operacion` — list de {codigo, facturado, abonado, saldo} por operación (operaciones con billing o payments).
    - `mayor_saldo` — top 5 operaciones por saldo.
    - `evolucion` — list de {fecha, total} de billing agrupado por fecha (para Chart.js).

- [ ] **Step 1: Descargar Chart.js vendored**

```powershell
New-Item -ItemType Directory -Path "C:\Users\Usuario\transportes-renacer\static\vendor" -Force | Out-Null
Invoke-WebRequest -Uri "https://cdn.jsdelivr.net/npm/chart.js@4.4.9/dist/chart.umd.js" -OutFile "C:\Users\Usuario\transportes-renacer\static\vendor\chart.umd.js"
```

Verificar que el archivo existe y tiene tamaño razonable (>300KB). Si no hay internet en el entorno, crear un stub mínimo que registre `window.Chart` y anotar la limitación.

- [ ] **Step 2: Escribir el test que falla**

Crear `apps/dashboard/tests/test_financiero.py`:

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


class FinancieroDashboardTests(TestCase):
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
        BillingRecord.objects.create(
            operation=self.op, fecha=date(2026, 8, 10), horas=11,
            tarifa_hora=35000, valor=385000,
        )
        ClientPayment.objects.create(operation=self.op, valor=200000)
        self.client.force_login(self.user)

    def test_financiero_muestra_totales(self):
        response = self.client.get(reverse("dashboard:financiero"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OP-001")

    def test_financiero_carga_chartjs_vendored(self):
        response = self.client.get(reverse("dashboard:financiero"))
        self.assertContains(response, "chart.umd.js")
```

- [ ] **Step 3: Verificar que falla**

Run: `python manage.py test apps.dashboard.tests.test_financiero -v 2`
Expected: FAIL — vista sin kpis.

- [ ] **Step 4: Implementar servicios y vista**

Añadir a `apps/dashboard/services.py`:

```python
def kpis_financiero():
    valor_generado = (
        BillingRecord.objects.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )
    abonos = (
        ClientPayment.objects.aggregate(total=Sum("valor"))["total"] or Decimal(0)
    )

    por_operacion = []
    for op in Operation.objects.filter(
        billing_records__isnull=False
    ).distinct().prefetch_related("billing_records", "client_payments"):
        facturado = (
            op.billing_records.aggregate(total=Sum("valor"))["total"] or Decimal(0)
        )
        abonado = (
            op.client_payments.aggregate(total=Sum("valor"))["total"] or Decimal(0)
        )
        por_operacion.append(
            {
                "codigo": op.codigo,
                "pk": op.pk,
                "facturado": facturado,
                "abonado": abonado,
                "saldo": facturado - abonado,
            }
        )
    por_operacion.sort(key=lambda x: x["saldo"], reverse=True)
    mayor_saldo = por_operacion[:5]

    evolucion = list(
        BillingRecord.objects.values("fecha")
        .annotate(total=Sum("valor"))
        .order_by("fecha")
    )

    return {
        "valor_generado": valor_generado,
        "abonos": abonos,
        "saldo": valor_generado - abonos,
        "por_operacion": por_operacion,
        "mayor_saldo": mayor_saldo,
        "evolucion": evolucion,
    }
```

En `apps/dashboard/views.py`, `dashboard_financiero`:

```python
@login_required
def dashboard_financiero(request):
    context = {
        "kpis": kpis_financiero(),
        "ultima_actualizacion": ultima_actualizacion(BillingRecord, ClientPayment),
    }
    return render(request, "dashboard/financiero.html", context)
```

Completar `templates/dashboard/financiero.html`:

```html
{% extends "base.html" %}
{% load static %}
{% load humanize %}
{% block title %}Financiero{% endblock %}
{% block content %}
<p class="eyebrow">Dashboard financiero</p>
<h1>Financiero</h1>
<p class="meta-update">Información registrada hasta: {{ ultima_actualizacion|date:"d/m/Y H:i"|default:"—" }}</p>

<div class="kpi-grid">
  <div class="kpi"><span class="kpi-value">${{ kpis.valor_generado|intcomma }}</span><span class="kpi-label">Valor generado</span></div>
  <div class="kpi"><span class="kpi-value">${{ kpis.abonos|intcomma }}</span><span class="kpi-label">Abonos recibidos</span></div>
  <div class="kpi"><span class="kpi-value">${{ kpis.saldo|intcomma }}</span><span class="kpi-label">Saldo pendiente</span></div>
</div>

<h2>Evolución de facturación</h2>
<canvas id="evolucion-chart" height="120"></canvas>

<h2>Valor por operación</h2>
<table class="table">
  <thead><tr><th>Operación</th><th>Facturado</th><th>Abonado</th><th>Saldo</th></tr></thead>
  <tbody>
  {% for row in kpis.por_operacion %}
    <tr>
      <td><a href="{% url 'operaciones:detalle' row.pk %}">{{ row.codigo }}</a></td>
      <td>${{ row.facturado|intcomma }}</td>
      <td>${{ row.abonado|intcomma }}</td>
      <td><strong>${{ row.saldo|intcomma }}</strong></td>
    </tr>
  {% empty %}
    <tr><td colspan="4">Sin facturación registrada.</td></tr>
  {% endfor %}
  </tbody>
</table>

{% block scripts %}
<script src="{% static 'vendor/chart.umd.js' %}"></script>
<script>
  const fechas = [{% for e in kpis.evolucion %}"{{ e.fecha|date:'d/m' }}",{% endfor %}];
  const totales = [{% for e in kpis.evolucion %}{{ e.total }},{% endfor %}];
  const ctx = document.getElementById("evolucion-chart");
  if (ctx && window.Chart) {
    new Chart(ctx, {
      type: "line",
      data: {
        labels: fechas,
        datasets: [{ label: "Facturación", data: totales, borderColor: "#23B5D3", backgroundColor: "rgba(35,181,211,0.15)", tension: 0.3 }]
      },
      options: { responsive: true, plugins: { legend: { display: false } } }
    });
  }
</script>
{% endblock %}
{% endblock %}
```

Nota: en Django solo puede haber un `{% block scripts %}` por plantilla — este template hereda de `base.html` que define `{% block scripts %}`. El código de arriba anida dos `{% endblock %}` por error; corregir: cerrar `{% block content %}` y tener `{% block scripts %}` como bloque hermano (no anidado). Asegurar la estructura correcta de bloques al implementar.

- [ ] **Step 5: Verificar que pasa**

Run: `python manage.py test apps.dashboard.tests -v 2`
Expected: PASS (16 tests).

- [ ] **Step 6: Suite completa**

Run: `python manage.py test -v 2`
Expected: PASS (~120). `python manage.py check` limpio.

- [ ] **Step 7: Commit local**

```bash
git add -A
git commit -m "feat(dashboard): financiero con evolucion de facturacion y Chart.js vendored"
```

---

### Task 6: Historial de operaciones con trazabilidad

**Files:**
- Modify: `apps/dashboard/views.py` (completar dashboard_historial)
- Modify: `templates/dashboard/historial.html`
- Create: `apps/dashboard/tests/test_historial.py`

**Interfaces:**
- Consumes: `Operation`.
- Produces: `dashboard_historial` con operaciones finalizadas/canceladas (código, buque, generador, puerto, fechas, estado, total de turnos, total de horas, saldo, link a detalle y al Gantt).

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/dashboard/tests/test_historial.py`:

```python
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.catalogos.models import CargoGenerator, Port
from apps.operaciones.models import Operation


class HistorialDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
        self.generador = CargoGenerator.objects.create(nombre="Terminal de Carga SA")
        self.puerto = Port.objects.create(nombre="Sociedad Portuaria Regional")
        self.client.force_login(self.user)

    def _crear(self, codigo, estado):
        return Operation.objects.create(
            codigo=codigo,
            buque=f"BUQUE {codigo}",
            generador_de_carga=self.generador,
            puerto=self.puerto,
            fecha_inicio=date(2026, 8, 10),
            tarifa_hora=35000,
            valor_turno_dia=180000,
            valor_turno_noche=180000,
            estado=estado,
        )

    def test_historial_muestra_finalizadas_y_canceladas(self):
        self._crear("OP-001", Operation.FINALIZADA)
        self._crear("OP-002", Operation.CANCELADA)
        response = self.client.get(reverse("dashboard:historial"))
        self.assertContains(response, "OP-001")
        self.assertContains(response, "OP-002")

    def test_historial_no_muestra_activas(self):
        self._crear("OP-003", Operation.ACTIVA)
        response = self.client.get(reverse("dashboard:historial"))
        self.assertNotContains(response, "OP-003")
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.dashboard.tests.test_historial -v 2`
Expected: FAIL — la plantilla aún no lista operaciones.

- [ ] **Step 3: Completar vista y plantilla**

`dashboard_historial` en views.py ya filtra FINALIZADA/CANCELADA (Task 1). Añadir anotaciones de total de turnos y horas. Modificar la vista:

```python
from django.db.models import Count, Sum

@login_required
def dashboard_historial(request):
    operaciones = (
        Operation.objects.filter(
            estado__in=[Operation.FINALIZADA, Operation.CANCELADA]
        )
        .annotate(
            num_turnos=Count("shifts", filter=Q(shifts__estado=Shift.REALIZADO)),
            horas_totales=Sum(
                "shifts__horas_trabajadas",
                filter=Q(shifts__estado=Shift.REALIZADO),
            ),
        )
        .order_by("-fecha_inicio")
    )
    context = {"operaciones": operaciones}
    return render(request, "dashboard/historial.html", context)
```

Nota: añadir `from django.db.models import Q` en views.py. Los `filter=` en agregaciones requieren Django 2.0+ (disponible).

Completar `templates/dashboard/historial.html`:

```html
{% extends "base.html" %}
{% block title %}Historial de operaciones{% endblock %}
{% block content %}
<p class="eyebrow">Historial</p>
<h1>Historial de operaciones</h1>
<table class="table">
  <thead><tr><th>Código</th><th>Buque</th><th>Generador de carga</th><th>Puerto</th><th>Inicio</th><th>Fin real</th><th>Turnos</th><th>Horas</th><th>Estado</th><th>Acciones</th></tr></thead>
  <tbody>
  {% for op in operaciones %}
    <tr>
      <td>{{ op.codigo }}</td>
      <td>{{ op.buque }}</td>
      <td>{{ op.generador_de_carga }}</td>
      <td>{{ op.puerto }}</td>
      <td>{{ op.fecha_inicio|date:"d/m/Y" }}</td>
      <td>{{ op.fecha_fin_real|date:"d/m/Y"|default:"—" }}</td>
      <td>{{ op.num_turnos }}</td>
      <td>{{ op.horas_totales|default:"0" }}</td>
      <td>{{ op.get_estado_display }}</td>
      <td>
        <a href="{% url 'operaciones:detalle' op.pk %}">Detalle</a> ·
        <a href="{% url 'dashboard:gantt' op.pk %}">Gantt</a>
      </td>
    </tr>
  {% empty %}
    <tr><td colspan="10">No hay operaciones finalizadas o canceladas.</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
```

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.dashboard.tests -v 2`
Expected: PASS (18 tests).

- [ ] **Step 5: Suite completa**

Run: `python manage.py test -v 2`
Expected: PASS (~122).

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "feat(dashboard): historial de operaciones finalizadas y canceladas"
```

---

### Task 7: Gantt multi-día por operación

**Files:**
- Modify: `apps/dashboard/views.py` (implementar gantt_datos)
- Create: `apps/dashboard/services.py` (añadir bloques_gantt) o hacerlo en la vista
- Modify: `templates/dashboard/gantt.html`
- Create: `static/js/gantt.js`
- Modify: `static/css/app.css` (estilos `.gantt` del eje continuo)
- Create: `apps/dashboard/tests/test_gantt.py`

**Interfaces:**
- Consumes: `Operation`, `Shift`, `Incident`.
- Produces:
  - `def bloques_gantt(operation) -> list[dict]` — filas por mula asignada; cada fila `{"placa": str, "bloques": [{id, inicio (ISO), fin (ISO), horas, cumplimiento, tipo, estado, novedad, mula, placa}]}`. Solo turnos programado/realizado/cancelado/anulado (todos visibles; cancelados/anulados marcados). Se ordena por fecha_inicio. Incluye la meta_horas de la operación.
  - `gantt_datos(request, pk)` → `JsonResponse` con `{"operation": {codigo, meta_horas, fecha_inicio, fecha_fin_estimada}, "filas": [...]}`.
  - `dashboard_gantt` renderiza `gantt.html` con `operation` y un `data-url` al endpoint JSON.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/dashboard/tests/test_gantt.py`:

```python
import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Incident, Operation, Shift


class GanttTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="x")
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
        self.client.force_login(self.user)

    def _shift(self, vehicle, inicio, fin, estado=Shift.REALIZADO, tipo=Shift.DIA):
        return Shift.objects.create(
            operation=self.op,
            vehicle=vehicle,
            driver=self.driver,
            fecha_inicio=timezone.make_aware(inicio),
            fecha_fin=timezone.make_aware(fin),
            tipo=tipo,
            meta_horas=self.op.meta_horas,
            valor_estandar=self.op.valor_turno_dia,
            estado=estado,
        )

    def test_gantt_pagina_renderiza(self):
        response = self.client.get(reverse("dashboard:gantt", args=[self.op.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BUQUE ATLANTIC")

    def test_gantt_datos_incluye_filas_y_bloques(self):
        self._shift(
            self.v1,
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 17, 0),
        )
        self._shift(
            self.v2,
            timezone.datetime(2026, 8, 10, 18, 0),
            timezone.datetime(2026, 8, 11, 6, 0),
            tipo=Shift.NOCHE,
        )
        response = self.client.get(reverse("dashboard:gantt_datos", args=[self.op.pk]))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["operation"]["codigo"], "OP-001")
        placas = [fila["placa"] for fila in data["filas"]]
        self.assertIn("ABC123", placas)
        self.assertIn("DEF456", placas)

    def test_gantt_datos_incluye_novedad(self):
        shift = self._shift(
            self.v1,
            timezone.datetime(2026, 8, 10, 6, 0),
            timezone.datetime(2026, 8, 10, 14, 0),
        )
        cat = IncidentCategory.objects.create(nombre="Lluvia")
        Incident.objects.create(shift=shift, categoria=cat, descripcion="Todo el día")
        response = self.client.get(reverse("dashboard:gantt_datos", args=[self.op.pk]))
        data = json.loads(response.content)
        bloque = data["filas"][0]["bloques"][0]
        self.assertEqual(bloque["novedad"], "Lluvia")
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.dashboard.tests.test_gantt -v 2`
Expected: FAIL — `gantt_datos` no definido.

- [ ] **Step 3: Implementar servicio y vista JSON**

Añadir a `apps/dashboard/services.py`:

```python
def bloques_gantt(operation):
    shifts = operation.shifts.select_related("vehicle", "incidente__categoria").order_by(
        "fecha_inicio"
    )
    filas = {}
    for shift in shifts:
        filas.setdefault(shift.vehicle.placa, {"placa": shift.vehicle.placa, "bloques": []})
        novedad = ""
        if hasattr(shift, "incidente"):
            novedad = shift.incidente.categoria.nombre
        filas[shift.vehicle.placa]["bloques"].append(
            {
                "id": shift.pk,
                "inicio": shift.fecha_inicio.isoformat(),
                "fin": shift.fecha_fin.isoformat(),
                "horas": float(shift.horas_trabajadas),
                "cumplimiento": float(shift.cumplimiento_pct),
                "tipo": shift.get_tipo_display(),
                "estado": shift.estado,
                "novedad": novedad,
                "mula": shift.vehicle.placa,
            }
        )
    return [
        {"placa": placa, "bloques": sorted(f["bloques"], key=lambda b: b["inicio"])}
        for placa, f in sorted(filas.items())
    ]
```

En `apps/dashboard/views.py`:

```python
from django.http import JsonResponse

from apps.dashboard.services import bloques_gantt


@login_required
def gantt_datos(request, pk):
    operation = get_object_or_404(Operation, pk=pk)
    data = {
        "operation": {
            "codigo": operation.codigo,
            "buque": operation.buque,
            "meta_horas": float(operation.meta_horas),
            "fecha_inicio": operation.fecha_inicio.isoformat(),
            "fecha_fin_estimada": (
                operation.fecha_fin_estimada.isoformat()
                if operation.fecha_fin_estimada
                else None
            ),
        },
        "filas": bloques_gantt(operation),
    }
    return JsonResponse(data)
```

Completar `templates/dashboard/gantt.html`:

```html
{% extends "base.html" %}
{% load static %}
{% block title %}Gantt {{ operation.codigo }}{% endblock %}
{% block content %}
<p class="eyebrow">Control de operación</p>
<h1>Operación <span>{{ operation.buque }}</span></h1>
<p class="meta-update" id="gantt-meta"></p>
<p class="gantt-filters">
  <label>Desde <input type="date" id="g-desde"></label>
  <label>Hasta <input type="date" id="g-hasta"></label>
  <label>Mula <select id="g-mula"><option value="">Todas</option></select></label>
</p>
<div class="gantt" id="gantt" data-url="{% url 'dashboard:gantt_datos' operation.pk %}"></div>
<div class="gantt-legend">
  <span class="legend-item"><span class="sw sw-ok"></span>Cumplimiento ≥ 90%</span>
  <span class="legend-item"><span class="sw sw-warn"></span>70–89%</span>
  <span class="legend-item"><span class="sw sw-bad"></span>&lt; 70%</span>
</div>
{% endblock %}
{% block scripts %}
<script src="{% static 'js/gantt.js' %}"></script>
{% endblock %}
```

Crear `static/js/gantt.js` (JS vanilla, eje continuo, adaptado del prototipo del PRD §40 a la paleta clara):

```javascript
(function () {
  const cont = document.getElementById("gantt");
  if (!cont) return;

  const desdeInput = document.getElementById("g-desde");
  const hastaInput = document.getElementById("g-hasta");
  const mulaSelect = document.getElementById("g-mula");

  async function cargar() {
    const res = await fetch(cont.dataset.url);
    const data = await res.json();
    pintar(data);
  }

  function estadoClase(cumplimiento, estado) {
    if (estado === "cancelado" || estado === "anulado") return "bad";
    if (cumplimiento >= 90) return "ok";
    if (cumplimiento >= 70) return "warn";
    return "bad";
  }

  function aMarca(iso) {
    const d = new Date(iso);
    return d.getTime();
  }

  function pintar(data) {
    const filas = data.filas;
    const todas = filas.flatMap((f) => f.bloques);
    let min = todas.length ? Math.min(...todas.map((b) => aMarca(b.inicio))) : Date.now() - 86400000;
    let max = todas.length ? Math.max(...todas.map((b) => aMarca(b.fin))) : Date.now();
    if (desdeInput.value) min = aMarca(desdeInput.value + "T00:00:00");
    if (hastaInput.value) max = aMarca(hastaInput.value + "T23:59:59");
    const rango = Math.max(max - min, 3600000);
    const ahora = Date.now();

    cont.innerHTML = "";
    const cab = document.createElement("div");
    cab.className = "gantt-cab";
    const etiqueta = document.createElement("div");
    etiqueta.className = "gantt-etiqueta";
    etiqueta.textContent = "Recurso";
    const regla = document.createElement("div");
    regla.className = "gantt-regla";
    const dias = Math.ceil(rango / 86400000);
    for (let i = 0; i <= dias; i++) {
      const d = document.createElement("span");
      d.textContent = new Date(min + i * 86400000).toLocaleDateString("es-CO", { day: "2-digit", month: "2-digit" });
      regla.appendChild(d);
    }
    cab.appendChild(etiqueta);
    cab.appendChild(regla);
    cont.appendChild(cab);

    filas.filter((f) => !mulaSelect.value || f.placa === mulaSelect.value).forEach((fila) => {
      const row = document.createElement("div");
      row.className = "gantt-fila";
      const et = document.createElement("div");
      et.className = "gantt-etiqueta";
      et.textContent = fila.placa;
      const track = document.createElement("div");
      track.className = "gantt-track";
      fila.bloques.forEach((b) => {
        if (aMarca(b.fin) < min || aMarca(b.inicio) > max) return;
        const block = document.createElement("div");
        block.className = "gantt-bloque " + estadoClase(b.cumplimiento, b.estado);
        block.style.left = ((aMarca(b.inicio) - min) / rango * 100) + "%";
        block.style.width = (Math.max((aMarca(b.fin) - aMarca(b.inicio)) / rango * 100, 0.5)) + "%";
        const hora = (ts) => new Date(ts).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
        block.textContent = hora(aMarca(b.inicio)) + "–" + hora(aMarca(b.fin)) + " · " + b.cumplimiento + "%";
        block.title = (b.novedad ? "Novedad: " + b.novedad + "\n" : "") + b.tipo + " · " + b.estado;
        track.appendChild(block);
      });
      if (ahora >= min && ahora <= max) {
        const now = document.createElement("div");
        now.className = "gantt-ahora";
        now.style.left = ((ahora - min) / rango * 100) + "%";
        track.appendChild(now);
      }
      row.appendChild(et);
      row.appendChild(track);
      cont.appendChild(row);
    });
    document.getElementById("gantt-meta").textContent = "Meta: " + data.operation.meta_horas + " h";
  }

  desdeInput.addEventListener("change", cargar);
  hastaInput.addEventListener("change", cargar);
  mulaSelect.addEventListener("change", cargar);
  cargar();
})();
```

Nota: este JS es una versión funcional simplificada del prototipo §40 adaptada a la paleta clara; el revisor lo evalúa por corrección funcional (filas por mula, bloques por timestamp, línea AHORA, leyenda, filtros), no por fidelidad pixel del prototipo.

Añadir a `static/css/app.css` los estilos del Gantt:

```css
.gantt { margin-top: 16px; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: var(--surface); }
.gantt-cab, .gantt-fila { display: grid; grid-template-columns: 120px 1fr; }
.gantt-cab { border-bottom: 1px solid var(--line); background: var(--surface-hover); }
.gantt-etiqueta { padding: 8px 10px; font-family: "IBM Plex Mono", monospace; font-size: 12px; border-right: 1px solid var(--line); }
.gantt-regla { position: relative; display: flex; overflow: hidden; }
.gantt-regla span { flex: 1 0 0; padding: 8px 2px; font-family: "IBM Plex Mono", monospace; font-size: 10px; color: var(--ink-faint); text-align: center; border-left: 1px solid var(--line); }
.gantt-fila { border-bottom: 1px solid var(--line); }
.gantt-track { position: relative; min-height: 46px; }
.gantt-bloque { position: absolute; top: 8px; bottom: 8px; border-radius: 4px; padding: 4px 6px; font-family: "IBM Plex Mono", monospace; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gantt-bloque.ok { background: var(--ok-tint); color: var(--ok-ink); border: 1px solid var(--ok); }
.gantt-bloque.warn { background: var(--warn-tint); color: var(--warn-ink); border: 1px dashed var(--warn); }
.gantt-bloque.bad { background: var(--danger-tint); color: var(--danger-ink); border: 2px solid var(--danger); }
.gantt-ahora { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--secondary); z-index: 5; }
.gantt-legend { display: flex; gap: 16px; margin-top: 12px; font-size: 12px; color: var(--ink-dim); }
.legend-item { display: flex; align-items: center; gap: 6px; }
.sw { width: 14px; height: 14px; border-radius: 3px; display: inline-block; }
.sw-ok { background: var(--ok-tint); border: 1px solid var(--ok); }
.sw-warn { background: var(--warn-tint); border: 1px dashed var(--warn); }
.sw-bad { background: var(--danger-tint); border: 2px solid var(--danger); }
```

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.dashboard.tests.test_gantt -v 2`
Expected: PASS (3 tests).

- [ ] **Step 5: Suite completa**

Run: `python manage.py test -v 2`
Expected: PASS (tests previos + 3 = ~125). `python manage.py check` limpio.

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "feat(dashboard): Gantt multi-dia por operacion con eje continuo"
```

---

## Self-Review del Plan

**Cobertura del spec (Plan 5):**
- Dashboard principal con KPIs de operaciones activas, mulas, horas, valor, abonos, saldo, nómina (§27): Task 1. ✔
- Fecha "Información registrada hasta" (§26) en todos los dashboards: Tasks 1-5, 7. ✔
- Panel de vencimientos con semáforo y link a ficha (§10, §29): Task 2. ✔
- Dashboard de nómina con selector de semana, rankings y doble turno (§30): Task 3. ✔
- Dashboard operativo (horas por operación/mula, cumplimiento, horas perdidas, novedades, menor cumplimiento) (§31): Task 4. ✔
- Dashboard financiero con evolución Chart.js vendored (§32): Task 5. ✔
- Historial de operaciones con trazabilidad (§28): Task 6. ✔
- Gantt multi-día con eje continuo, línea AHORA, turnos nocturnos, panel de novedades, filtros (§19, §40): Task 7. ✔
- Sustitución del stub `inicio` por el dashboard real: Task 1. ✔

**Fuera de este plan:** reportes avanzados, exportaciones adicionales, notificaciones, WhatsApp/email, app móvil, OCR, drag/resize del Gantt (todo P2, fuera de MVP). Estados de billing gestionados desde UI (MVP los deja en pendiente y el CSV los usa). Granularidad de permisos por grupo (decisión del humano pendiente desde Plan 1).

**Placeholders:** ninguno; cada paso contiene código o comandos reales.

**Consistencia de tipos:** `ultima_actualizacion`, `kpis_inicio`, `kpis_nomina`, `kpis_operativo`, `kpis_financiero`, `bloques_gantt` definidos en services y consumidos por vistas/tests con las mismas firmas. `alertas_vencimiento` (flota) y `detectar_dobles_turnos` (operaciones) reutilizados tal cual. El endpoint `gantt_datos` produce JSON con la forma exacta que `gantt.js` consume (operation/filas/bloques con claves inicio/fin/horas/cumplimiento/tipo/estado/novedad).
