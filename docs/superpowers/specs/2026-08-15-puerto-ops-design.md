# Sistema de Gestión de Operaciones Portuarias — Transportes Renacer

**Fecha:** 2026-08-15
**Estado:** Aprobado por el cliente
**Tipo:** Especificación de diseño / spec de implementación

---

## 1. Resumen

Aplicación web para el control integral de operaciones portuarias de Transportes Renacer (Barranquilla): operaciones asociadas a buques, flota de tractomulas, turnos de conductores, nómina semanal y facturación por horas. La unidad fundamental de registro es el **turno operativo**, del que se derivan horas trabajadas, pago al conductor, horas facturables, valor generado, abonos y saldo.

El MVP cubre toda la prioridad P0 del PRD más dashboards y Gantt básicos (P1). El resto de P1/P2 queda fuera de alcance.

---

## 2. Decisiones de stack (aprobadas)

| Capa | Decisión |
|---|---|
| Backend | Django 5.x + Python 3.13 |
| BD producción | PostgreSQL vía Supabase (cadena de conexión por variable de entorno) |
| BD desarrollo | SQLite |
| Frontend | Templates Django + HTMX + **CSS puro con variables** (patrón del prototipo Gantt) + JS vanilla |
| Gantt | HTML/CSS/JS vanilla, eje de tiempo continuo multi-día, turnos que cruzan medianoche |
| Dashboards KPI | Chart.js (solo gráficos line/bar/pie), servido como archivo estático local (`static/vendor/`) |
| Deploy | Render (web service) + Gunicorn + Whitenoise, configuración por variables de entorno |

**No se usa:** Node.js (no instalado ni requerido), React/Vue, Chart.js para el Gantt, Tailwind Play CDN, Tailwind en general (el sistema visual ya existe en CSS puro con variables).

### Justificación del Gantt sin Chart.js
Chart.js no tiene tipo de gráfico Gantt; sus barras horizontales requieren plugins de terceros sin mantenimiento o hacks de stacking. El requisito es un *scheduler de recursos* (filas por mula, bloques de ancho variable, metadata por bloque, click → panel detalle, drag/resize futuro), que es un caso de uso de DOM/SVG, no de canvas. Chart.js se limita a los KPIs (evolución de facturación, horas por mula, ranking de conductores).

### Justificación de CSS puro sin Tailwind
El sistema visual ya existe, tokenizado (`:root { --bg, --ink, --line }`) y deliberado. Tailwind añadiría una capa de traducción (mapear tokens al theme) con riesgo de "look por defecto" y un paso de build, sin ganancia para un producto de ~11 módulos con identidad propia. CSS puro es lo más durable para una empresa pequeña que mantendrá el sistema años.

---

## 3. Paleta de colores (definitiva)

Identidad: **seguridad industrial / fiabilidad**. Base clara para legibilidad en exteriores (consultas de la secretaria desde el puerto).

```css
/* Primario — azul marino profundo (navegación, headers, estructura) */
--primary:       #0A2A4A;
--primary-dark:  #071E35;
--primary-ink:   #FFFFFF;

/* Secundario — naranja de seguridad (SOLO CTA críticos + estado Activo) */
--secondary:       #FF5A1F;
--secondary-hover: #E64A14;
--secondary-ink:   #FFFFFF;

/* Semánticos — texto oscuro + tinta de fondo (mapea ok/warn/bad del Gantt) */
--ok:        #1E9E5A;  --ok-tint:  #E3F5EC;  --ok-ink:  #0E5C37;
--warn:      #B45309;  --warn-tint:#FFF1D6;  --warn-ink:#7A4507;
--danger:    #D92D20;  --danger-tint:#FDE9E9;--danger-ink:#8F1D13;

/* Neutros fríos */
--surface:        #FFFFFF;
--surface-base:   #F8F9FA;
--surface-hover:  #EEF1F4;
--line:           #D5DCE3;
--ink:            #16212B;
--ink-dim:        #5A6B7B;
--ink-faint:      #8A97A5;
```

### Tipografía
- **IBM Plex Sans** — interfaz.
- **IBM Plex Mono** — todos los datos (horas, placas, códigos, tablas, Gantt).

### Reglas de uso
- El naranja `--secondary` se gasta con disciplina: solo CTA críticos y estado "Activo".
- Verde/ámbar/rojo solo con valor semántico; el texto siempre usa la variante oscura (`--ok-ink`, `--warn-ink`, `--danger-ink`) sobre tinta de fondo (`--ok-tint`, etc.) para cumplir contraste.
- `#FFFFFF` = nivel elevado (tarjetas/paneles); `#F8F9FA` = fondo base.
- La línea "AHORA" del Gantt se pinta con `--secondary` (señal en vivo).

