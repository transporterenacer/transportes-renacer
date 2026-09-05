# Transportes Renacer — Sistema de Gestión de Operaciones Portuarias

Sistema web para gestión integral de operaciones de transporte portuario en Colombia.

**Python 3.12+** · **Django 5.2** · **SQLite / PostgreSQL**

---

## Qué es el sistema

Transportes Renacer es una plataforma web diseñada para empresas de transporte portuario en Colombia que necesitan centralizar y controlar toda su operación diaria. El sistema reemplaza planillas, hojas de cálculo y procesos manuales por una herramienta única donde se registra cada operación por buque, se asignan mulas y conductores, y se liquidan pagos y facturación de forma automática.

El corazón del sistema es la gestión de operaciones portuarias: cada vez que un buque llega al puerto, se crea una operación, se asignan vehículos (mulas) y conductores con sus respectivos turnos, y el sistema calcula automáticamente las horas trabajadas, los valores de nómina y las relaciones de cobro hacia los clientes. Esto elimina errores manuales y acelera los procesos de facturación y pago.

También incluye un módulo de gestión documental digital que mantiene el expediente de cada vehículo y conductor organizado, con alertas automáticas de vencimiento de documentos críticos como technomechanical, pólizas y licencias. La información se almacena de forma segura y está disponible para consulta en cualquier momento.

Todo está pensado para que el equipo operativo, administrativo y de nómina trabaje sobre la misma información, en tiempo real, sin duplicidades ni sorpresas al cierre de semana.

---

## Módulos

| Módulo | Qué hace |
| ------ | -------- |
| Panel de control | KPIs del día: operaciones activas, flota disponible, horas trabajadas y nómina pendiente. |
| Operaciones | Crear y gestionar operaciones por buque, asignar mulas, registrar turnos con cálculo automático de horas. |
| Línea de tiempo | Vista Gantt semanal de todas las operaciones y turnos para visualizar la carga de trabajo. |
| Flota | Gestión de vehículos (mulas), estados, documentación vehicular y mantenimiento. |
| Conductores | Gestión de conductores, estados, licencias y documentos personales. |
| Nómina | Liquidación semanal de conductores, pagos, anticipos y resumen de costos. |
| Facturación | Relaciones de cobro, abonos de clientes, aplicación FIFO y exportación CSV. |
| Documentos | Expediente digital por vehículo y conductor con alertas de vencimiento. |
| Configuración | Catálogos maestros: puertos, generadores de carga, categorías y parámetros del sistema. |

---

## Stack tecnológico

| Capa | Tecnología |
| ---- | ---------- |
| Backend | Django 5.2, Python 3.12 |
| Frontend | HTML/CSS/JS vanilla (sin framework JavaScript) |
| Base de datos | SQLite (desarrollo), PostgreSQL (producción) |
| Almacenamiento de documentos | Local / Supabase Storage |
| Autenticación | Django auth |

---

## Setup local

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/transportes-renacer.git
cd transportes-renacer

# 2. Crear y activar el entorno virtual
python -m venv .venv
.\.venv\Scripts\activate        # Windows PowerShell
# source .venv/bin/activate     # Linux / macOS

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Copiar la configuración de entorno
copy .env.example .env          # Windows
# cp .env.example .env          # Linux / macOS

# 5. Aplicar migraciones y sembrar datos iniciales
python manage.py migrate
python manage.py setup_document_types

# 6. (Opcional) Sembrar datos de demostración
python manage.py seed_demo

# 7. Levantar el servidor
python manage.py runserver
```

Abre http://127.0.0.1:8000 en el navegador.

---

## Variables de entorno

Copiá `.env.example` a `.env` y ajustá los valores según tu entorno.

| Variable | Descripción | Default |
| -------- | ----------- | ------- |
| `DJANGO_SETTINGS_MODULE` | Módulo de configuración de Django. | `config.settings.dev` |
| `SECRET_KEY` | Clave secreta de Django (cambiar en producción). | `change-me` |
| `DEBUG` | Modo depuración (`True`/`False`). | `True` |
| `DATABASE_URL` | URL de conexión a la base de datos. | `sqlite:///db.sqlite3` |
| `ALLOWED_HOSTS` | Hosts permitidos (separados por coma). | `127.0.0.1,localhost` |
| `DOCUMENT_STORAGE_BACKEND` | Backend de almacenamiento: `local` o `supabase`. | `local` |
| `DOCUMENT_BUCKET` | Nombre del bucket en Supabase Storage. | `documents` |
| `SUPABASE_URL` | URL del proyecto Supabase (solo backend `supabase`). | *(vacío)* |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key de Supabase (nunca en el navegador). | *(vacío)* |

---

## Tests

```bash
python manage.py test -v 2
```

En desarrollo y tests el módulo documental usa `LocalStorage`, por lo que la suite corre sin credenciales de Supabase.

---

## Licencia

© 2026 Transportes Renacer — Todos los derechos reservados.

Barranquilla, Colombia.

---

*Desarrollado para Transportes Renacer.*
