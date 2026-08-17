# Fase 0 — Shell + Inicio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rediseñar el shell de navegación (sidebar + topbar + footer) con el sistema de diseño nuevo y rediseñar el dashboard de inicio, creando listas mínimas de Flota y Conductores para que la sidebar no tenga enlaces muertos.

**Architecture:** CSS puro con variables (`base.css`) cargado después de `app.css` para transición sin romper. `base.html` reescrito con sidebar+topbar+footer y URLs reales corregidas. `inicio.html` con datos reales de `kpis_inicio()` y `alertas_vencimiento()`. Listas mínimas nuevas en apps `flota` y `conductores`.

**Tech Stack:** Django 5.2, CSS puro, Material Symbols, Google Fonts (Inter + Courier Prime).

## Global Constraints

- No usar Tailwind ni frameworks CSS; solo CSS puro con variables.
- No tocar git (proyecto local sin repo).
- `base.css` debe cargarse DESPUÉS de `app.css` en `base.html`.
- URLs reales: `dashboard:inicio`, `operaciones:lista`, `nomina:lista`, `documentos:panel`, `dashboard:financiero` (para Facturación).
- Turnos y Configuración aún no tienen URL: sus ítems en sidebar van `disabled` hasta sus fases.
- Sidebar y navegación solo para `user.is_authenticated`.

---

### Task 1: Sistema de diseño nuevo — `static/css/base.css`

**Files:**
- Create: `static/css/base.css`

**Interfaces:**
- Consumes: tokens de color de la paleta (navy `#0A2A4A`, naranja `#FF5A1F`, semánticos).
- Produces: clases `.sidebar`, `.brand-btn`, `.nav-link`, `.sub-nav`, `.topbar`, `.btn-primary`, `.card`, `.kpi-grid`, `.kpi-card`, `.kpi-label`, `.kpi-value`, `.data-table`, `.badge`, `.badge-ok/warn/danger`, `.nav-link.disabled`, footer, login.

- [ ] **Step 1: Escribir el archivo**

Contenido completo (tokens + sidebar + topbar + cards + tabla + badges + footer + responsive + `.nav-link.disabled` y `.login-wrap`):

