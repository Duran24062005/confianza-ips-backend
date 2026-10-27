# PRD técnico — Registro público de pacientes para la demostración

## Problema y objetivo

El acceso institucional solo ofrecía cuentas seed. Esto impedía crear identidades de paciente adicionales para comprobar el flujo de activación de Waylo sin modificar datos existentes.

El objetivo es permitir un alta autocontenida de **pacientes ficticios** que pueda iniciar sesión de inmediato y generar su código temporal del agente.

## Alcance y actores

- Un visitante puede enviar `POST /api/v1/auth/register` sin JWT.
- El servidor crea un `Patient` activo y un `User` asociado con rol `patient`.
- Administración, recepción y médicos siguen creándose únicamente mediante los flujos internos protegidos.
- El endpoint es exclusivo de esta demostración; no sustituye una admisión ni una verificación de identidad institucional real.

## Contrato y reglas

El payload incluye los campos administrativos obligatorios de un paciente y una contraseña de mínimo ocho caracteres. El correo se normaliza a minúsculas y el nombre visible se deriva de nombres y apellidos.

El backend rechaza correo duplicado y la combinación de tipo/número de documento duplicada con `409`. El rol no forma parte del payload y se fuerza en el servidor a `patient`. La creación del paciente, la cuenta y el evento de auditoría se confirman en una única transacción antes de emitir el JWT de sesión.

## Seguridad y límites

- La contraseña se conserva solo como hash Argon2id mediante la política existente.
- La respuesta no expone `patient_id`, hash, datos de otros pacientes ni credenciales de integración.
- La cuenta resultante mantiene el alcance de paciente: solo sus datos, agenda e información clínica autorizada.
- El código de activación y `AGENT_API_KEY` siguen siendo mecanismos distintos; el registro nunca genera ni revela la credencial del agente.

## Validación

- Alta válida devuelve `201` y un JWT que resuelve `/auth/me` como `patient`.
- Correos y documentos duplicados devuelven `409` sin crear una segunda identidad.
- El flujo frontend exige los campos administrativos, confirma la contraseña y muestra errores del backend.
