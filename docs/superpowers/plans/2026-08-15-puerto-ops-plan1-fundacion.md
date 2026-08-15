# Plan 1 â€” FundaciÃ³n del sistema de operaciones portuarias

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear el proyecto Django de Transportes Renacer con configuraciÃ³n por entorno, base visual (tokens CSS + template base), app `core` (mixins de auditorÃ­a y grupos de permisos), catÃ¡logos (clientes, puertos, categorÃ­as de novedades), conductores y flota con control de vencimientos (SOAT / tÃ©cnico-mecÃ¡nica) y panel de alertas.

**Architecture:** Django 5.2 LTS monolÃ­tico con apps por dominio (`core`, `catalogos`, `conductores`, `flota`). ConfiguraciÃ³n separada por entorno (`base` / `dev` / `prod`) leÃ­da desde variables de entorno. Base visual propia con CSS puro + variables (patrÃ³n del prototipo Gantt) sin ninguna librerÃ­a de build. Pruebas con el test runner nativo de Django.

**Tech Stack:** Python 3.13, Django 5.2 LTS, django-simple-history, whitenoise, gunicorn, dj-database-url, python-dotenv, psycopg[binary], HTMX (por CDN en el template base).

**Spec de referencia:** `docs/superpowers/specs/2026-08-15-puerto-ops-design.md`

## Global Constraints

- Zona horaria: `America/Bogota`. Lenguaje de interfaz: espaÃ±ol.
- Moneda: pesos colombianos (COP), enteros en pantalla; campos `DecimalField(max_digits=14, decimal_places=0)`.
- No Node.js, no Tailwind, no build step. Todo el CSS es puro con variables.
- Todas las tablas de negocio llevan `created_at`, `updated_at`, `created_by`, `updated_by` (via mixins de `core`).
- Auditabilidad con `django-simple-history` (clase `HistoricalRecords`).
- `DEBUG`/`DATABASE_URL`/`SECRET_KEY` vienen de variables de entorno; nunca hardcodear secretos.
- Estados de vehÃ­culos: `disponible | en_operacion | en_taller | fuera_de_servicio`.
- Estados de conductores: `disponible | trabajando | inactivo`.
- Grupos Django: `Admin`, `Secretaria`, `Gerencia`.
- Fecha lÃ­mite de alerta de vencimiento: 30 dÃ­as (constante `ALERT_DAYS = 30` en `apps.flota.services`).
- Formato de cÃ³digo: PEP 8; sin comentarios salvo docstrings de mÃ³dulo/funciÃ³n cuando aporten.
- Git SOLO LOCAL (sin remoto). Cada task termina con tests en verde y un commit local.

---

### Task 1: Scaffolding del proyecto Django

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `config/__init__.py`
- Create: `config/settings/__init__.py`
- Create: `config/settings/base.py`
- Create: `config/settings/dev.py`
- Create: `config/settings/prod.py`
- Create: `config/urls.py`
- Create: `config/wsgi.py`
- Create: `config/asgi.py`
- Create: `manage.py`
- Modify: `.gitignore` (ya existe)

**Interfaces:**
- Consumes: nada.
- Produces: proyecto Django arrancable. `DJANGO_SETTINGS_MODULE=config.settings.dev` corre en dev; `config.settings.prod` en producciÃ³n. Este es el esqueleto que usan todas las tareas siguientes.

- [ ] **Step 1: Escribir requirements y entorno**

Crear `requirements.txt`:

```
Django==5.2.12
django-simple-history==3.8.0
gunicorn==23.0.0
whitenoise==6.9.0
dj-database-url==2.3.0
python-dotenv==1.1.0
psycopg[binary]==3.2.9
```

Crear `.env.example`:

```
DJANGO_SETTINGS_MODULE=config.settings.dev
SECRET_KEY=change-me
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=127.0.0.1,localhost
```

- [ ] **Step 2: Crear la estructura de settings**

Crear `config/settings/base.py`:

```python
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-dev-key")
DEBUG = os.environ.get("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "simple_history",
    "apps.core",
    "apps.catalogos",
    "apps.conductores",
    "apps.flota",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(default="sqlite:///db.sqlite3")
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard:inicio"
LOGOUT_REDIRECT_URL = "login"
```

Nota: aÃ±adir `import dj_database_url` en `base.py` (ver `requirements.txt`).

Crear `config/settings/__init__.py`:

```python
# Settings por entorno: usa config.settings.dev o config.settings.prod via DJANGO_SETTINGS_MODULE.
```

Crear `config/settings/dev.py`:

```python
from .base import *  # noqa: F401,F403
```

Crear `config/settings/prod.py`:

