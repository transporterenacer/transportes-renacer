# Nómina por saldo acumulado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrar la nómina de pago-semanal a saldo acumulado por conductor con FIFO por turno, pagos parciales y saldo a favor derivado.

**Architecture:** El `PayrollItem` persiste cuánto lleva cubierto cada turno (`pagado`). Una reconciliación FIFO idempotente (`recalcular_fifo`) reparte abonos+pagos sobre los turnos ordenados por antigüedad tras cada abono/pago/liquidación. `saldo_a_favor`, `saldo_pendiente`, `turnos_cubiertos` y `nomina_pendiente_actual` se derivan de `Σ(abonos+pagos)` y `Σ(valor)`/`Σ(pagado)`, sin columnas extra.

**Tech Stack:** Django 5.x, Python 3.13, SQLite (dev), templates DTL con locale `es-co`.

**Repo:** Sin git (local, no commits). Cada tarea termina ejecutando `manage.py test` para el módulo afectado.

## Global Constraints

- `PayrollItem.pagado` se persiste; `saldo_a_favor` NO (derivado en memoria).
- FIFO determinista: turnos ordenados por `(payroll__periodo_inicio, payroll__periodo_fin, shift__fecha_inicio, shift__fecha_fin, id)`; avances (abonos+pagos) ordenados por `(fecha, id)`.
- `registrar_pago`: solo `0 < valor <= saldo_pendiente`. `registrar_abono`: sin tope.
- `DriverAdvance` nuevos con `payroll=None`. Deja de existir `pagar_nomina`.
- Locale `es-co`: ancho de barras en templates vía `|stringformat:".0f"`/`.1f`, nunca `floatformat`.
- Servidor con `--noreload`; los cambios Python requieren reinicio manual al final.

---

### Task 1: Migración `0005` — `PayrollItem.pagado` + backfill FIFO

**Files:**
- Modify: `apps/nomina/models.py:44` (añadir campo `pagado`)
- Create: `apps/nomina/migrations/0005_payrollitem_pagado.py`

**Interfaces:**
- Produces: campo `PayrollItem.pagado` (Decimal, default 0); migración que deja `pagado` consistente con los `DriverAdvance` existentes.

- [ ] **Step 1: Añadir el campo al modelo**
```python
pagado = models.DecimalField(max_digits=14, decimal_places=0, default=0)
```
Colocado tras `valor`.

- [ ] **Step 2: Generar migración y añadir `RunPython` de backfill**
- [ ] **Step 3: Verificar**
Run: `python manage.py makemigrations nomina` (en `.venv`) y `python manage.py showmigrations nomina`.
Expected: aparece `0005` con el nuevo campo.

---

### Task 2: `recalcular_fifo` y derivados de saldo

**Files:**
- Modify: `apps/nomina/services.py` (tras `resumen_liquidacion`)

**Interfaces:**
- Produces:
  - `recalcular_fifo(driver) -> None` — idempotente, persiste `item.pagado`.
  - `saldo_conductor(driver) -> dict` con claves: `saldo_pendiente`, `saldo_a_favor`,
    `total_turnos`, `turnos_cubiertos`, `turnos_pendientes`, `items` (lista de dicts con
    `periodo`, `shift`, `valor`, `pagado`, `pendiente`, `estado`), `abonos`, `pagos`,
    `estado`.
  - `conductor_pagado(driver) -> bool` (saldo_pendiente == 0).

Implementación de `saldo_conductor`:
```python
def saldo_conductor(driver):
    recalcular_fifo(driver)
    items = (
        PayrollItem.objects.filter(shift__driver=driver)
        .select_related("shift", "shift__vehicle", "shift__operation", "payroll")
        .order_by("payroll__periodo_inicio", "payroll__periodo_fin",
                  "shift__fecha_inicio", "shift__fecha_fin", "id")
    )
    saldo_pendiente = Decimal(0)
    cubiertos = 0
    detalle = []
    for item in items:
        pendiente = item.valor - item.pagado
        if pendiente > 0:
            saldo_pendiente += pendiente
        if pendiente == 0:
            cubiertos += 1
        detalle.append({
            "periodo": item.payroll,
            "shift": item.shift,
            "valor": item.valor,
            "pagado": item.pagado,
            "pendiente": pendiente,
            "estado": "cubierto" if pendiente == 0 else "pendiente",
        })
    abonos, pagos = Decimal(0), Decimal(0)
    for adv in DriverAdvance.objects.filter(driver=driver):
        if adv.tipo == DriverAdvance.PAGO:
            pagos += adv.valor
        else:
            abonos += adv.valor
    total_valor = sum(i.valor for i in detalle) if detalle else Decimal(0)
    recibido = abonos + pagos
    saldo_a_favor = max(Decimal(0), recibido - total_valor)
    return {
        "saldo_pendiente": saldo_pendiente,
        "saldo_a_favor": saldo_a_favor,
        "total_turnos": len(detalle),
        "turnos_cubiertos": cubiertos,
        "turnos_pendientes": len(detalle) - cubiertos,
        "items": detalle,
        "abonos": abonos,
        "pagos": pagos,
        "estado": "pagado" if saldo_pendiente == 0 else "pendiente",
    }
```
`recalcular_fifo` se implementa con los órdenes FIFO definidos en Constraints y escribe
`item.pagado` (solo save de los cambiados).

- [ ] **Step 1: escribir tests (Task 4 antes de Task 5: escribir tests primero)**
- [ ] **Step 2–4: implementar y verificar**

---

### Task 3: `registrar_abono`, `registrar_pago`, `nomina_pendiente_actual`, `crear_liquidacion`

