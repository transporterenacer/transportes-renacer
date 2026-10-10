# Módulo Viajes Locales — Transportes Renacer

**Fecha:** 2026-10-10
**Estado:** Aprobado por el usuario
**Alcance:** Modelo `Viaje` separado de `Operation`, integrado a nómina, facturación y gastos. UI híbrida.

## Contexto

La plataforma fue diseñada para operación portuaria (turnos por hora, buque, puerto). El negocio también realiza **fletes locales** (ciudad a ciudad) con las mismas mulas y conductores. Se requiere registrar esos viajes, cobrarlos al cliente con valor libre, pagar un valor fijo al conductor, liquidarlo en la misma nómina semanal y cargarles gastos (ACPM, peaje, etc.).

## Decisiones fijadas

1. **Modelo separado `Viaje`** en `apps/operaciones` (no se estira `Operation`).
2. **Valor cobrado libre** por viaje (el usuario lo digita).
3. **Valor conductor fijo** por viaje (el usuario lo digita).
4. **Cliente** = reutiliza catálogo `CargoGenerator` (FK).
5. **Pago del conductor entra a la nómina semanal** (`PayrollItem`).
6. **Gastos** se cargan al viaje con el mismo formulario/categorías que los de operación (`OperationExpense` extendido).
7. **UI híbrida**: en Operaciones, botón "Nueva operación" pregunta Portuaria/Local; Local abre el formulario de Viaje. Menú lateral "Viajes" para listado.
8. **Facturación**: al finalizar un viaje se crea un registro por `valor_cobrado` (sin horas ni tarifa_hora).
9. **Seed**: agrega viajes de ejemplo (uno finalizado liquidado, uno en curso) con gastos.

## Modelo `Viaje`

| Campo | Tipo | Notas |
|-------|------|-------|
| `codigo` | CharField(20, unique) | Auto: `VJ-AAAA-NNN` |
| `cliente` | FK `CargoGenerator` | PROTECT |
| `vehicle` | FK `Vehicle` | PROTECT |
| `driver` | FK `Driver` | PROTECT |
| `origen` | CharField(120) | Ej. "Barranquilla" |
| `destino` | CharField(120) | Ej. "Cartagena" |
| `fecha_ida` | DateTimeField | |
| `fecha_vuelta` | DateTimeField | validada > fecha_ida |
| `valor_cobrado` | Decimal(14,0) | lo que paga el cliente |
| `valor_conductor` | Decimal(14,0) | lo que recibe el conductor |
| `estado` | CharField | `pendiente`/`en_viaje`/`finalizado`/`cancelado` |
| `observaciones` | TextField | blank |

- Extiende `AuditMixin`.
- `clean()`: `fecha_vuelta > fecha_ida`; `valor_cobrado > 0`; `valor_conductor > 0`.
- `save()`: al pasar a `FINALIZADO` no cambia valores automáticamente (la facturación y la liberación de la mula se hacen en el service).

## Cambios en modelos existentes

### `PayrollItem` (`apps/nomina/models.py`)
- `shift`: **nullable=True** (antes obligatorio).
- Nuevo campo `viaje`: FK `Viaje`, nullable, `on_delete=PROTECT`, `related_name="payroll_items"`.
- `clean()` / constraint: exactamente uno de (`shift`, `viaje`).
- `__str__` y `resumen_liquidacion` deben tolerar items con `viaje`.
- `horas` del resumen: viajes suman 0 horas (no aplican).

### `OperationExpense` (`apps/operaciones/models.py`)
- `operation`: **nullable=True**.
- Nuevo campo `viaje`: FK `Viaje`, nullable, `on_delete=PROTECT`, `related_name="expenses"`.
- Constraint: exactamente uno de (`operation`, `viaje`).
- `vehicle` sigue obligatorio (la mula del viaje).