```python
from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")  # noqa: F405
SECRET_KEY = os.environ["SECRET_KEY"]  # noqa: F405
```

Crear `config/urls.py`:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
]
```

- [ ] **Step 3: Crear manage.py y paquetes de apps**

Crear `manage.py`:

```python
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

Crear `config/wsgi.py` y `config/asgi.py` (usar las plantillas estÃ¡ndar de Django; `wsgi.py` con `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")` para producciÃ³n).

Crear los paquetes de apps con su `__init__.py` y `apps.py` vacÃ­os (se completan en sus tareas):
- `apps/__init__.py`
- `apps/core/__init__.py`
- `apps/catalogos/__init__.py`
- `apps/conductores/__init__.py`
- `apps/flota/__init__.py`

- [ ] **Step 4: Verificar que el proyecto arranca**

Crear entorno virtual e instalar dependencias:

```bash
cd C:\Users\Usuario\transportes-renacer
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Ejecutar las comprobaciones del sistema:

```bash
python manage.py check
python manage.py migrate
```

Expected: `check` devuelve "System check identified no issues". `migrate` aplica las migraciones base de Django sin errores (SQLite dev).

- [ ] **Step 5: Commit local**

```bash
git add -A
git commit -m "chore: scaffolding del proyecto Django con settings por entorno"
```

---

### Task 2: App core â€” mixins de auditorÃ­a y grupos de permisos

**Files:**
- Create: `apps/core/__init__.py` (ya creado, no modificar)
- Create: `apps/core/apps.py`
- Create: `apps/core/models.py`
- Create: `apps/core/management/__init__.py`
- Create: `apps/core/management/commands/__init__.py`
- Create: `apps/core/management/commands/setup_groups.py`
- Create: `apps/core/tests/__init__.py`
- Create: `apps/core/tests/test_models.py`
- Create: `apps/core/tests/test_commands.py`

**Interfaces:**
- Consumes: el esqueleto de la Task 1.
- Produces:
  - `class TimeStampedModel(models.Model)` â€” campos `created_at`, `updated_at`.
  - `class UserStampedModel(TimeStampedModel)` â€” aÃ±ade `created_by`, `updated_by` (FK a `auth.User`, null=True, on_delete=SET_NULL, related_name `+`).
  - `class AuditMixin(models.Model)` â€” alias de `UserStampedModel` con `HistoricalRecords()`. Todos los modelos de negocio heredan de `AuditMixin`.
  - Comando `python manage.py setup_groups` â€” crea/actualiza los grupos `Admin`, `Secretaria`, `Gerencia`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/core/tests/test_models.py`:

```python
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import AuditMixin, TimeStampedModel


class StampModel(AuditMixin):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "core"


class TimeStampedModelTests(TestCase):
    def test_stamps_are_set_on_creation(self):
        obj = StampModel.objects.create(name="x")
        self.assertIsNotNone(obj.created_at)
        self.assertIsNotNone(obj.updated_at)

    def test_updated_at_changes_on_update(self):
        obj = StampModel.objects.create(name="x")
        original = obj.updated_at
        obj.name = "y"
        obj.save()
        obj.refresh_from_db()
        self.assertGreater(obj.updated_at, original)


class AuditMixinTests(TestCase):
    def test_user_stamps_are_recorded(self):
        user = get_user_model().objects.create_user(username="ana")
        obj = StampModel.objects.create(name="x", created_by=user, updated_by=user)
        self.assertEqual(obj.created_by, user)
        self.assertEqual(obj.updated_by, user)
```

Nota: el test necesita `from django.db import models` al inicio del archivo.

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.core.tests -v 2`
Expected: FAIL con `ModuleNotFoundError: apps.core.models` o `StampModel` indefinido.

- [ ] **Step 3: ImplementaciÃ³n mÃ­nima**

Crear `apps/core/apps.py`:

```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
```

Crear `apps/core/models.py`:

```python
from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserStampedModel(TimeStampedModel):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True


class AuditMixin(UserStampedModel):
    history = HistoricalRecords(inherit=True)

    class Meta:
        abstract = True
```

Nota: los modelos concretos heredarÃ¡n de `AuditMixin`. El test `StampModel` extiende `AuditMixin` con `app_label = "core"`.

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.core.tests -v 2`
Expected: PASS (2 tests).

- [ ] **Step 5: Escribir test del comando de grupos**

Crear `apps/core/tests/test_commands.py`:

```python
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase


class SetupGroupsTests(TestCase):
    def test_groups_are_created(self):
        call_command("setup_groups")
        names = set(Group.objects.values_list("name", flat=True))
        self.assertEqual(names, {"Admin", "Secretaria", "Gerencia"})

    def test_command_is_idempotent(self):
        call_command("setup_groups")
        call_command("setup_groups")
        self.assertEqual(Group.objects.count(), 3)
```

