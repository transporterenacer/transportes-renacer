# Guía de Presentación — Transportes Renacer

Sistema de gestión de transporte portuario para **Transportes Renacer**, Barranquilla, Colombia.

---

## 1. Preparación antes de la demo

1. **Levantar el servidor** con datos de demostración:
   ```
   python manage.py migrate
   python manage.py seed_demo
   python manage.py runserver
   ```
2. **Abrir el navegador** en `http://localhost:8000` y verificar que el login funcione.
3. **Iniciar sesión** con el usuario `admin`.
4. **Verificar el panel de control**: debe mostrar KPIs con datos, operaciones activas y alertas de documentos.
5. **Revisar cada módulo** rápidamente para confirmar que no hay errores visibles ni pantallas vacías.
6. **Tener pestañas preparadas** con el dashboard y la lista de operaciones.
7. **Testear el flujo completo** antes de presentar: crear un turno, revisar documentos, verificar nómina.

---

## 2. Orden de presentación (Hoja de ruta)

### Primera reunión (30–45 min)

| # | Módulo | Tiempo | Qué se muestra |
|---|--------|--------|----------------|
| 1 | Panel de control | 5 min | KPIs: operaciones activas, mulas en operación, horas trabajadas, nómina pendiente |
| 2 | Operaciones | 10 min | Operación activa, flujo: crear → asignar mulas → registrar turnos. Formulario de turno con calendario y paradas |
| 3 | Flota | 5 min | Lista de mulas, estados (en operación, disponible, taller). Documentación adjunta |
| 4 | Conductores | 5 min | Lista de conductores y su documentación |
| 5 | Documentos | 5 min | Panel de vencimientos. Alertas de SOAT, tecnomecánica próximos a vencer |

### Segunda reunión (si hay tiempo o en otra sesión)

| # | Módulo | Qué se muestra |
|---|--------|----------------|
| 6 | Nómina | Liquidación semanal, pagos, anticipos |
| 7 | Facturación | Relaciones de cobro, abonos, saldo por operación |
| 8 | Línea de tiempo | Vista Gantt de turnos por operación |
| 9 | Configuración | Catálogos maestros |

---

## 3. Talking points por módulo

### Panel de control

- **Qué decir:** "Aquí ve todo de un solo vistazo: cuántas operaciones tiene activas, cuántas mulas están trabajando y cuánto dinero debe la semana."
- **Qué mostrar:** Los cuatro KPIs principales, la lista de operaciones activas con barras de progreso, el estado de la flota y las alertas de vencimiento.
- **Qué evitar:** No explicar cómo se calculan los KPIs a nivel técnico.

### Operaciones

- **Qué decir:** "Registra el turno como le dan la información en el vale: hora de inicio, hora de fin, y si hubo vacancia. El sistema calcula las horas solo."
- **Qué mostrar:** Una operación activa con mulas asignadas, el formulario de registro de turno con calendario, selector de horas y las paradas del puerto.
- **Qué evitar:** No mencionar modelos de base de datos ni relaciones técnicas.

### Flota

- **Qué decir:** "Ve en tiempo real cuántas mulas tiene trabajando, cuáles están disponibles y cuáles están en el taller."
- **Qué mostrar:** La lista de vehículos con su estado, placa, modelo y documentación adjunta.
- **Qué evitar:** No mostrar el formulario de creación de vehículos a menos que el cliente pregunte.

### Conductores

- **Qué decir:** "Toda la información de sus conductores está centralizada: documento, licencia y contacto."
- **Qué mostrar:** La lista de conductores y la documentación de cada uno.
- **Qué evitar:** No mostrar campos técnicos como ID interno o fecha de creación.

### Documentos

- **Qué decir:** "Nunca más se le vence un SOAT sin avisar. El sistema le avisa con anticipación."
- **Qué mostrar:** El panel de vencimientos con las alertas de SOAT y tecnomecánica. Mostrar los colores: rojo para vencido, naranja para próximo a vencer.
- **Qué evitar:** No mostrar los tipos de documento disponibles ni la configuración de días de anticipación.

### Nómina (segunda reunión)

- **Qué decir:** "La nómina se liquenda automáticamente cada semana. Solo revisa y aprueba."
- **Qué mostrar:** Una liquidación semanal con los conductores, horas trabajadas y valores a pagar.
- **Qué evitar:** No mostrar el proceso técnico de cálculo.

### Facturación (segunda reunión)

