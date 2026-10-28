# Contrato de despliegue Confianza IPS para Waylo

**Fecha:** 2026-10-28
**Repositorio:** `confianza-ips-backend`

## Variables server-side

El endpoint `POST /api/v1/integrations/agent/token` requiere en el mismo entorno:

- `AGENT_API_KEY`
- `AGENT_ACTIVATION_SECRET`
- `AGENT_JWT_SECRET`
- `DATABASE_URL`

`AGENT_API_KEY` debe ser exactamente igual a `CONFIANZA_AGENT_KEY` del adaptador
Waylo. Las claves JWT normal y de agente son independientes. Ninguna debe publicarse
en el frontend institucional ni en el repositorio.

## Contrato HTTP

Waylo envía:

```text
POST /api/v1/integrations/agent/token
X-Confianza-Agent-Key: <AGENT_API_KEY>
Content-Type: application/json
```

con `document_type`, `document_number`, `eps` y `activation_code`. El código es
temporal y de un solo uso. Un documento, EPS, código o clave de agente inválidos deben
rechazarse sin revelar cuál de ellos falló.

El token emitido es de paciente y solo puede consultar los recursos permitidos por el
contrato de agente. Waylo conserva el token cifrado en su backend; Confianza nunca debe
enviarlo al navegador ciudadano.

## CORS y frontend institucional

`CORS_ORIGINS` debe incluir la URL de `confianza-ips-frontend` y cualquier origen local
usado para pruebas. Esto permite el dashboard institucional, pero no sustituye la
autenticación del agente server-to-server.

## Validación de despliegue

- `/health` confirma disponibilidad básica.
- `GET /health/ready` confirma acceso a la base.
- La suite `tests/test_agent.py` cubre código temporal, clave de agente, alcance de
  paciente y uso único.
- La prueba real con Waylo requiere una base con paciente activo, una cuenta de
  paciente y un código recién generado desde Confianza.