```css
/* base.css — sistema de diseño nuevo (se carga DESPUÉS de app.css) */
:root {
  --nav-bg: #0A2A4A;
  --accent: #FF5A1F;
  --accent-hover: #E64A15;
  --surface: #F4F7F6;
  --border: #E2E8F0;
  --text-main: #1E293B;
  --text-muted: #64748B;
  --ok: #10B981; --ok-bg: rgba(16,185,129,0.1);
  --warn: #F59E0B; --warn-bg: rgba(245,158,11,0.1);
  --danger: #EF4444; --danger-bg: rgba(239,68,68,0.1);
  --font-sans: 'Inter', -apple-system, 'Segoe UI', sans-serif;
  --font-mono: 'Courier Prime', Menlo, Consolas, monospace;
}
body { font-family: var(--font-sans); background: var(--surface); color: var(--text-main); margin: 0; display: flex; height: 100vh; overflow: hidden; }

/* Sidebar */
.sidebar { width: 260px; background: var(--nav-bg); color: #fff; display: flex; flex-direction: column; flex-shrink: 0; box-shadow: 2px 0 8px rgba(0,0,0,0.1); z-index: 20; }
.sidebar-header { padding: 24px; border-bottom: 1px solid rgba(255,255,255,0.1); }
.brand-btn { display: block; font-weight: 700; font-size: 1.125rem; color: #fff; text-decoration: none; letter-spacing: 0.05em; }
.brand-btn:hover { color: var(--accent); }
.nav-container { flex: 1; overflow-y: auto; padding: 16px 0; }
.nav-link { display: flex; align-items: center; gap: 12px; padding: 12px 24px; color: rgba(255,255,255,0.8); text-decoration: none; font-weight: 500; transition: all .2s ease; }
.nav-link:hover { background: rgba(255,255,255,0.05); color: #fff; }
.nav-link.active { background: rgba(255,255,255,0.1); color: #fff; border-left: 4px solid var(--accent); }
.nav-link.disabled { opacity: 0.4; cursor: not-allowed; pointer-events: none; }
.nav-link .material-symbols-outlined { font-size: 20px; }
.sub-nav { background: rgba(0,0,0,0.15); padding: 8px 0; display: flex; flex-direction: column; }
.sub-nav-link { padding: 8px 24px 8px 60px; color: rgba(255,255,255,0.6); text-decoration: none; font-size: .875rem; transition: color .2s ease; }
.sub-nav-link:hover { color: #fff; }
.sub-nav-link.active { color: #fff; font-weight: 600; }
.sidebar-footer { padding: 16px 24px; border-top: 1px solid rgba(255,255,255,0.1); display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.2); }
.user-info { font-size: .875rem; color: rgba(255,255,255,0.9); }
.logout-btn { background: none; border: 1px solid rgba(255,255,255,0.3); color: rgba(255,255,255,0.8); padding: 4px 12px; border-radius: 4px; font-size: .75rem; cursor: pointer; transition: all .2s ease; }
.logout-btn:hover { background: rgba(255,255,255,0.1); color: #fff; border-color: #fff; }

/* Main wrapper / topbar */
.main-wrapper { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.topbar { height: 64px; background: #fff; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; padding: 0 32px; flex-shrink: 0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); position: sticky; top: 0; z-index: 10; }
.page-title { font-size: 1.25rem; font-weight: 600; }
.topbar-actions { display: flex; align-items: center; gap: 16px; }
.search-box { position: relative; }
.search-box .material-symbols-outlined { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--text-muted); font-size: 18px; }
.search-input { background: var(--surface); border: 1px solid var(--border); padding: 8px 12px 8px 36px; border-radius: 6px; font-size: .875rem; width: 250px; transition: border-color .2s; }
.search-input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 2px rgba(255,90,31,0.1); }
.btn-primary { background: var(--accent); color: #fff; border: none; border-radius: 6px; padding: 8px 16px; font-size: .875rem; font-weight: 500; cursor: pointer; transition: background-color .2s; box-shadow: 0 2px 4px rgba(255,90,31,0.2); }
.btn-primary:hover { background: var(--accent-hover); }
.action-icon { color: var(--text-muted); cursor: pointer; transition: color .2s; padding: 4px; border-radius: 4px; position: relative; }
.action-icon:hover { color: var(--text-main); background: var(--surface); }
.action-icon .badge-dot { position: absolute; top: 2px; right: 2px; width: 8px; height: 8px; border-radius: 50%; background: var(--danger); border: 1.5px solid #fff; }

/* Main content */
main { flex: 1; padding: 32px; overflow-y: auto; }
.card { background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: 1px solid var(--border); }
.card-title { margin: 0 0 20px; font-size: 1.125rem; font-weight: 600; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; margin-bottom: 32px; }
@media (max-width: 900px) { .kpi-grid { grid-template-columns: repeat(2, 1fr); } }
.kpi-card { border-left: 4px solid var(--nav-bg); display: flex; flex-direction: column; justify-content: center; }
.kpi-card.warn { border-left-color: var(--warn); }
.kpi-card.ok { border-left-color: var(--ok); }
.kpi-label { font-size: .75rem; font-weight: 600; color: var(--text-muted); margin-bottom: 8px; letter-spacing: .05em; text-transform: uppercase; }
.kpi-value { font-size: 2rem; font-weight: 700; font-family: var(--font-mono); line-height: 1.2; }
.kpi-value.warn { color: var(--warn); }
.kpi-value.ok { color: var(--ok); }
.kpi-value.danger { color: var(--danger); }

/* Tabla */
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { text-align: left; padding: 12px 16px; font-size: .75rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: .05em; border-bottom: 1px solid var(--border); background: #F8FAFC; }
.data-table td { padding: 16px; border-bottom: 1px solid var(--border); font-size: .875rem; vertical-align: middle; }
.data-table tbody tr:hover { background: #F8FAFC; }
.data-table tbody tr:last-child td { border-bottom: none; }
.data-table .mono { font-family: var(--font-mono); color: var(--text-muted); }
.data-table .empty-row td { text-align: center; color: var(--text-muted); padding: 32px 16px; }

/* Badges */
.badge { display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 9999px; font-size: .75rem; font-weight: 600; letter-spacing: .025em; }
.badge-ok { background: var(--ok-bg); color: var(--ok); }
.badge-warn { background: var(--warn-bg); color: var(--warn); }
.badge-danger { background: var(--danger-bg); color: var(--danger); }

/* Login (anonimo) */
.login-wrap { display: flex; justify-content: center; align-items: center; height: 100%; }
.login-card { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 28px; width: 360px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }

footer { padding: 16px 32px; background: #fff; border-top: 1px solid var(--border); font-size: .75rem; color: var(--text-muted); text-align: center; flex-shrink: 0; }

/* Alertas */
.alerta-list { display: flex; flex-direction: column; gap: 8px; }
.alerta-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px; font-size: .875rem; background: #fff; }
.alerta-item.vencido { border-color: var(--danger); background: var(--danger-bg); }
.alerta-item.proximo { border-color: var(--warn); background: var(--warn-bg); }
```

