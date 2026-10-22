# PRD técnico — Alcance coherente de pacientes por rol

## Problema y objetivo

La agenda frontend carga pacientes para el médico porque el producto define que puede consultar sus pacientes autorizados, pero `GET /api/v1/patients` solo aceptaba administración y recepción. Esto producía un `403` visible durante una pantalla que el médico sí puede usar.

El objetivo es que la interfaz y la API compartan la misma regla: el personal administrativo ve el listado global y el médico ve únicamente los pacientes relacionados con sus citas.

## Alcance

- Permitir `GET /api/v1/patients` para `admin`, `receptionist` y `doctor`.
- Mantener la creación, edición y activación de pacientes limitada a `admin` y `receptionist`.
- Filtrar las respuestas del médico por pacientes que tengan al menos una cita con su `doctor_id`.
- Aplicar el mismo filtro de pertenencia a `GET /api/v1/patients/{patient_id}`.
- Mantener el acceso del paciente a sus endpoints `/patients/me`, sin habilitar listados globales.
- Alinear las acciones de estado visibles en la agenda con las transiciones permitidas por rol.
- Actualizar la guía pública del endpoint y cubrir el comportamiento con pruebas.

## Actores y reglas

| Rol | `GET /patients` | `GET /patients/{id}` | Escritura administrativa |
| --- | --- | --- | --- |
| Administrador | Todos los pacientes | Todos los pacientes | Sí |
| Recepcionista | Todos los pacientes | Todos los pacientes | Sí |
| Médico | Pacientes con citas propias | Solo pacientes con citas propias | No |
| Paciente | No | Solo su propio paciente mediante `/me` | Solo `/me` |

La relación operativa del médico se demuestra mediante `appointments.doctor_id`. Un paciente puede aparecer aunque sus citas sean históricas o estén canceladas, porque continúa siendo parte del contexto de atención del profesional; el filtro `active=true` sigue controlando si se devuelve un registro activo.

## Implementación y contrato

El backend conserva el contrato de ruta y de respuesta. La autorización se evalúa después de autenticar el usuario y antes de devolver datos:

- `GET /patients` usa una dependencia de lectura con los tres roles permitidos.
- Para médicos, la consulta hace `JOIN` con `appointments`, filtra por `user.doctor_id` y elimina duplicados.
- `GET /patients/{patient_id}` rechaza con `403` un paciente sin relación operativa con el médico.
- `POST`, `PUT` y `PATCH /patients/{id}/status` conservan la dependencia administrativa existente.

El frontend puede seguir cargando pacientes desde la agenda médica porque la respuesta queda limitada al alcance autorizado. La vista administrativa continúa siendo exclusiva de administración y recepción.

Las acciones de estado de la agenda también respetan el contrato: administración y recepción pueden confirmar o cancelar; el médico puede completar una cita confirmada. La interfaz no muestra botones para transiciones que el backend rechazaría.

## Validaciones

- Un médico recibe `200` y solo sus pacientes relacionados.
- Un médico no puede listar ni consultar pacientes sin una cita propia.
- Administración y recepción conservan el listado global.
- Un paciente no obtiene el listado global.
- Las pruebas existentes de escritura administrativa siguen requiriendo rol administrativo.
- La guía de endpoints refleja los roles y el filtro real.
- Un médico no ve acciones de confirmar o cancelar que terminarían en `403`; ve completar para una cita confirmada.

## Riesgos y límites

- Un médico sin citas relacionadas recibirá una lista vacía; la interfaz debe tratarla como estado vacío, no como error.
- Esta decisión no concede acceso a historia clínica: las rutas clínicas mantienen sus propias reglas de cita y profesional asignado.
- Si en el futuro se necesita un concepto de autorización independiente de las citas, deberá modelarse como una relación persistida propia y no inferirse de este listado.