---

## 4. Usuarios y permisos

Modelo: `User` de Django + `Group`.

| Grupo | Permisos |
|---|---|
| **Admin** | Acceso completo: crear usuarios, configurar tarifas, administrar vehículos/conductores, reportes, configuración, catálogos |
| **Secretaria** | Operativo principal: crear/actualizar operaciones, registrar turnos, novedades, abonos, preparar nómina, registrar pagos, exportar relaciones |
| **Gerencia** | Solo consulta: dashboards, operaciones, nómina, facturación, saldos, indicadores, historial |

Restricciones de vista por grupo en las vistas (mixins de permisos). Los campos `created_by` / `updated_by` se autocompletan con el usuario autenticado.

---

## 5. Modelo de datos

Todas las tablas relevantes llevan `created_at`, `updated_at`, `created_by`, `updated_by` (mixins). El historial completo de modificaciones se registra con `django-simple-history`.

### Catálogos
**`cargo_generators`** — Generador de carga: nombre, nit (opcional, único si se llena), contacto, teléfono.
**`ports`** — nombre, ciudad.
**`incident_categories`** — nombre (unique), activa. Catálogo de novedades (Lluvia, Avería mecánica, Pinchazo, Tanqueo, Falla eléctrica, Espera de embarque, Problema operativo del puerto, Cambio de mula, Cambio de conductor, Espera, Otro). Se pueden crear nuevas categorías desde el registro de turno.

### Flota y conductores
**`vehicles`** — placa (unique), marca, modelo, año, estado, observaciones.
**`vehicle_documents`** — vehicle FK, tipo (SOAT | Tecnomecánica), fecha_vencimiento. Como máximo un documento vigente por tipo por vehículo (se actualiza la fecha al renovar); el historial de valores anteriores queda en el log de auditoría.
**`drivers`** — nombre, documento (unique), teléfono, estado, observaciones.

### Estados
**vehicles**: `disponible | en_operacion | en_taller | fuera_de_servicio`
**drivers**: `disponible | trabajando | inactivo`

### Operaciones
**`operations`** — codigo (unique), buque, generador_de_carga FK, puerto FK, fecha_inicio, fecha_fin_estimada, fecha_fin_real (null), estado, meta_horas (default 11), tarifa_hora, valor_turno_dia, valor_turno_noche, observaciones.

Estado: `programada | activa | finalizada | cancelada`. Las finalizadas/canceladas no se eliminan: pasan a historial.

**`operation_vehicles`** — operation FK, vehicle FK, fecha_asignacion, activa (bool), unique_together(operation, vehicle) cuando activa.

Al crear la operación se seleccionan mulas; solo se ofrecen las **disponibles**. Al asignar: vehicle → `en_operacion`. Al finalizar la operación: todos sus vehicles → `disponible`. (Si un vehicle está asignado a otra operación activa, no se libera.)

### Turnos (unidad central)
**`shifts`** — operation FK, vehicle FK, driver FK, fecha_inicio (datetime), fecha_fin (datetime), horas_trabajadas (decimal, calculado), meta_horas (copiada de la operación), cumplimiento_pct (calculado), tipo (`dia | noche`), valor_estandar (copiado de la operación), valor_pagado (decimal), estado, motivo_cancelacion, observaciones, `history`. La novedad asociada se registra vía `incidents` (1:1 opcional).

Estado: `programado | realizado | cancelado | anulado`.

- **horas_trabajadas** = fecha_fin − fecha_inicio (soporta turno nocturno 18:00→06:00 que cruza medianoche; el turno pertenece a la fecha de inicio). Zona horaria `America/Bogota`.
- **cumplimiento_pct** = horas_trabajadas / meta_horas × 100.
- **valor_pagado** = valor del turno (día/noche) desde la operación, completo si el turno es **realizado**. Editables con auditoría: valor original, nuevo valor, motivo, usuario, fecha.
- Un turno con horas < meta (p. ej. 8h de 11h) **exige novedad** al guardar (§16).
- Los turnos no se eliminan físicamente. Cancelado/anulado: motivo, usuario, fecha, observación. Un turno cancelado **no** genera horas facturables ni pago, no aparece en nómina ni CSV, pero permanece en historial.
- **Cancelado** ≠ **Anulado**: cancelado = no se realizó (mula averiada, turno cancelado). Anulado = error administrativo de registro.

### Novedades
**`incidents`** — shift FK (1:1, null, se crea/actualiza con el turno), incident_categories FK, descripcion. Un turno corto (< meta) exige tener incident asociado al guardar.

