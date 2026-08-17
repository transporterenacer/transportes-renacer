# Nómina por saldo acumulado del conductor — Spec

**Fecha:** 2026-08-16
**Estado:** Aprobado por el usuario.

## Contexto

El módulo de nómina liquidaba y pagaba semana a semana (Payroll = período fijo de pago).
El negocio real no funciona así: los turnos se registran manualmente, hay retrasos y
correcciones, y el pago a conductores puede ser total o parcial, sin estar atado a la
semana en la que se trabajó. Se migra a un modelo de **saldo acumulado por conductor**.

## Reglas de negocio

1. **Payroll es solo un agrupador.** Los turnos se agrupan en períodos semanales
   (manual, "Nueva liquidación") para mantener trazabilidad. No significa pago ni
   bloquea nada.
2. **Creación manual con captura automática.** La secretaria elige el período; el
   sistema incorpora automáticamente todos los turnos `REALIZADO` del rango que aún
   no estén en un Payroll. Validación: **no se admiten períodos solapados**.
3. **El saldo entra al liquidar.** Un turno alimenta el saldo del conductor cuando
   entra a un `PayrollItem`.
4. **Saldo acumulado por conductor** = Σ(`item.valor − item.pagado`) sobre todos sus
   turnos agrupados, sin importar la semana.
5. **Pago parcial/conductor.** Un pago puede ser total o parcial (siempre `0 < valor ≤
   saldo pendiente`). El estado **PAGADO** es: saldo pendiente == 0.
6. **FIFO determinista.** Los abonos y pagos se aplican primero al turno más antiguo
   del conductor y continúan cronológicamente hasta consumir el valor. La cobertura
   queda persistida en `PayrollItem.pagado`.
7. **Abono sin tope.** Un adelanto puede superar el saldo pendiente: el excedente se
   muestra como **saldo a favor del conductor** (valor derivado, no almacenado) y se
   descuenta automáticamente (FIFO) de turnos futuros cuando se liquiden.
8. **Saldo a favor** = `max(0, Σ abonos+pagos − Σ item.valor)`. Derivado, sin campo.
9. El Home muestra **"Nómina pendiente (acumulado)"** = Σ global (`valor − pagado`).

## Vistas del conductor

`nomina:conductor/<driver_pk>/` muestra: saldo pendiente (KPI), saldo a favor (KPI),
turnos cubiertos/pendientes, tabla por turno (fecha, operación, mula, horas, valor,
período semanal, pagado FIFO, saldo por turno), todos los abonos y pagos, saldo
restante. Botones: **Pagar** (monto libre, validado) y **Registrar abono**.

## Restricciones técnicas

- `PayrollItem.pagado = DecimalField(max_digits=14, decimal_places=0, default=0)`.
- `saldo_a_favor` es derivado; no crear columna.
- Locale `es-co`: en templates, `width: X%` usa `|stringformat:".1f"` (o `.0f`).
- Los `DriverAdvance` nuevos se crean con `payroll=None` (suelto); la columna `payroll`
  se conserva nullable por compatibilidad con registros históricos.
- Se elimina `pagar_nomina` (pago por lote de semana). `conductor_pagado()` pasa a
  depender solo del saldo del conductor.