- [ ] **Step 6: Verificar que falla**

Run: `python manage.py test apps.core.tests.test_commands -v 2`
Expected: FAIL con `CommandError: No command 'setup_groups'`.

- [ ] **Step 7: Implementar el comando**

Crear `apps/core/management/commands/setup_groups.py`:

```python
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

GROUPS = {
    "Admin": {"__all__"},
    "Secretaria": {"__all__"},
    "Gerencia": {"view_all"},
}


class Command(BaseCommand):
    help = "Crea o actualiza los grupos de usuarios del sistema."

    def handle(self, *args, **options):
        for name, perms in GROUPS.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.set(Permission.objects.all())
            self.stdout.write(self.style.SUCCESS(f"Grupo '{name}' listo"))
```

- [ ] **Step 8: Verificar que pasa**

Run: `python manage.py test apps.core.tests -v 2`
Expected: PASS (5 tests).

- [ ] **Step 9: Commit local**

```bash
git add -A
git commit -m "feat(core): mixins de auditoria y comando setup_groups"
```

---

### Task 3: Base visual â€” tokens CSS, template base y login

**Files:**
- Create: `static/css/tokens.css`
- Create: `static/css/app.css`
- Create: `templates/base.html`
- Create: `templates/registration/login.html`
- Create: `apps/core/tests/test_templates.py`

**Interfaces:**
- Consumes: Task 1 (settings con `STATICFILES_DIRS`, `templates/`, `LOGIN_URL`).
- Produces:
  - CSS con las variables de diseÃ±o (secciÃ³n 3 del spec) disponibles como `static/css/tokens.css` cargado por `base.html`.
  - `base.html` con navbar, zona de usuario, bloques `{% block content %}` y `{% block scripts %}`.
  - Plantilla de login en `templates/registration/login.html`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/core/tests/test_templates.py`:

```python
from django.test import SimpleTestCase
from django.urls import reverse


class TemplateTests(SimpleTestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Iniciar sesiÃ³n")

    def test_base_template_has_css_tokens(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "tokens.css")
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.core.tests.test_templates -v 2`
Expected: FAIL â€” no existe la URL `login`.

- [ ] **Step 3: Configurar URLs de auth y crear plantillas**

En `config/urls.py`, aÃ±adir:

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
]
```

Crear `templates/registration/login.html`:

```html
{% extends "base.html" %}
{% block title %}Iniciar sesiÃ³n{% endblock %}
{% block content %}
<div class="login-wrap">
  <div class="login-card">
    <p class="eyebrow">Transportes Renacer</p>
    <h1>Iniciar sesiÃ³n</h1>
    <form method="post">
      {% csrf_token %}
      {{ form.as_p }}
      <button type="submit" class="btn btn-primary">Entrar</button>
    </form>
    {% if form.errors %}
      <p class="form-error">Usuario o contraseÃ±a incorrectos.</p>
    {% endif %}
  </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Crear los tokens CSS**

Crear `static/css/tokens.css` (paleta definitiva del spec, secciÃ³n 3):

```css
:root {
  --primary:       #0A2A4A;
  --primary-dark:  #071E35;
  --primary-ink:   #FFFFFF;

  --secondary:       #FF5A1F;
  --secondary-hover: #E64A14;
  --secondary-ink:   #FFFFFF;

  --ok:         #1E9E5A;  --ok-tint:  #E3F5EC;  --ok-ink:  #0E5C37;
  --warn:       #B45309;  --warn-tint:#FFF1D6;  --warn-ink:#7A4507;
  --danger:     #D92D20;  --danger-tint:#FDE9E9;--danger-ink:#8F1D13;

  --surface:       #FFFFFF;
  --surface-base:  #F8F9FA;
  --surface-hover: #EEF1F4;
  --line:          #D5DCE3;
  --ink:           #16212B;
  --ink-dim:       #5A6B7B;
  --ink-faint:     #8A97A5;
}
```

- [ ] **Step 5: Crear el template base y CSS de app**

Crear `templates/base.html`:

```html
{% load static %}
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Transportes Renacer{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/tokens.css' %}">
  <link rel="stylesheet" href="{% static 'css/app.css' %}">
  <script src="https://unpkg.com/htmx.org@1.9.12" defer></script>
</head>
<body>
  <header class="topbar">
    <div class="topbar-brand">Transportes Renacer</div>
    <nav class="topbar-nav">
      {% if user.is_authenticated %}
        <span class="topbar-user">{{ user.get_full_name|default:user.username }}</span>
        <form method="post" action="{% url 'logout' %}">
          {% csrf_token %}
          <button type="submit" class="btn-link">Salir</button>
        </form>
      {% endif %}
    </nav>
  </header>
  <main class="main">
    {% block content %}{% endblock %}
  </main>
  {% block scripts %}{% endblock %}
</body>
</html>
```

Crear `static/css/app.css` (estilos base mÃ­nimos y reutilizables):

```css
* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--surface-base);
  color: var(--ink);
  font-family: "IBM Plex Sans", -apple-system, "Segoe UI", sans-serif;
}