- [ ] **Step 2: Verificar archivo creado**

Run: `Get-ChildItem static\css\base.css`
Expected: archivo existe.

- [ ] **Step 3: No commit (proyecto local sin git)**

---

### Task 2: Shell — reescribir `templates/base.html`

**Files:**
- Modify: `templates/base.html`

**Interfaces:**
- Consumes: clases de `base.css` (Task 1), URLs reales, `alertas_count` del context processor.
- Produces: bloques `{% block title %}`, `{% block page_title %}`, `{% block topbar_action %}`, `{% block content %}`, `{% block scripts %}`. Sidebar para autenticados.

- [ ] **Step 1: Escribir el archivo**

```html
{% load static %}
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Transportes Renacer{% endblock %}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&family=Inter:wght@400;500;600;700&display=swap">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0">
  <link rel="stylesheet" href="{% static 'css/tokens.css' %}">
  <link rel="stylesheet" href="{% static 'css/app.css' %}">
  <link rel="stylesheet" href="{% static 'css/base.css' %}">
  {% block extra_head %}{% endblock %}
</head>
<body>
{% if user.is_authenticated %}
<aside class="sidebar">
  <div class="sidebar-header">
    <a class="brand-btn" href="{% url 'dashboard:inicio' %}">TRANSPORTES RENACER</a>
  </div>
  <nav class="nav-container">
    <a class="nav-link {% if request.resolver_match.app_name == 'dashboard' %}active{% endif %}"
       href="{% url 'dashboard:inicio' %}">
      <span class="material-symbols-outlined">dashboard</span> Inicio
    </a>
    {% if request.resolver_match.app_name == 'dashboard' %}
    <div class="sub-nav">
      <a class="sub-nav-link" href="{% url 'dashboard:vencimientos' %}">Vencimientos</a>
      <a class="sub-nav-link" href="{% url 'dashboard:nomina' %}">Nómina</a>
      <a class="sub-nav-link" href="{% url 'dashboard:operativo' %}">Operativo</a>
      <a class="sub-nav-link" href="{% url 'dashboard:financiero' %}">Financiero</a>
      <a class="sub-nav-link" href="{% url 'dashboard:historial' %}">Historial</a>
    </div>
    {% endif %}
    <a class="nav-link {% if request.resolver_match.app_name == 'operaciones' %}active{% endif %}"
       href="{% url 'operaciones:lista' %}">
      <span class="material-symbols-outlined">conveyor_belt</span> Operaciones
    </a>
    <a class="nav-link disabled" href="#">
      <span class="material-symbols-outlined">schedule</span> Turnos
    </a>
    <a class="nav-link {% if request.resolver_match.app_name == 'flota' %}active{% endif %}"
       href="{% url 'flota:lista' %}">
      <span class="material-symbols-outlined">local_shipping</span> Flota
    </a>
    <a class="nav-link {% if request.resolver_match.app_name == 'conductores' %}active{% endif %}"
       href="{% url 'conductores:lista' %}">
      <span class="material-symbols-outlined">badge</span> Conductores
    </a>
    <div class="sub-nav"></div>
    <a class="nav-link {% if request.resolver_match.app_name == 'nomina' %}active{% endif %}"
       href="{% url 'nomina:lista' %}">
      <span class="material-symbols-outlined">payments</span> Nómina
    </a>
    <a class="nav-link {% if request.resolver_match.app_name == 'dashboard' and request.resolver_match.url_name == 'financiero' %}active{% endif %}"
       href="{% url 'dashboard:financiero' %}">
      <span class="material-symbols-outlined">receipt_long</span> Facturación
    </a>
    <a class="nav-link {% if request.resolver_match.app_name == 'documentos' %}active{% endif %}"
       href="{% url 'documentos:panel' %}">
      <span class="material-symbols-outlined">folder_shared</span> Documentos
    </a>
    <a class="nav-link disabled" href="#">
      <span class="material-symbols-outlined">settings</span> Configuración
    </a>
  </nav>
  <div class="sidebar-footer">
    <div class="user-info"><strong>{{ request.user.get_full_name|default:request.user.username }}</strong></div>
    <form action="{% url 'logout' %}" method="post" style="margin:0;">
      {% csrf_token %}
      <button class="logout-btn" type="submit">Salir</button>
    </form>
  </div>
</aside>
{% endif %}

<div class="main-wrapper">
  {% if user.is_authenticated %}
  <header class="topbar">
    <div class="page-title">{% block page_title %}Transportes Renacer{% endblock %}</div>
    <div class="topbar-actions">
      <div class="search-box">
        <span class="material-symbols-outlined">search</span>
        <input class="search-input" type="text" placeholder="Buscar...">
      </div>
      {% block topbar_action %}
      <a class="btn-primary" href="{% url 'operaciones:nuevo' %}">+ Nueva Operación</a>
      {% endblock %}
      <span class="action-icon">
        <span class="material-symbols-outlined">notifications</span>
        {% if alertas_count %}<span class="badge-dot"></span>{% endif %}
      </span>
    </div>
  </header>
  {% endif %}
  <main>
    {% block content %}{% endblock %}
  </main>
  {% if user.is_authenticated %}
  <footer>
    &copy; {% now "Y" %} Transportes Renacer — Sistema de Gestión Portuaria. Barranquilla, Colombia.
  </footer>
  {% endif %}
</div>
{% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Verificar que las URLs referenciadas existen**

Run: `python manage.py shell -c "from django.urls import reverse; print(reverse('dashboard:inicio'), reverse('operaciones:lista'), reverse('nomina:lista'), reverse('documentos:panel'), reverse('dashboard:financiero'), reverse('operaciones:nuevo'))"`
Expected: imprime las 6 rutas sin NoReverseMatch.

- [ ] **Step 3: No commit (proyecto local sin git)**

---

### Task 3: Listas mínimas de Flota y Conductores

**Files:**
- Create: `apps/flota/views.py`
- Create: `apps/flota/urls.py`
- Create: `templates/flota/list.html`
- Create: `apps/conductores/views.py`
- Create: `apps/conductores/urls.py`
- Create: `templates/conductores/list.html`
- Modify: `config/urls.py`

**Interfaces:**
- Consumes: `Vehicle`, `Driver` modelos.
- Produces: URL `flota:lista` y `conductores:lista` (consumidas por Task 2).

- [ ] **Step 1: Escribir `apps/flota/views.py`**

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.flota.models import Vehicle


@login_required
def flota_lista(request):
    vehiculos = Vehicle.objects.all().order_by("placa")
    estados = {c[0]: c[1] for c in Vehicle.ESTADOS}
    resumen = {
        "total": vehiculos.count(),
        "en_operacion": vehiculos.filter(estado=Vehicle.EN_OPERACION).count(),
        "disponibles": vehiculos.filter(estado=Vehicle.DISPONIBLE).count(),
        "en_taller": vehiculos.filter(estado=Vehicle.EN_TALLER).count(),
        "fuera_de_servicio": vehiculos.filter(estado=Vehicle.FUERA_DE_SERVICIO).count(),
    }
    return render(
        request,
        "flota/list.html",
        {"vehiculos": vehiculos, "estados": estados, "resumen": resumen},
    )
```