### Nómina
**`payrolls`** — numero (NOM-YYYY-NNN, unique), periodo_inicio, periodo_fin, estado, total, fecha_pago, observaciones.

Estado: `pendiente | liquidado | pagado`.

**`payroll_items`** — payroll FK, shift FK, valor. **unique_together(payroll, shift)**; además el shift solo puede estar en un payroll_item activo (constraint única sobre shift) → **impide pago duplicado**.

**`driver_advances`** — driver FK, fecha, valor, descripcion, payroll FK (null; si se asigna, se descuenta en esa liquidación).

Liquidación: el usuario selecciona periodo (inicio/fin). Solo se muestran turnos **realizados sin pagar** dentro del periodo. Al liquidar se fijan los turnos a la liquidación. Neto por conductor = Σ valores de sus turnos en la liquidación − Σ abonos del conductor asociados a la liquidación.

### Facturación
**`billing_records`** — operation FK, shift FK (null para ajustes manuales), fecha, horas, tarifa_hora, valor, estado.

- Valor facturado por turno = **horas_trabajadas × tarifa_hora de la operación** (independiente del pago al conductor).
- Estado: `pendiente | incluido | facturado | cobrado`.
- El CSV de facturación se genera por operación: columnas Fecha, Operación, Mula, Turno, Hora inicio, Hora final, Horas trabajadas + resumen Mula/Horas totales. **No incluye el chofer.**

### Abonos de clientes y saldos
**`client_payments`** — operation FK, fecha, valor, observaciones.

**Saldo de la operación** = Σ(billing_records) − Σ(client_payments). Se muestra por operación.

### Auditoría
**`audit_logs`** / django-simple-history en: operations, shifts, vehicles, drivers, payrolls, billing_records, client_payments, driver_advances, vehicle_documents.

**Tarifas** — se modelan como campos en `operations` (tarifa_hora, valor_turno_dia, valor_turno_noche) y quedan congeladas por operación: modificar tarifas de una operación nueva no afecta operaciones anteriores. El historial de cambios en estos campos queda cubierto por el log de `operations`.

---

## 6. Reglas de negocio (aprobadas)

1. **Pago al conductor** = valor turno completo si el turno es **realizado** (aunque haya novedad y trabaje menos horas; estuvo disponible). **Cancelado/Anulado = $0**, sin nómina, sin facturación, queda en historial.
2. **Facturación** = horas reales × tarifa_hora. **Separación estricta** pago vs. facturación (§38 del PRD).
3. **Turno corto** (< meta) exige novedad al guardar.
4. **Doble turno**: mismo conductor con turnos solapados, o descanso < 8h entre fin de un turno y inicio del siguiente → alerta "⚠️ Posible doble turno" (se muestra en nómina/ranking y en el Gantt del conductor).
5. **Nómina semanal**: periodo configurable elegido por la secretaria; solo turnos sin pagar; liquidación bloquea turnos (unique).
6. **Alertas de vencimiento**: documento con ≤30 días → 🟡 "Próximo a vencer"; < hoy → 🔴 "Vencido"; resto 🟢 "Normal". No bloquea asignación en MVP (decisión de configuración posterior). El panel de alertas permite ir directo a la ficha del vehículo.
7. **"Información registrada hasta"**: se calcula como el `updated_at` máximo de las entidades relevantes de cada dashboard (no "ahora"). Se muestra en todos los dashboards.
8. **Horas**: datetimes con `America/Bogota`; el turno nocturno 18:00→06:00 se calcula real y pertenece a la fecha de inicio.
9. **Operaciones finalizadas/canceladas**: no se eliminan, pasan a historial.
10. **Tarifas congeladas por operación** (campos `tarifa_hora`, `valor_turno_dia`, `valor_turno_noche` en `operations`).

---

## 7. Gantt de operación (rediseñado)

**Eje de tiempo continuo multi-día** (no 24 columnas por día). Cada turno es un bloque posicionado por timestamp absoluto.

- Regla superior: bandas de día + horas, línea **AHORA** en `--secondary` (hora servidor, `America/Bogota`).
- Filas: una por mula asignada (o por conductor cuando el filtro lo pida).
- Estilos por cumplimiento: `ok` (≥90%), `warn` (70–89%), `bad` (<70%) usando las tintas de fondo semánticas; relleno proporcional al % cumplido.
- Turnos cancelados/anulados: punteado/atenuado + tooltip con motivo.
- Click en bloque → panel lateral: horario, duración, cumplimiento, actividad, novedad, mula/placa, valor.
- Filtros: operación, mula, rango de fechas.
- Datos vía `fetch('/api/...')` (endpoint JSON).
- Futuro (fuera de MVP): drag/resize de bloques tipo Monday.

