# Arquitectura de Módulos — Transportes Renacer

**Fecha:** 16/08/2026
**Estado:** Aprobado por el usuario el 16/08/2026

## 1. Propósito

Definir la arquitectura de páginas/módulos de la aplicación para que cada módulo tenga
una responsabilidad clara, evitando que funcionalidad de un módulo se mezcle con otro
(ej. funciones de nómina dentro de operaciones, o facturación dentro de turnos).

## 2. Principios

1. **Cada módulo responde una pregunta distinta** sobre los mismos datos.
2. **Los turnos son el módulo central transversal** de la aplicación: del turno nace el
   valor económico (horas → nómina + facturación + analítica).
3. **Anular ≠ eliminar**: los turnos se anulan con motivo y trazabilidad; un turno
   anulado no genera nómina ni facturación.
4. **Rediseño visual** en CSS puro con variables (sin Tailwind ni frameworks), con
   carga coexistente `app.css` + `base.css` para no romper páginas aún no migradas.
5. Los valores económicos (pago conductor, valor facturable) se **congelan al momento
   del registro** con trazabilidad de excepciones.

## 3. Modelo de datos

```
OPERACIÓN (buque/servicio)
    └── genera TURNOS (horas / mula / conductor)
            ├── NÓMINA (por conductor)      → Shift.valor_pagado
            └── FACTURACIÓN (por cliente)   → Shift.valor_facturable
```

Alrededor: FLOTA, CONDUCTORES, DOCUMENTOS y CATÁLOGOS alimentan a TURNOS.

## 4. Mapa de módulos vs estado actual

| Módulo | Dónde vive hoy | Estado | Qué falta |
|---|---|---|---|
| INICIO | `dashboard:inicio` | Existe | Rediseño + panel de alertas + analítica |
| OPERACIONES | app `operaciones` | Existe | Rediseño + filtros + detalle enriquecido |
| TURNOS | modelo `Shift` en `operaciones` | Modelo existe, módulo nuevo | Página transversal, KPIs, tabla, registro, edición/anulación, Gantt de semana |
| FLOTA | app `flota` (solo modelos) | Páginas nuevas | Lista + detalle de mula |
| CONDUCTORES | app `conductores` (solo modelos) | Páginas nuevas | Lista + detalle |
| NÓMINA | app `nomina` | Existe y completo | Rediseño |
| FACTURACIÓN | app `facturacion` | Parcial | Página de resumen/lista + rediseño |
| DOCUMENTOS | app `documentos` | Recién construido | Solo aplicar shell nuevo |
| CONFIGURACIÓN | modelos en `catalogos` + `DocumentType` | Páginas nuevas | CRUD de catálogos |
| REPORTES | — | Futuro | No va en sidebar por ahora |

## 5. Navegación (sidebar definitiva)

Orden de los ítems (enlaces a URLs reales):

| Ítem | URL real |
|---|---|
| **TRANSPORTES RENACER** (logo → home) | `dashboard:inicio` |
| Inicio | `dashboard:inicio` |
| Operaciones | `operaciones:lista` |
| Turnos | `turnos:lista` (nuevo) |
| Flota | `flota:lista` (nuevo) |
| Conductores | `conductores:lista` (nuevo) |
| — separador — | |
| Nómina | `nomina:lista` |
| Facturación | `facturacion:resumen` (nuevo) |
| — separador — | |
| Documentos | `documentos:panel` |
| — separador — | |
| Configuración | `configuracion:inicio` (nuevo) |

Reglas:
- El logo es un botón que lleva siempre a `dashboard:inicio`.
- Ítem activo resaltado (borde naranja `--secondary`).
- Los sub-paneles del dashboard (Vencimientos, Nómina, Operativo, Financiero,
  Historial) se muestran como sub-nav solo cuando el usuario está dentro de `dashboard`.
- Sidebar y navegación se ocultan para usuarios anónimos (login).

## 6. Shell base (Fase 0)

- `static/css/base.css` (nuevo): tokens + componentes (sidebar, topbar, cards,
  data-table, badges, buttons, forms). Cargado DESPUÉS de `app.css`.
- `templates/base.html`: shell con sidebar + topbar + footer.
  - Topbar: `{% block page_title %}` a la izquierda; a la derecha búsqueda,
    `{% block topbar_action %}` (por defecto "+ Nueva Operación" → `operaciones:nuevo`),
    campana con `alertas_count`, ayuda.
  - Footer simple.