**Files:**
- Modify: `apps/nomina/services.py` (reescribir `registrar_abono`, `registrar_pago`;
  sustituir `pendiente_total` por `nomina_pendiente_actual`; añadir validación de solape
  en `crear_liquidacion`; quitar `pagar_nomina`; `resumen_liquidacion`/`estado_nomina`
  pasan a leer `item.pagado`; `conductor_pagado` pasa a driver-solo).

**Interfaces:**
- `registrar_abono(driver, valor, descripcion="", fecha=None, usuario=None) -> DriverAdvance` (payroll=None).
- `registrar_pago(driver, valor, metodo=EFECTIVO, usuario=None) -> DriverAdvance` (valida tope).
- `nomina_pendiente_actual() -> Decimal`. Implementación:
```python
def nomina_pendiente_actual():
    agg = PayrollItem.objects.aggregate(
        total=Sum("valor"), pagado=Sum("pagado")
    )
    return (agg["total"] or Decimal(0)) - (agg["pagado"] or Decimal(0))
```
- `crear_liquidacion(desde, hasta, usuario=None)`: rechaza si existe otro `Payroll`
  cuyo rango solape `(desde, hasta)`; al final itera los conductores de los items y
  ejecuta `recalcular_fifo`.
- `resumen_liquidacion(payroll)`: pagos por conductor = Σ de `item.pagado`; columnas
  `cubierto` (item.pagado) y `pendiente` (valor − pagado).
- `estado_nomina(payroll)`: `total`=Σ valor, `pagos`(=cubierto)=Σ pagado, `pendiente`=
  total−pagos; `porcentaje` desde pagos/total; estado derivado por conductor (todos
  cubiertos → pagado; alguno → parcial; ninguno → pendiente).

- [ ] **Step 1–2: escribir tests y verificar que fallan**
- [ ] **Step 3–4: implementar y verificar**

---

### Task 4: Tests de servicios

**Files:**
- Modify: `apps/nomina/tests/test_services.py` (ajustar firmas antiguas)
- Add tests: FIFO por antigüedad, abono suelto antes de liquidar que cubre turnos al
  liquidar, pago parcial deja pendiente por turno, saldo a favor cuando abono > devengado,
  multi-período, validación de solape, `nomina_pendiente_actual`.

- [ ] Redactar y ejecutar; suite `apps.nomina` verde.

---

### Task 5: Vistas y URLs

**Files:**
- Modify: `apps/nomina/views.py`, `apps/nomina/urls.py`

**URLs resultantes:**
```
nomina:conductor            -> conductores/<int:driver_pk>/
nomina:abono_conductor_nuevo-> conductores/<int:driver_pk>/abonos/nuevo/
nomina:pago_nuevo           -> conductores/<int:driver_pk>/pagos/nuevo/
nomina:detalle, lista, nueva, exportar sin cambios de patrón
Se elimina nomina:pagar (pagar_seleccionados).
```
- `conductor_detail(request, driver_pk)`: usa `saldo_conductor(driver)`; renderiza
  `nomina/conductor_detail.html` con `saldo`, `driver`, `abono_form`, `pago_form`.
- `abono_nuevo(request, driver_pk)`: `registrar_abono(driver, ...)`.
- `pago_nuevo(request, driver_pk)`: `registrar_pago(driver, ...)`.
- `payroll_list`: KPIs nuevos `pendiente_global` (`nomina_pendiente_actual()`) y
  `conductores_pendientes` (nº de conductores con saldo pendiente > 0); conservar
  navegación semanal, alertas, historial.
- `exportar_csv`: columna "Pagos" → "Cubierto (FIFO)" usando `item.pagado`.

- [ ] Ejecutar tests de vistas (Task 6).

---

### Task 6: Tests de vistas

**Files:**
- Modify: `apps/nomina/tests/test_views.py`
- Ajustar por URLs nuevas (p. ej. `reverse("nomina:conductor", args=[driver.pk])`,
  `reverse("nomina:pago_nuevo", args=[driver.pk])`), eliminar test de `pagar_seleccionados`,
  adaptar `test_pago_duplicado_bloqueado` (pago > saldo → sigue con 200 y mensaje).

- [ ] Suite `apps.nomina` verde.

---

### Task 7: Templates

**Files:**
- Modify: `templates/nomina/conductor_detail.html` (rediseño completo)
- Modify: `templates/nomina/payroll_detail.html` (sin batch; columnas cubierto/pendiente)
- Modify: `templates/nomina/payroll_list.html` (KPIs acumulados; enlaces a conductor nuevo)
- Modify: `templates/dashboard/inicio.html` (KPI "Nómina pendiente (acumulado)")

**conductor_detail.html:** KPI grande saldo pendiente; KPI saldo a favor; badge estado;
3 cards KPIs (turnos cubiertos, turnos pendientes, total turnos); tabla de turnos con
período semanal y saldo por turno; tablas de abonos y pagos; formularios de pago
(`pago_form.valor` localizado, monto por defecto = saldo pendiente) y abono; botón volver
a lista.

- [ ] Render 200 de `/nomina/`, `/nomina/<pk>/`, `/nomina/conductores/<pk>/`, Home.

---

### Task 8: seed_demo.py y dashboard

**Files:**
- Modify: `seed_demo.py` (sustituir `pagar_nomina` por pagar por conductor con
  `registrar_pago`; `resumen_liquidacion` columnas nuevas)
- Modify: `apps/dashboard/services.py` (importar `nomina_pendiente_actual`)
- Modify: `templates/dashboard/inicio.html`

---

### Task 9: Verificación final

- [ ] `python manage.py test` (suite completa) — verde.
- [ ] `python manage.py migrate` en dev.
- [ ] Reiniciar servidor limpio (matar PIDs duplicados del puerto 8000, levantar uno).
- [ ] Verificar por HTTP/KPI: Home muestra pendiente acumulado; páginas 200.