- [ ] **Step 2: Escribir `apps/flota/urls.py`**

```python
from django.urls import path

from apps.flota import views

app_name = "flota"

urlpatterns = [
    path("", views.flota_lista, name="lista"),
]
```

- [ ] **Step 3: Escribir `templates/flota/list.html`**

```html
{% extends "base.html" %}
{% block title %}Flota{% endblock %}
{% block page_title %}Flota{% endblock %}
{% block content %}
<div class="kpi-grid">
  <div class="card kpi-card"><div class="kpi-label">Total mulas</div><div class="kpi-value">{{ resumen.total }}</div></div>
  <div class="card kpi-card ok"><div class="kpi-label">En operación</div><div class="kpi-value ok">{{ resumen.en_operacion }}</div></div>
  <div class="card kpi-card"><div class="kpi-label">Disponibles</div><div class="kpi-value">{{ resumen.disponibles }}</div></div>
  <div class="card kpi-card warn"><div class="kpi-label">En taller</div><div class="kpi-value warn">{{ resumen.en_taller }}</div></div>
</div>
<div class="card">
  <h3 class="card-title">Vehículos</h3>
  <table class="data-table">
    <thead><tr><th>Placa</th><th>Marca</th><th>Modelo</th><th>Año</th><th>Estado</th></tr></thead>
    <tbody>
    {% for v in vehiculos %}
      <tr>
        <td class="mono"><strong>{{ v.placa }}</strong></td>
        <td>{{ v.marca }}</td>
        <td>{{ v.modelo }}</td>
        <td class="mono">{{ v.anio|default:"—" }}</td>
        <td>
          {% if v.estado == "disponible" %}<span class="badge badge-ok">{{ estados|dictsort:""|get_item:v.estado|default:v.estado }}</span>
          {% elif v.estado == "en_operacion" %}<span class="badge badge-ok">{{ v.get_estado_display }}</span>
          {% elif v.estado == "en_taller" %}<span class="badge badge-warn">{{ v.get_estado_display }}</span>
          {% else %}<span class="badge badge-danger">{{ v.get_estado_display }}</span>{% endif %}
        </td>
      </tr>
    {% empty %}
      <tr class="empty-row"><td colspan="5">No hay vehículos registrados.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

(Nota: `estados` se pasa pero se usa `v.get_estado_display` — mantener simple. Eliminar la variable `estados` si no se usa para evitar complejidad; se simplifica en Step 4.)

- [ ] **Step 4: Simplificar template (usar solo get_estado_display)**

Reescribir la celda de estado con:

```html
        <td>
          {% if v.estado == "disponible" %}<span class="badge badge-ok">{{ v.get_estado_display }}</span>
          {% elif v.estado == "en_operacion" %}<span class="badge badge-ok">{{ v.get_estado_display }}</span>
          {% elif v.estado == "en_taller" %}<span class="badge badge-warn">{{ v.get_estado_display }}</span>
          {% else %}<span class="badge badge-danger">{{ v.get_estado_display }}</span>{% endif %}
        </td>