.eyebrow {
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin: 0 0 6px;
}

h1 { font-size: 24px; font-weight: 600; margin: 0 0 20px; }

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--primary);
  color: var(--primary-ink);
  padding: 12px 24px;
}
.topbar-brand { font-weight: 600; font-size: 16px; }
.topbar-nav { display: flex; gap: 16px; align-items: center; }
.btn-link {
  background: none; border: none; color: var(--primary-ink);
  text-decoration: underline; cursor: pointer; font-size: 14px;
}

.main { max-width: 1180px; margin: 0 auto; padding: 32px 24px 80px; }

.btn {
  border: none; border-radius: 6px; padding: 9px 16px;
  font-size: 14px; cursor: pointer; font-weight: 600;
}
.btn-primary { background: var(--secondary); color: var(--secondary-ink); }
.btn-primary:hover { background: var(--secondary-hover); }

.login-wrap { display: flex; justify-content: center; padding-top: 60px; }
.login-card {
  background: var(--surface); border: 1px solid var(--line);
  border-radius: 8px; padding: 28px; width: 360px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}
.login-card form p { display: flex; flex-direction: column; gap: 4px; margin-bottom: 14px; }
.login-card input {
  padding: 8px 10px; border: 1px solid var(--line); border-radius: 6px;
  font-size: 14px;
}
.form-error { color: var(--danger-ink); font-size: 13px; margin-top: 12px; }

@media (max-width: 720px) {
  .main { padding: 20px 14px 60px; }
}
```

- [ ] **Step 6: Verificar que pasa**

Run: `python manage.py test apps.core.tests -v 2`
Expected: PASS (7 tests) y la pÃ¡gina de login renderiza con el CSS.

- [ ] **Step 7: Commit local**

```bash
git add -A
git commit -m "feat(core): base visual con tokens CSS, template base y login"
```

---

### Task 4: App catalogos â€” clientes, puertos y categorÃ­as de novedades

**Files:**
- Create: `apps/catalogos/apps.py`
- Create: `apps/catalogos/models.py`
- Create: `apps/catalogos/admin.py`
- Create: `apps/catalogos/tests/__init__.py`
- Create: `apps/catalogos/tests/test_models.py`

**Interfaces:**
- Consumes: `apps.core.models.AuditMixin` (Task 2).
- Produces:
  - `class Client(AuditMixin)` â€” nombre, nit, contacto, telefono.
  - `class Port(AuditMixin)` â€” nombre, ciudad.
  - `class IncidentCategory(AuditMixin)` â€” nombre (unique), activa.
  - `__str__` de cada uno retorna el campo legible (nombre/placa).

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/catalogos/tests/test_models.py`:

```python
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.catalogos.models import Client, IncidentCategory, Port


class CatalogModelsTests(TestCase):
    def test_client_creation(self):
        client = Client.objects.create(
            nombre="Puerto de Barranquilla", nit="901000000-0"
        )
        self.assertEqual(str(client), "Puerto de Barranquilla")

    def test_port_creation(self):
        port = Port.objects.create(nombre="Sociedad Portuaria Regional", ciudad="Barranquilla")
        self.assertEqual(str(port), "Sociedad Portuaria Regional")

    def test_incident_category_unique_name(self):
        IncidentCategory.objects.create(nombre="Lluvia")
        with self.assertRaises(IntegrityError):
            IncidentCategory.objects.create(nombre="Lluvia")

    def test_incident_category_active_by_default(self):
        cat = IncidentCategory.objects.create(nombre="AverÃ­a mecÃ¡nica")
        self.assertTrue(cat.activa)

    def test_incident_category_str(self):
        cat = IncidentCategory.objects.create(nombre="Pinchazo")
        self.assertEqual(str(cat), "Pinchazo")
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.catalogos.tests -v 2`
Expected: FAIL â€” `ModuleNotFoundError: apps.catalogos.models`.

- [ ] **Step 3: ImplementaciÃ³n mÃ­nima**

Crear `apps/catalogos/apps.py`:

```python
from django.apps import AppConfig


class CatalogosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalogos"
```

Crear `apps/catalogos/models.py`:

```python
from django.db import models

from apps.core.models import AuditMixin


class Client(AuditMixin):
    nombre = models.CharField(max_length=200)
    nit = models.CharField("NIT", max_length=20, unique=True, blank=True, default="")
    contacto = models.CharField(max_length=200, blank=True, default="")
    telefono = models.CharField(max_length=30, blank=True, default="")

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Port(AuditMixin):
    nombre = models.CharField(max_length=200, unique=True)
    ciudad = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        verbose_name = "Puerto"
        verbose_name_plural = "Puertos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class IncidentCategory(AuditMixin):
    nombre = models.CharField(max_length=100, unique=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "CategorÃ­a de novedad"
        verbose_name_plural = "CategorÃ­as de novedades"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
```

Crear `apps/catalogos/admin.py`:

```python
from django.contrib import admin

from apps.catalogos.models import Client, IncidentCategory, Port


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("nombre", "nit", "contacto", "telefono")
    search_fields = ("nombre", "nit")


@admin.register(Port)
class PortAdmin(admin.ModelAdmin):
    list_display = ("nombre", "ciudad")
    search_fields = ("nombre",)


@admin.register(IncidentCategory)
class IncidentCategoryAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa")
    list_filter = ("activa",)
```

- [ ] **Step 4: Generar y aplicar migraciones**

```bash
python manage.py makemigrations catalogos
python manage.py migrate
```

- [ ] **Step 5: Verificar que pasa**

Run: `python manage.py test apps.catalogos.tests -v 2`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "feat(catalogos): clientes, puertos y categorias de novedades"
```

---

### Task 5: App conductores â€” modelo Driver

**Files:**
- Create: `apps/conductores/apps.py`
- Create: `apps/conductores/models.py`
- Create: `apps/conductores/admin.py`
- Create: `apps/conductores/tests/__init__.py`
- Create: `apps/conductores/tests/test_models.py`

**Interfaces:**
- Consumes: `apps.core.models.AuditMixin` (Task 2).
- Produces:
  - `class Driver(AuditMixin)` â€” nombre, documento (unique), telefono, estado, observaciones.
  - Constantes de estado: `DRIVER_DISPONIBLE = "disponible"`, `DRIVER_TRABAJANDO = "trabajando"`, `DRIVER_INACTIVO = "inactivo"`.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/conductores/tests/test_models.py`:

```python
from django.db import IntegrityError
from django.test import TestCase

from apps.conductores.models import Driver


class DriverTests(TestCase):
    def test_driver_creation(self):
        driver = Driver.objects.create(nombre="Juan PÃ©rez", documento="12345678")
        self.assertEqual(str(driver), "Juan PÃ©rez")

    def test_driver_document_unique(self):
        Driver.objects.create(nombre="Juan PÃ©rez", documento="12345678")
        with self.assertRaises(IntegrityError):
            Driver.objects.create(nombre="MarÃ­a GÃ³mez", documento="12345678")

    def test_driver_default_state(self):
        driver = Driver.objects.create(nombre="Juan PÃ©rez", documento="12345678")
        self.assertEqual(driver.estado, Driver.DISPONIBLE)

    def test_driver_is_inactive_state(self):
        driver = Driver.objects.create(
            nombre="Juan PÃ©rez", documento="12345678", estado=Driver.INACTIVO
        )
        self.assertTrue(driver.estado == Driver.INACTIVO)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.conductores.tests -v 2`
Expected: FAIL â€” `ModuleNotFoundError`.

- [ ] **Step 3: ImplementaciÃ³n mÃ­nima**

Crear `apps/conductores/apps.py`:

```python
from django.apps import AppConfig


class ConductoresConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.conductores"
```

Crear `apps/conductores/models.py`:

```python
from django.db import models

from apps.core.models import AuditMixin


class Driver(AuditMixin):
    DISPONIBLE = "disponible"
    TRABAJANDO = "trabajando"
    INACTIVO = "inactivo"

    ESTADOS = [
        (DISPONIBLE, "Disponible"),
        (TRABAJANDO, "Trabajando"),
        (INACTIVO, "Inactivo"),
    ]

    nombre = models.CharField(max_length=200)
    documento = models.CharField(max_length=30, unique=True)
    telefono = models.CharField(max_length=30, blank=True, default="")
    estado = models.CharField(max_length=20, choices=ESTADOS, default=DISPONIBLE)
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Conductor"
        verbose_name_plural = "Conductores"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
```

Crear `apps/conductores/admin.py`:

```python
from django.contrib import admin

from apps.conductores.models import Driver


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("nombre", "documento", "telefono", "estado")
    list_filter = ("estado",)
    search_fields = ("nombre", "documento")
```

- [ ] **Step 4: Generar y aplicar migraciones**

```bash
python manage.py makemigrations conductores
python manage.py migrate
```