### `BillingRecord` (`apps/facturacion/models.py`)
- `operation`: **nullable=True**.
- Nuevo campo `viaje`: FK `Viaje`, nullable, `on_delete=PROTECT`, `related_name="billing_records"`.
- Constraint: exactamente uno de (`operation`, `viaje`).
- Cuando `viaje` esté seteado: `horas=0`, `tarifa_hora=0`, `valor=viaje.valor_cobrado`.
- `ClientPayment` NO se extiende (los viajes locales no tienen abonos parciales en fase 1; se factura el total al finalizar).

## Servicios nuevos (`apps/operaciones/services.py`)

```python
def generar_numero_viaje(anio) -> str          # "VJ-2026-001", patrón correlativo existente
def crear_viaje(*, cliente, vehicle, driver, origen, destino,
                fecha_ida, fecha_vuelta, valor_cobrado, valor_conductor,
                usuario=None) -> Viaje         # valida solape de vehículo/conductor, crea PENDIENTE
def iniciar_viaje(viaje, usuario=None)         # PENDIENTE -> EN_VIAJE, marca vehículo EN_OPERACION
def finalizar_viaje(viaje, usuario=None)       # EN_VIAJE -> FINALIZADO, libera vehículo,
                                               # crea BillingRecord por valor_cobrado
def cancelar_viaje(viaje, motivo, usuario=None) # bloquea si tiene payroll_items; libera vehículo
def viajes_pendientes_pago(desde, hasta)       # Viaje FINALIZADO, fecha_vuelta en rango,
                                               # payroll_items__isnull=True
```

Validaciones (ValidationError en español):
- `fecha_vuelta <= fecha_ida`
- Solape: vehículo o conductor con otro viaje en estados PENDIENTE/EN_VIAJE que solape en el tiempo
- `finalizar_viaje` solo desde EN_VIAJE
- `cancelar_viaje` bloquea si `viaje.payroll_items.exists()`

## Integración nómina (`apps/nomina/services.py`)

- `turnos_pendientes_pago(desde, hasta)`: se mantiene solo para turnos.
- Nueva `viajes_pendientes_pago(desde, hasta)`.
- `crear_liquidacion(desde, hasta, usuario=None)`:
  1. Combina turnos pendientes + viajes pendientes.
  2. Si ambos vacíos → ValidationError.
  3. Crea `Payroll` y un `PayrollItem` por turno (shift=...) y por viaje (viaje=..., valor=viaje.valor_conductor).
  4. `resumen_liquidacion`: agrupa por conductor considerando `item.shift` o `item.viaje`; `horas` suma solo turnos.
- `recalcular_fifo`: no cambia (trabaja sobre `PayrollItem` genérico).

## Integración facturación (`apps/facturacion/services.py`)

- `finalizar_viaje` crea `BillingRecord(viaje=viaje, operation=None, horas=0, tarifa_hora=0, valor=viaje.valor_cobrado, estado=PENDIENTE, numero_relacion=f"VJ-{viaje.codigo}")`.
- `saldo_operacion` y KPIs de operación NO cambian (viaje no es operación).
- `kpis_facturacion` / `alertas_facturacion`: se agregan viajes con saldo pendiente (opcional fase 1; se documenta como pendiente si no).

## Integración gastos

- `OperationExpenseForm` acepta kwarg `viaje=None` además de `operation=None`; restringe `vehicle` a la mula del viaje.
- Vistas de gastos de viaje: `viaje_gasto_lista`, `viaje_gasto_nuevo`, `viaje_gasto_editar`, `viaje_gasto_eliminar` (clonadas de las de operación).
- `dashboard.kpis_gastos`: se suma `OperationExpense.objects.filter(viaje__isnull=False)` en el total (o se deja documentado; decisión: se suma al total global).

## URLs y vistas (`apps/operaciones/urls.py` + `views.py`)