```

Y en el view quitar `estados` del contexto.

- [ ] **Step 5: Escribir `apps/conductores/views.py`**

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.conductores.models import Driver


@login_required
def conductores_lista(request):
    conductores = Driver.objects.all().order_by("nombre")
    return render(request, "conductores/list.html", {"conductores": conductores})
```

- [ ] **Step 6: Escribir `apps/conductores/urls.py`**

```python
from django.urls import path

from apps.conductores import views

app_name = "conductores"

urlpatterns = [
    path("", views.conductores_lista, name="lista"),
]
```

- [ ] **Step 7: Escribir `templates/conductores/list.html`**

```html
{% extends "base.html" %}
{% block title %}Conductores{% endblock %}
{% block page_title %}Conductores{% endblock %}
{% block content %}
<div class="card">
  <h3 class="card-title">Conductores</h3>
  <table class="data-table">
    <thead><tr><th>Nombre</th><th>Documento</th><th>Teléfono</th><th>Estado</th></tr></thead>
    <tbody>
    {% for c in conductores %}
      <tr>
        <td><strong>{{ c.nombre }}</strong></td>
        <td class="mono">{{ c.documento }}</td>
        <td class="mono">{{ c.telefono|default:"—" }}</td>
        <td>
          {% if c.estado == "inactivo" %}<span class="badge badge-danger">{{ c.get_estado_display }}</span>
          {% elif c.estado == "trabajando" %}<span class="badge badge-ok">{{ c.get_estado_display }}</span>
          {% else %}<span class="badge badge-ok">{{ c.get_estado_display }}</span>{% endif %}
        </td>
      </tr>
    {% empty %}
      <tr class="empty-row"><td colspan="4">No hay conductores registrados.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 8: Modificar `config/urls.py`**

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("apps.dashboard.urls")),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("operaciones/", include("apps.operaciones.urls")),
    path("nomina/", include("apps.nomina.urls")),
    path("facturacion/", include("apps.facturacion.urls")),
    path("documentos/", include("apps.documentos.urls")),
    path("flota/", include("apps.flota.urls")),
    path("conductores/", include("apps.conductores.urls")),
]
```