- [ ] **Step 5: Verificar que pasa**

Run: `python manage.py test apps.conductores.tests -v 2`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "feat(conductores): modelo de conductores con estados"
```

---

### Task 6: App flota â€” modelo Vehicle y VehicleDocument

**Files:**
- Create: `apps/flota/apps.py`
- Create: `apps/flota/models.py`
- Create: `apps/flota/admin.py`
- Create: `apps/flota/tests/__init__.py`
- Create: `apps/flota/tests/test_models.py`

**Interfaces:**
- Consumes: `apps.core.models.AuditMixin` (Task 2).
- Produces:
  - `class Vehicle(AuditMixin)` â€” placa (unique, upper), marca, modelo, anio, estado, observaciones.
  - `class VehicleDocument(AuditMixin)` â€” vehicle FK (related_name="documentos"), tipo, fecha_vencimiento. `unique_together = (("vehicle", "tipo"))`.
  - Constantes:
    - `Vehicle.DISPONIBLE/EN_OPERACION/EN_TALLER/FUERA_DE_SERVICIO`
    - `VehicleDocument.SOAT = "soat"`, `VehicleDocument.TECNOMECANICA = "tecnomecanica"`.
  - `VehicleDocument.dias_restantes()` â†’ `int` (dÃ­as desde hoy hasta vencimiento; negativo si vencido).

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/flota/tests/test_models.py`:

```python
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.flota.models import Vehicle, VehicleDocument


class VehicleTests(TestCase):
    def test_vehicle_creation(self):
        v = Vehicle.objects.create(placa="ABC123", marca="Kenworth", modelo="T880", anio=2020)
        self.assertEqual(str(v), "ABC123")

    def test_vehicle_plate_uppercased(self):
        v = Vehicle.objects.create(placa="abc123")
        self.assertEqual(v.placa, "ABC123")

    def test_vehicle_default_state(self):
        v = Vehicle.objects.create(placa="ABC123")
        self.assertEqual(v.estado, Vehicle.DISPONIBLE)

    def test_vehicle_plate_unique(self):
        Vehicle.objects.create(placa="ABC123")
        with self.assertRaises(IntegrityError):
            Vehicle.objects.create(placa="ABC123")


class VehicleDocumentTests(TestCase):
    def setUp(self):
        self.vehicle = Vehicle.objects.create(placa="ABC123")

    def test_document_creation(self):
        doc = VehicleDocument.objects.create(
            vehicle=self.vehicle,
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() + timedelta(days=20),
        )
        self.assertEqual(doc.tipo, VehicleDocument.SOAT)

    def test_document_type_unique_per_vehicle(self):
        VehicleDocument.objects.create(
            vehicle=self.vehicle,
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() + timedelta(days=20),
        )
        with self.assertRaises(IntegrityError):
            VehicleDocument.objects.create(
                vehicle=self.vehicle,
                tipo=VehicleDocument.SOAT,
                fecha_vencimiento=timezone.localdate() + timedelta(days=40),
            )

    def test_dias_restantes_positive(self):
        doc = VehicleDocument.objects.create(
            vehicle=self.vehicle,
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() + timedelta(days=10),
        )
        self.assertEqual(doc.dias_restantes(), 10)

    def test_dias_restantes_negative_when_expired(self):
        doc = VehicleDocument.objects.create(
            vehicle=self.vehicle,
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() - timedelta(days=5),
        )
        self.assertEqual(doc.dias_restantes(), -5)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.flota.tests -v 2`
Expected: FAIL â€” `ModuleNotFoundError`.

- [ ] **Step 3: ImplementaciÃ³n mÃ­nima**

Crear `apps/flota/apps.py`:

```python
from django.apps import AppConfig


class FlotaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.flota"
```

Crear `apps/flota/models.py`:

```python
from django.db import models

from apps.core.models import AuditMixin


class Vehicle(AuditMixin):
    DISPONIBLE = "disponible"
    EN_OPERACION = "en_operacion"
    EN_TALLER = "en_taller"
    FUERA_DE_SERVICIO = "fuera_de_servicio"

    ESTADOS = [
        (DISPONIBLE, "Disponible"),
        (EN_OPERACION, "En operaciÃ³n"),
        (EN_TALLER, "En taller"),
        (FUERA_DE_SERVICIO, "Fuera de servicio"),
    ]

    placa = models.CharField(max_length=10, unique=True)
    marca = models.CharField(max_length=100, blank=True, default="")
    modelo = models.CharField(max_length=100, blank=True, default="")
    anio = models.PositiveIntegerField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=DISPONIBLE)
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "VehÃ­culo"
        verbose_name_plural = "VehÃ­culos"
        ordering = ["placa"]

    def __str__(self):
        return self.placa

    def save(self, *args, **kwargs):
        self.placa = self.placa.upper()
        super().save(*args, **kwargs)


class VehicleDocument(AuditMixin):
    SOAT = "soat"
    TECNOMECANICA = "tecnomecanica"

    TIPOS = [
        (SOAT, "SOAT"),
        (TECNOMECANICA, "TÃ©cnico-mecÃ¡nica"),
    ]

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="documentos"
    )
    tipo = models.CharField(max_length=20, choices=TIPOS)
    fecha_vencimiento = models.DateField()

    class Meta:
        verbose_name = "Documento de vehÃ­culo"
        verbose_name_plural = "Documentos de vehÃ­culos"
        ordering = ["fecha_vencimiento"]
        unique_together = (("vehicle", "tipo"),)

    def __str__(self):
        return f"{self.get_tipo_display()} {self.vehicle.placa}"

    def dias_restantes(self):
        return (self.fecha_vencimiento - timezone.localdate()).days
```

Nota: aÃ±adir `from django.utils import timezone` al inicio de `apps/flota/models.py`.

Crear `apps/flota/admin.py`:

```python
from django.contrib import admin

from apps.flota.models import Vehicle, VehicleDocument


class VehicleDocumentInline(admin.TabularInline):
    model = VehicleDocument
    extra = 0


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("placa", "marca", "modelo", "anio", "estado")
    list_filter = ("estado",)
    search_fields = ("placa", "marca")
    inlines = [VehicleDocumentInline]


@admin.register(VehicleDocument)
class VehicleDocumentAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "tipo", "fecha_vencimiento", "dias_restantes")
    list_filter = ("tipo",)
```

- [ ] **Step 4: Generar y aplicar migraciones**

```bash
python manage.py makemigrations flota
python manage.py migrate
```

- [ ] **Step 5: Verificar que pasa**

Run: `python manage.py test apps.flota.tests -v 2`
Expected: PASS (8 tests).

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "feat(flota): modelo de vehiculos y documentos con vencimiento"
```

---

### Task 7: App flota â€” servicios de alertas de vencimiento

**Files:**
- Create: `apps/flota/services.py`
- Create: `apps/flota/tests/test_services.py`

**Interfaces:**
- Consumes: `Vehicle`, `VehicleDocument` (Task 6).
- Produces:
  - Constantes: `ALERT_DAYS = 30`, `ESTADO_NORMAL = "normal"`, `ESTADO_PROXIMO = "proximo"`, `ESTADO_VENCIDO = "vencido"`.
  - `def documento_estado(doc: VehicleDocument) -> str` â€” devuelve el estado del documento segÃºn `dias_restantes()`: `> ALERT_DAYS` â†’ `normal`; `0..ALERT_DAYS` â†’ `proximo`; `< 0` â†’ `vencido`.
  - `def alertas_vencimiento() -> list[dict]` â€” lista de alertas de TODOS los documentos con estado `proximo` o `vencido`. Cada dict: `{"documento": doc, "vehiculo": doc.vehicle, "tipo": doc.get_tipo_display(), "fecha_vencimiento": doc.fecha_vencimiento, "dias": doc.dias_restantes(), "estado": estado}`. Ordenadas por `dias` ascendente.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/flota/tests/test_services.py`:

```python
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.flota.models import Vehicle, VehicleDocument
from apps.flota.services import (
    ALERT_DAYS,
    ESTADO_NORMAL,
    ESTADO_PROXIMO,
    ESTADO_VENCIDO,
    alertas_vencimiento,
    documento_estado,
)


class DocumentoEstadoTests(TestCase):
    def test_normal_when_more_than_30_days(self):
        doc = VehicleDocument(
            vehicle=Vehicle(placa="ABC123"),
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() + timedelta(days=ALERT_DAYS + 1),
        )
        self.assertEqual(documento_estado(doc), ESTADO_NORMAL)

    def test_proximo_when_within_30_days(self):
        doc = VehicleDocument(
            vehicle=Vehicle(placa="ABC123"),
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() + timedelta(days=10),
        )
        self.assertEqual(documento_estado(doc), ESTADO_PROXIMO)

    def test_vencido_when_expired(self):
        doc = VehicleDocument(
            vehicle=Vehicle(placa="ABC123"),
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() - timedelta(days=1),
        )
        self.assertEqual(documento_estado(doc), ESTADO_VENCIDO)


class AlertasVencimientoTests(TestCase):
    def setUp(self):
        self.vehiculo = Vehicle.objects.create(placa="ABC123")

    def test_alerts_include_only_proximo_and_vencido(self):
        VehicleDocument.objects.create(
            vehicle=self.vehiculo,
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() + timedelta(days=60),
        )
        VehicleDocument.objects.create(
            vehicle=self.vehiculo,
            tipo=VehicleDocument.TECNOMECANICA,
            fecha_vencimiento=timezone.localdate() + timedelta(days=10),
        )
        alerts = alertas_vencimiento()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["estado"], ESTADO_PROXIMO)

    def test_alerts_sorted_by_days_ascending(self):
        VehicleDocument.objects.create(
            vehicle=self.vehiculo,
            tipo=VehicleDocument.SOAT,
            fecha_vencimiento=timezone.localdate() + timedelta(days=15),
        )
        VehicleDocument.objects.create(
            vehicle=self.vehiculo,
            tipo=VehicleDocument.TECNOMECANICA,
            fecha_vencimiento=timezone.localdate() - timedelta(days=3),
        )
        alerts = alertas_vencimiento()
        days = [a["dias"] for a in alerts]
        self.assertEqual(days, sorted(days))
        self.assertEqual(days[0], -3)
        self.assertEqual(alerts[0]["estado"], ESTADO_VENCIDO)
```

