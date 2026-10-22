# PRD — Confianza IPS

## Problema y objetivo

Confianza necesita demostrar una operación institucional realista para una IPS ficticia: usuarios con permisos, pacientes, médicos, agendas, citas e historial persistidos en PostgreSQL.

## Alcance

El MVP incluye autenticación JWT, roles, catálogos, pacientes, agendas, citas, auditoría, dashboard, notas clínicas ficticias y una constancia imprimible de cita. Autorizaciones y PDF quedan implementados como capacidades secundarias.

## Reglas

- Los registros administrativos se desactivan, no se borran físicamente.
- Las citas activas no pueden solaparse para el mismo médico o paciente.
- Las citas completadas no se reprograman.
- Las atenciones clínicas solo pueden registrarlas médicos asociados a la cita.
- Todo cambio relevante registra actor, recurso, fecha y estado anterior/posterior.

## Seguridad y datos

Todos los datos son sintéticos. Las contraseñas se almacenan con Argon2id. El backend valida rol y pertenencia del recurso; el frontend nunca sustituye esas validaciones.

## Riesgos

La misma base Neon se utilizará para desarrollo y demostración por decisión del proyecto. El seed es idempotente y las pruebas destructivas deben ejecutarse contra una base o esquema aislado.