- [ ] **Step 9: Verificar rutas**

Run: `python manage.py shell -c "from django.urls import reverse; print(reverse('flota:lista'), reverse('conductores:lista'))"`
Expected: imprime `/flota/` y `/conductores/`.

---

### Task 4: Context processor de notificaciones

**Files:**
- Create: `apps/core/context_processors.py`
- Modify: `config/settings/base.py`

**Interfaces:**
- Produces: `alertas_count` disponible en todos los templates (consumida por Task 2).

- [ ] **Step 1: Escribir `apps/core/context_processors.py`**

```python
from apps.flota.services import alertas_vencimiento


def notificaciones(request):
    if not request.user.is_authenticated:
        return {"alertas_count": 0}
    return {"alertas_count": len(alertas_vencimiento())}
```

- [ ] **Step 2: Registrar en `config/settings/base.py` (TEMPLATES context_processors)**

Agregar `"apps.core.context_processors.notificaciones"` a la lista de context_processors.

- [ ] **Step 3: Verificar con shell**

Run: `python manage.py shell -c "from apps.core import context_processors; print(context_processors.notificaciones(None))"`
Expected: imprime `{'alertas_count': 0}` o similar (para None puede fallar; si falla, probar con request autenticado en test). Simplificar: si `request` es None retorna `{"alertas_count": 0}`.

Ajuste defensivo en Step 4:

```python
def notificaciones(request):
    if request is None or not request.user.is_authenticated:
        return {"alertas_count": 0}
    return {"alertas_count": len(alertas_vencimiento())}
```

---

### Task 5: Dashboard de inicio — `inicio.html` + view

**Files:**
- Modify: `templates/dashboard/inicio.html`
- Modify: `apps/dashboard/views.py`

**Interfaces:**
- Consumes: `kpis` (dict de `kpis_inicio()`), `operaciones_activas` (queryset), `ultima_actualizacion`, `alertas` (de `alertas_vencimiento()`).
- Produces: página de inicio rediseñada con KPIs, operaciones activas y alertas.

- [ ] **Step 1: Modificar `apps/dashboard/views.py` (dashboard_inicio)**

Agregar import de alertas y pasar `alertas`:

```python
from apps.flota.services import alertas_vencimiento
```

Y en `dashboard_inicio`:

```python
    context = {
        "kpis": kpis_inicio(),
        "operaciones_activas": Operation.objects.filter(estado=Operation.ACTIVA),
        "alertas": alertas_vencimiento(),
        "ultima_actualizacion": ultima_actualizacion(
            Operation, Shift, BillingRecord, ClientPayment, Payroll
        ),
    }
```

- [ ] **Step 2: Escribir `templates/dashboard/inicio.html`**