- [ ] **Step 2: Verificar que falla**

Run: `python manage.py test apps.flota.tests.test_services -v 2`
Expected: FAIL â€” `ModuleNotFoundError: apps.flota.services`.

- [ ] **Step 3: ImplementaciÃ³n mÃ­nima**

Crear `apps/flota/services.py`:

```python
from apps.flota.models import VehicleDocument

ALERT_DAYS = 30
ESTADO_NORMAL = "normal"
ESTADO_PROXIMO = "proximo"
ESTADO_VENCIDO = "vencido"


def documento_estado(doc):
    dias = doc.dias_restantes()
    if dias < 0:
        return ESTADO_VENCIDO
    if dias <= ALERT_DAYS:
        return ESTADO_PROXIMO
    return ESTADO_NORMAL


def alertas_vencimiento():
    alerts = []
    for doc in VehicleDocument.objects.select_related("vehicle").all():
        estado = documento_estado(doc)
        if estado in (ESTADO_PROXIMO, ESTADO_VENCIDO):
            alerts.append(
                {
                    "documento": doc,
                    "vehiculo": doc.vehicle,
                    "tipo": doc.get_tipo_display(),
                    "fecha_vencimiento": doc.fecha_vencimiento,
                    "dias": doc.dias_restantes(),
                    "estado": estado,
                }
            )
    alerts.sort(key=lambda a: a["dias"])
    return alerts
```

- [ ] **Step 4: Verificar que pasa**

Run: `python manage.py test apps.flota.tests -v 2`
Expected: PASS (13 tests total en `apps.flota`).

- [ ] **Step 5: Verificar que todos los tests del proyecto pasan**

Run: `python manage.py test -v 2`
Expected: PASS (todos los tests del proyecto: core, catalogos, conductores, flota).

- [ ] **Step 6: Commit local**

```bash
git add -A
git commit -m "feat(flota): servicios de alertas de vencimiento de documentos"
```

---

## Self-Review del Plan

**Cobertura del spec (Plan 1):**
- Scaffolding Django + settings por entorno + dev/prod: Task 1. âœ”
- Paleta de tokens CSS + template base + login: Task 3. âœ”
- `core` mixins de auditorÃ­a (`created_at/updated_at/created_by/updated_by`) + `history`: Task 2. âœ”
- Grupos Admin/Secretaria/Gerencia: Task 2 (`setup_groups`). âœ”
- `clients`, `ports`, `incident_categories` (catÃ¡logo de novedades): Task 4. âœ”
- `drivers` con estados: Task 5. âœ”
- `vehicles` con estados + `vehicle_documents` (SOAT/tecnomecÃ¡nica, vencimiento): Task 6. âœ”
- Alertas preventivas 30 dÃ­as + clasificaciÃ³n normal/prÃ³ximo/vencido: Task 7. âœ”

**Fuera de este plan (fases posteriores):** operaciones y turnos (Plan 2), nÃ³mina (Plan 3), facturaciÃ³n/saldos/CSV (Plan 4), dashboards/Gantt (Plan 5). El dashboard de flota (panel de vencimientos) se construye en Plan 5 sobre `alertas_vencimiento()`.

**Placeholders:** ninguno; cada paso contiene cÃ³digo o comandos reales.

**Consistencia de tipos:** `dias_restantes()` definido en Task 6 y usado en Task 7 con la misma semÃ¡ntica. `alertas_vencimiento()` produce dicts con las claves documentadas en "Produces". `AuditMixin` heredado por Client/Port/IncidentCategory/Driver/Vehicle/VehicleDocument.