- `templates/dashboard/inicio.html`: rediseño con KPIs, operaciones activas, alertas.

### Datos del dashboard de inicio
- KPIs: `kpis.operaciones_activas`, `kpis.mulas_en_operacion`, `kpis.mulas_disponibles`,
  `kpis.mulas_en_taller`, `kpis.horas_trabajadas`, `kpis.horas_facturables`,
  `kpis.valor_generado`, `kpis.abonos`, `kpis.saldo_pendiente`,
  `kpis.nomina_semanal_pendiente`.
- Alertas: `apps.flota.services.alertas_vencimiento()`.
- Tabla de operaciones activas: `op.codigo`, `op.buque`, `op.generador_de_carga`,
  `op.puerto`, `op.estado`, `op.total_horas` / `op.meta_horas`.
- Mostrar siempre "Información registrada hasta: DD/MM/AAAA HH:MM".

### Contexto de notificaciones
- `alertas_count` debe estar disponible en el shell para todas las páginas
  (context processor o similar).

## 7. Módulo TURNOS (Fase 1)

Es el módulo central. Respuesta: "¿Qué turnos se trabajaron esta semana?"

### 7.1 Modelo — cambios (D1 aprobado)

Agregar a `apps.operaciones.models.Shift`:
- `valor_facturable` (`DecimalField`, por defecto 0) — valor facturable al cliente.
- `es_excepcion` (`BooleanField`, default False) — True si el valor se editó al registrar.

Reglas:
- Al registrar desde el módulo, precargar `valor_estandar` = valor del turno de la
  operación (día/noche) y `valor_facturable` = `tarifa_hora × horas`. Si la secretaria
  modifica cualquiera de los dos, `es_excepcion=True`.
- Requiere migración de la app `operaciones`.

### 7.2 Páginas

- `turnos:lista` — abre la semana actual por defecto.
  - Cabecera: "Turnos · Semana del X al Y de MMMM YYYY" + navegación `[‹] [Hoy] [›]`.
  - KPIs pequeños: turnos registrados, horas trabajadas, cumplimiento promedio,
    turnos con novedad, doble turno.
  - Tabla: Fecha | Operación | Mula | Conductor | Turno (Día/Noche) | Inicio | Fin |
    Horas | Meta | Cumpl. | Valor turno | Novedad | Estado.
  - Filtros: fecha, operación, mula, conductor, estado, novedad.
  - Botón "+ Registrar turno" (no requiere pasar por Operaciones).
- `turnos:nuevo` — formulario con cálculos automáticos:
  - Entradas: operación, fecha, mula, conductor, turno (día/noche), hora inicio,
    hora fin, novedad, observación.
  - Automático (desde la operación): meta horas, valor turno, tarifa cliente.
  - Calcula: horas trabajadas, cumplimiento, pago conductor, valor facturable.
  - Si se modifica un valor → excepción (D1).
- `turnos:editar` — edición del turno (conserva trazabilidad).
- `turnos:anular` — anula con motivo (usa `cancelar_turno`); el turno anulado no
  genera nómina ni facturación (ya garantizado por `valor_pagado=0`).
- `turnos:gantt` / `turnos:gantt_datos` (D2 aprobado) — Gantt transversal por semana
  (timeline), reutilizando la lógica de `bloques_gantt` y `gantt.js`.
  - Filtros: operación, mula, fecha/semana.
  - Permite analizar horas reales, huecos, turnos incompletos, solapamientos,
    doble turno y novedades.

### 7.3 Servicios

- Reutilizar `registrar_turno`, `cancelar_turno`, `detectar_dobles_turnos`,
  `kpis_operativo`, `bloques_gantt`.
- El registro desde `/turnos/` debe permitir seleccionar la operación (a diferencia del
  flujo actual que recibe la operación por URL).

## 8. Módulo FLOTA (Fase 2)

Respuesta: "¿Qué vehículos tengo y cuál es su estado?"

- `flota:lista` — dashboard con KPIs de estado (total, en operación, disponible, en
  taller, fuera de servicio) + tabla: Placa | Marca | Modelo | Estado | Operación |
  Conductor | SOAT | Tecnomecánica.
- `flota:detalle` — información, estado actual, historial (operaciones/turnos/horas),
  documentación (reusa `documentos`), alertas de vencimiento.