- **Qué decir:** "Sabe exactamente cuánto le deben por cada operación y cuánto le han abonado."
- **Qué mostrar:** Las relaciones de cobro por operación, abonos registrados y saldo pendiente.
- **Qué evitar:** No mostrar la lógica de generación automática de facturación.

### Línea de tiempo (segunda reunión)

- **Qué decir:** "Ve en una sola pantalla cuándo trabaja cada mula durante la semana."
- **Qué mostrar:** La vista Gantt con los turnos asignados por operación.
- **Qué evitar:** No explicar cómo se genera el gráfico.

---

## 4. Flujo narrativo completo

**Guión paso a paso para narrar la demo:**

1. **Abrir con:** "Este es el centro de control de su operación."
2. **Mostrar dashboard:** "Aquí ve todo cada mañana. Las operaciones activas, las mulas trabajando, las horas de la semana y cuánto va a pagar en nómina."
3. **Ir a operaciones:** "Estas son sus operaciones activas. Cada buque que está descargando es una operación."
4. **Abrir una operación:** "Aquí ve las mulas asignadas y los turnos registrados. Cada turno es un día de trabajo de una mula."
5. **Registrar un turno nuevo:** "Así se registra un turno nuevo. Selecciona la fecha, la hora de inicio y de fin, y el sistema calcula las horas automáticamente."
6. **Ir a documentos:** "Y aquí nunca se le vence un documento sin aviso. El sistema le muestra cuáles están por vencer y cuáles ya vencieron."
7. **Cerrar con:** "Todo esto centralizado, sin papeles, sin errores de cálculo, sin surprises al final del mes."

---

## 5. Errores comunes a evitar

- **No mostrar el admin de Django** (`/admin/`). El cliente no debe ver esa interfaz.
- **No mostrar errores de consola.** Si hay errores, resolverlos antes de la demo.
- **No explicar la arquitectura técnica.** No mencionar Django, Python, bases de datos ni servidores.
- **No mencionar que es "un proyecto en desarrollo".** Se presenta como un sistema listo.
- **No navegar a módulos que no estén listos.** Si un módulo tiene problemas, saltarlo.
- **No mostrar datos vacíos.** Siempre ejecutar `seed_demo` antes de presentar.
- **No usar jerga técnica.** Usar语言aje del negocio: "turnos", "mulas", "operaciones", "vales".

---

## 6. Hoja de ruta para siguientes reuniones

| Reunión | Enfoque | Módulos |
|---------|---------|---------|
| **Reunión 1** | Visión general y operaciones | Dashboard, Operaciones, Flota, Conductores, Documentos |
| **Reunión 2** | Gestión financiera | Nómina, Facturación |
| **Reunión 3** | Configuración y capacitación | Configuración, Catálogos, Ajustes, Capacitación de usuario |
| **Reunión 4** | Pruebas y puesta en producción | Pruebas finales, migración de datos, capacitación completa |

---

## 7. Preguntas frecuentes del cliente

| Pregunta | Respuesta |
|----------|-----------|
| ¿Puedo usarlo en el celular? | Sí, el sistema se adapta a pantallas pequeñas. Puede revisar el dashboard y operaciones desde su celular. |
| ¿Necesito internet? | Solo para guardar datos en la nube. En el servidor local funciona sin conexión a internet. |
| ¿Cuánto cuesta? | [A definir — placeholder para cotización] |
| ¿Puedo agregar más conductores? | Sí, desde el módulo de Conductores puede registrar nuevos conductores con su documentación. |
| ¿Puedo agregar más mulas? | Sí, desde el módulo de Flota. Cada mula se registra con placa, marca, modelo y año. |
| ¿Qué pasa si se me daña la computadora? | Se realiza un respaldo periódico de la base de datos. Los datos se pueden restaurar en una nueva computadora. |
| ¿Puedo modificar los turnos después de registrarlos? | Sí, puede editar la información de un turno si detecta un error. |
| ¿El sistema calcula la nómina solo? | Sí, la nómina se liquenda automáticamente cada semana con los turnos registrados. |
| ¿Puedo ver reportes? | Sí, el dashboard muestra resúmenes semanales. En futuras versiones se agregarán reportes exportables. |
| ¿Necesito capacitar a mi equipo? | Sí, recomendamos una sesión de capacitación de 1-2 horas con el equipo que usará el sistema. |

---

*Documento generado para Transportes Renacer — Barranquilla, Colombia.*
