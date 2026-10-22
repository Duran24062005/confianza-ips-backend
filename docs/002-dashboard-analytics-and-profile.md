# Dashboard analítico y perfil de usuario

## Problema y objetivo

El dashboard anterior exponía contadores básicos y el frontend dibujaba una barra estática. Esta capacidad agrega una respuesta analítica calculada desde citas persistidas, con alcance por rol y zona horaria institucional.

## Contrato

`GET /api/v1/dashboard/analytics?days=30`

`days` acepta valores entre 7 y 90. La respuesta incluye el alcance (`global`, `doctor` o `patient`), el periodo UTC equivalente a días calendario en `America/Bogota`, resumen, tendencia diaria, estados y servicios.

La tasa de asistencia se calcula como `completadas / (completadas + no asistió) * 100`. Si no existe historial suficiente, el valor es `null` y el frontend muestra un estado sin historial.

## Permisos y alcance

- `admin` y `receptionist`: todas las citas del sistema y conteos institucionales.
- `doctor`: citas donde `doctor_id` coincide con el usuario autenticado.
- `patient`: citas donde `patient_id` coincide con el vínculo del usuario.

Los pacientes y médicos no reciben los conteos globales de pacientes activos ni de médicos activos.

## Perfil

`PATCH /api/v1/auth/me` acepta `{ "full_name": "Nombre actualizado" }`. El nombre se valida, se persiste y genera un evento de auditoría sobre el recurso `user`. La edición administrativa del paciente continúa en `PATCH /api/v1/patients/me` y mantiene sus reglas actuales.

## Riesgos y compatibilidad

- `/api/v1/dashboard` se mantiene sin cambios para consumidores existentes.
- Las agregaciones se realizan en la capa de router usando entidades persistidas, lo que mantiene compatibilidad con SQLite de pruebas y PostgreSQL.
- El endpoint no inventa filas cuando el periodo está vacío: devuelve puntos diarios en cero y desgloses vacíos o con estados cero.
- Las fechas recibidas y almacenadas siguen siendo UTC; solo el límite de día y la agrupación visual usan `America/Bogota`.

## Validación

La suite cubre periodos inválidos, alcance global y personal, periodo local de siete días, ausencia de historial para la tasa de asistencia, actualización de nombre y auditoría.