## 9. Módulo CONDUCTORES (Fase 3)

Respuesta: "¿Quiénes trabajan y cuánto han trabajado?"

- `conductores:lista` — tabla: Conductor | Estado | Horas semana | Turnos | Doble turno.
- `conductores:detalle` — información personal, estadísticas (turnos, horas,
  operaciones), historial, documentos (reusa `documentos`), historial de nómina.

## 10. Módulo NÓMINA (Fase 4)

Respuesta: "¿Cuánto debo pagarle a cada conductor?"

- Ya existe: `nomina:lista`, `nomina:nueva` (período), `nomina:detalle` (relación por
  conductor con turnos y abonos), abono, `marcar_pagada`.
- El estado PENDIENTE/LIQUIDADO/PAGADO ya evita doble pago.
- Solo rediseño visual + asegurar que un turno anulado no genera nómina.

## 11. Módulo FACTURACIÓN (Fase 4)

Respuesta: "¿Cuánto puedo cobrarle al cliente?"

- `facturacion:resumen` (NUEVO) — resumen: valor trabajado, abonos, saldo por cobrar +
  tabla por operación (Horas | Valor trabajado | Abonos | Saldo).
- Existe: `facturacion:detalle` (por operación), `generar_billing`, `abono`, CSV.
- CSV: Fecha | Mula | Horas turno | Total horas, por operación (sin conductor).

## 12. Módulo DOCUMENTOS (Fase 7)

- Módulo recién construido; solo aplicar el shell nuevo. No hay cambios funcionales.

## 13. Módulo CONFIGURACIÓN (Fase 6)

Respuesta: "Parámetros que no deben mezclarse con la operación diaria."

- Operaciones: puertos, clientes/generadores de carga, tipos de operación.
- Turnos: tipos de turno, meta de horas, categorías de novedades (CRUD).
- Tarifas: puerto/operación → valor hora → valor turno (los distintos clientes no
  pagan igual).
- Documentos: tipos, obligatorios, vencimiento, días de alerta.
- Tablas destino: `catalogos.Port`, `catalogos.CargoGenerator`,
  `catalogos.IncidentCategory`, `documentos.DocumentType`.

## 14. Decisiones técnicas (todas aprobadas)

| # | Decisión | Estado |
|---|---|---|
| D1 | Agregar `Shift.valor_facturable` + `Shift.es_excepcion` (migración) | ✅ aprobado |
| D2 | Endpoint Gantt transversal por semana reusando `bloques_gantt`/`gantt.js` | ✅ aprobado |
| D3 | Turnos como módulo central transversal (página propia, no duplicado) | ✅ aprobado |
| D4 | Anular ≠ eliminar (`Shift.CANCELADO` con motivo) | ✅ aprobado |
| D5 | CSS puro con variables, `base.css` nuevo cargado tras `app.css` | ✅ aprobado |
| D6 | Sidebar definitiva con separadores (sección 5) | ✅ aprobado |
| D7 | Flota y Conductores obtienen listas mínimas (luego detalle) | ✅ aprobado |
| D8 | Facturación: crear página de resumen | ✅ aprobado |
| D9 | Login anónimo: sin sidebar | ✅ aprobado |

## 15. Orden de construcción (fases)

1. Fase 0 — Shell + Inicio (base.html, base.css, inicio.html, listas flota/conductores
   básicas para que la sidebar no tenga enlaces muertos).
2. Fase 1 — TURNOS (modelo D1 → lista/KPIs/tabla → registrar/editar/anular → Gantt D2).
3. Fase 2 — FLOTA (detalle).
4. Fase 3 — CONDUCTORES (detalle).
5. Fase 4 — NÓMINA + FACTURACIÓN (resumen).
6. Fase 5 — OPERACIONES (filtros + detalle enriquecido).
7. Fase 6 — CONFIGURACIÓN (CRUDs).
8. Fase 7 — DOCUMENTOS (solo shell).

Cada fase: prompt → IA externa genera → revisión e integración → página siguiente.
Cada fase con su propia spec/plan si lo requiere.

## 16. Fuera de alcance

- REPORTES (futuro; exportaciones CSV/Excel/PDF).
- Páginas de Flota/Conductores detalladas hasta sus respectivas fases.
- Supabase Storage (ya implementado en `documentos`; no cambia).