---

## 8. Dashboards

### Dashboard principal (operativo-financiero)
Operaciones activas, mulas en operación/disponibles/en taller, horas trabajadas, horas facturables, valor generado, abonos, saldo pendiente, nómina semanal, última actualización de datos.

### Dashboard de flota
Total mulas, en operación, disponibles, en taller, fuera de servicio + **panel de vencimientos** (Mula, Documento, Vencimiento, Días restantes, Estado, link a ficha) con semáforo 🟢🟡🔴.

### Dashboard de nómina
Selector de semana. Total nómina, conductores, turnos, horas, abonos, neto a pagar. Ranking: más horas, más turnos, posibles dobles turnos.

### Dashboard operativo
Horas por operación, horas por mula, cumplimiento de 11h, horas perdidas, principales novedades, operaciones con menor cumplimiento.

### Dashboard financiero
Valor generado, abonos recibidos, saldo pendiente, valor por operación, operaciones con mayor saldo, evolución de facturación (Chart.js line/bar).

### Historial de operaciones
Operaciones finalizadas/canceladas con trazabilidad completa.

---

## 9. Estructura del proyecto

```
transportes-renacer/
  manage.py
  requirements.txt
  render.yaml
  .env.example
  .gitignore
  config/
    settings/
      __init__.py
      base.py
      dev.py
      prod.py
    urls.py
    wsgi.py
    asgi.py
  apps/
    core/          # mixins (TimeStampedModel, UserStampedModel), permisos, audit
    catalogos/     # cargo_generators, ports, incident_categories
    flota/         # vehicles, vehicle_documents, alertas
    conductores/   # drivers
    operaciones/   # operations, operation_vehicles, shifts, incidents, gantt/timeline
    nomina/        # payrolls, payroll_items, driver_advances
    facturacion/   # billing_records, client_payments, csv
    dashboard/     # vistas de agregación de todos los módulos
  templates/
    base.html
    ... (por app)
  static/
    css/tokens.css, app.css
    js/gantt.js, app.js
    vendor/chart.umd.js
  docs/superpowers/specs/
```

- Apps configuradas como `apps.<nombre>.apps.<Nombre>Config`.
- URL prefix por app.
- `requirements.txt`: django, django-simple-history, gunicorn, whitenoise, dj-database-url, python-dotenv, psycopg[binary].

---

## 10. Configuración y despliegue

- **Entorno dev**: `config/settings/dev.py`, SQLite, `python manage.py runserver`.
- **Entorno prod (Render + Supabase)**: `config/settings/prod.py` lee `DATABASE_URL` (Supabase PostgreSQL), `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`. Whitenoise sirve estáticos. Gunicorn.
- `render.yaml`: web service, build command (instalar deps, collectstatic), start command (gunicorn).
- `.env.example` documenta todas las variables.

---

## 11. Alcance MVP

**Incluido (P0 completo + dashboards/Gantt básicos):**
Usuarios y roles, conductores, mulas, generadores de carga, puertos, operaciones, tarifas, asignación de mulas, registro de turnos, cálculo de horas, cumplimiento, novedades (con creación de categorías), cancelación de turnos, nómina semanal, abonos a conductores, control de turnos pagados, facturación por horas, abonos de clientes, saldos, CSV, estados de vehículos, SOAT, técnico-mecánica, alertas de vencimiento, dashboards (principal, flota, nómina, operativo, financiero), historial de operaciones, Gantt por operación, detección de doble turno, ranking de conductores, horas por mula/operación, análisis de novedades, fecha "actualizado hasta".

**Excluido (fuera de MVP):** reportes avanzados, exportaciones adicionales, automatización de relaciones, notificaciones automáticas, WhatsApp/email, app móvil, digitalización de boletas con foto/OCR, drag/resize del Gantt.

---

## 12. Criterios de aceptación

El MVP es funcional cuando se puede completar el flujo del §37 del PRD manteniendo trazabilidad en cada paso:
1. Crear operación (buque, puerto, tarifa $35.000/h, turno $180.000, meta 11h) → 2. asignar mulas → 3. registrar turno (mula, Juan, 06:00→17:00) → 4. sistema calcula 11h, 100% cumplimiento, $180.000 nómina, $385.000 facturación → 5. segundo turno → 6. nómina semanal → 7. abono al conductor → 8. marcar liquidación pagada → 9. relación de facturación → 10. abono del cliente → 11. consultar saldo → 12. finalizar operación → 13. consultar en historial.