| path | view | name |
|------|------|------|
| `viajes/` | `viaje_lista` | `viaje_lista` |
| `viajes/nuevo/` | `viaje_nuevo` | `viaje_nuevo` |
| `viajes/<int:pk>/` | `viaje_detalle` | `viaje_detalle` |
| `viajes/<int:pk>/iniciar/` | `viaje_iniciar` | `viaje_iniciar` |
| `viajes/<int:pk>/finalizar/` | `viaje_finalizar` | `viaje_finalizar` |
| `viajes/<int:pk>/cancelar/` | `viaje_cancelar` | `viaje_cancelar` |
| `viajes/<int:pk>/gastos/` | `viaje_gasto_lista` | `viaje_gastos` |
| `viajes/<int:pk>/gastos/nuevo/` | `viaje_gasto_nuevo` | `viaje_gasto_nuevo` |
| `viajes/<int:pk>/gastos/<int:gasto_pk>/editar/` | `viaje_gasto_editar` | `viaje_gasto_editar` |
| `viajes/<int:pk>/gastos/<int:gasto_pk>/eliminar/` | `viaje_gasto_eliminar` | `viaje_gasto_eliminar` |

- Todas con `@login_required`; acciones de estado (iniciar/finalizar/cancelar) con `@role_required("Admin", "Secretaria")`.
- Vistas FBV, Post/Redirect/Get, `messages.success`, errores de dominio → `operaciones/error.html` status 409 (o `form.add_error`).

## UI híbrida

- `templates/operaciones/operacion_list.html`: el botón "Nueva operación" (o el `topbar_action`) abre un pequeño selector: **Portuaria** (link al form actual) | **Local** (link a `operaciones:viaje_nuevo`).
- `templates/base.html`: ítem de menú "Viajes" en el bloque Admin+Secretaria, junto a Operaciones. Icono `local_shipping` o `route`.
- Templates nuevos: `templates/operaciones/viaje_list.html`, `viaje_detail.html`, `viaje_form.html`.
- `viaje_detail.html`: datos del viaje, estado con botones de acción, gastos del viaje, resumen financiero (valor cobrado, costo gastos, valor conductor, resultado).
- `viaje_form.html`: campos cliente, vehículo (mulas disponibles), conductor, origen, destino, fecha_ida/vuelta (datetime-local), valor_cobrado, valor_conductor, observaciones. Código auto (no se digita).

## Formularios (`apps/operaciones/forms.py`)

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
            ...
        }
    def __init__(self, *args, **kwargs):
        # vehicle: solo DISPONIBLES; driver: solo activos
```

## Dashboard

- `kpis_inicio` (fase 1, mínimo): se agrega "Viajes locales activos" (count EN_VIAJE + PENDIENTE) y opcional "Fletes del mes".
- Si el tiempo aprieta, se deja para fase 2 y se documenta.

## Seed (`seed_demo.py`)

Agregar:
- 1 viaje FINALIZADO (hace ~10 días) con 2 gastos (ACPM, peaje) — ya liquidado en la nómina de ejemplo.
- 1 viaje EN_VIAJE (iniciado hace 2 días).
- 1 viaje PENDIENTE (sale mañana).

## Migraciones

1. `operaciones`: crea `Viaje`; altera `OperationExpense` (operation nullable + viaje).
2. `nomina`: altera `PayrollItem` (shift nullable + viaje).
3. `facturacion`: altera `BillingRecord` (operation nullable + viaje).

Constraints: `CheckConstraint` para "exactamente uno" en las tres tablas (o `clean()` + validación en forms/services; se prefiere CheckConstraint + validación).

## Criterios de aceptación

- [ ] Se puede crear, iniciar, finalizar y cancelar un viaje desde la UI.
- [ ] El viaje finalizado crea `BillingRecord` por `valor_cobrado`.
- [ ] `crear_liquidacion` incluye viajes finalizados no liquidados del periodo.
- [ ] Se pueden cargar gastos a un viaje con las mismas categorías.
- [ ] La UI híbrida pregunta Portuaria/Local y lleva al formulario correcto.
- [ ] El menú lateral muestra "Viajes".
- [ ] El seed crea viajes de ejemplo coherentes.
- [ ] Tests unitarios de modelos, services y views pasan.
- [ ] No se rompe ningún test existente.

## Fuera de alcance (fase 2)

- Abonos/anticipos del cliente por viaje (`ClientPayment` para viajes).
- Ruta en mapa / cálculo automático de distancia.
- KPIs avanzados de fletes en dashboard.
- App móvil / seguimiento GPS.