```html
{% extends "base.html" %}
{% load humanize %}
{% block title %}Panel de control{% endblock %}
{% block page_title %}Panel de control{% endblock %}
{% block content %}
<p class="meta-update">Información registrada hasta: {{ ultima_actualizacion|date:"d/m/Y H:i"|default:"—" }}</p>

<div class="kpi-grid">
  <div class="card kpi-card"><div class="kpi-label">Operaciones activas</div><div class="kpi-value">{{ kpis.operaciones_activas }}</div></div>
  <div class="card kpi-card"><div class="kpi-label">Mulas en operación</div><div class="kpi-value">{{ kpis.mulas_en_operacion }}</div></div>
  <div class="card kpi-card"><div class="kpi-label">Mulas disponibles</div><div class="kpi-value">{{ kpis.mulas_disponibles }}</div></div>
  <div class="card kpi-card warn"><div class="kpi-label">En taller</div><div class="kpi-value warn">{{ kpis.mulas_en_taller }}</div></div>
  <div class="card kpi-card"><div class="kpi-label">Horas trabajadas</div><div class="kpi-value">{{ kpis.horas_trabajadas|floatformat:0 }} h</div></div>
  <div class="card kpi-card"><div class="kpi-label">Horas facturables</div><div class="kpi-value">{{ kpis.horas_facturables|floatformat:0 }} h</div></div>
  <div class="card kpi-card"><div class="kpi-label">Valor generado</div><div class="kpi-value">${{ kpis.valor_generado|intcomma }}</div></div>
  <div class="card kpi-card"><div class="kpi-label">Saldo pendiente</div><div class="kpi-value">${{ kpis.saldo_pendiente|intcomma }}</div></div>
  <div class="card kpi-card ok"><div class="kpi-label">Nómina pendiente</div><div class="kpi-value ok">${{ kpis.nomina_semanal_pendiente|intcomma }}</div></div>
</div>

<div class="card">
  <h3 class="card-title">Operaciones activas</h3>
  <table class="data-table">
    <thead><tr><th>Código</th><th>Buque</th><th>Generador de carga</th><th>Puerto</th><th>Horas</th><th>Estado</th></tr></thead>
    <tbody>
    {% for op in operaciones_activas %}
      <tr>
        <td><a href="{% url 'operaciones:detalle' op.pk %}"><strong>{{ op.codigo }}</strong></a></td>
        <td>{{ op.buque }}</td>
        <td>{{ op.generador_de_carga }}</td>
        <td>{{ op.puerto }}</td>
        <td class="mono">{{ op.total_horas }} / {{ op.meta_horas }} h</td>
        <td><span class="badge badge-ok">{{ op.get_estado_display }}</span></td>
      </tr>
    {% empty %}
      <tr class="empty-row"><td colspan="6">No hay operaciones activas.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>

<div class="card" style="margin-top:24px;">
  <h3 class="card-title">Alertas de vencimiento</h3>
  <div class="alerta-list">
    {% for a in alertas %}
      <div class="alerta-item {% if a.estado == 'vencido' %}vencido{% else %}proximo{% endif %}">
        <span>{% if a.estado == 'vencido' %}🔴{% else %}🟡{% endif %}</span>
        <span><strong>{{ a.vehiculo.placa }}</strong> — {{ a.tipo }}: {{ a.fecha_vencimiento|date:"d/m/Y" }} ({{ a.dias }} días)</span>
      </div>
    {% empty %}
      <p style="margin:0; color:var(--text-muted); font-size:.875rem;">Sin alertas de vencimiento.</p>
    {% endfor %}
  </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Verificar que la página carga**

Run: `python manage.py check`
Expected: sin errores.

---

### Task 6: Verificación final

- [ ] **Step 1: Levantar servidor y probar**

Run: `python manage.py runserver 127.0.0.1:8000 --noreload` (en segundo plano) y consultar:
- `GET /` con sesión de admin → 200.
- `GET /flota/` → 200.
- `GET /conductores/` → 200.
- `GET /accounts/login/` → 200 (sin sidebar).

- [ ] **Step 2: Revisar visualmente** en navegador.
