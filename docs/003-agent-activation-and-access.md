# PRD — Activación segura del agente y acceso del paciente

## Problema y objetivo

Confianza IPS necesita permitir que un paciente active nuestro agente sin entregar su contraseña institucional. El paciente genera una clave temporal desde su dashboard y el agente la combina con documento, EPS y una API key propia para obtener una sesión limitada al paciente identificado.

El objetivo es permitir consultas y operaciones reales del rol paciente —como solicitar, cancelar o reprogramar citas según las reglas existentes— manteniendo aislamiento por paciente, expiración corta y trazabilidad.

El triage de urgencia, moderado o no urgente no forma parte de este contrato. Será una capacidad posterior con reglas clínicas, advertencias y auditoría propias.

## Actores y alcance

- **Paciente activo:** genera una clave de seis dígitos desde el dashboard.
- **Agente autorizado:** presenta su API key y los datos entregados por el paciente para obtener un JWT temporal.
- **Sistema interno:** valida la sesión, afiliación y estado de la cuenta.
- **Usuario no afiliado:** puede utilizar capacidades públicas futuras, pero no puede consultar ni modificar datos personales ni servicios de una IPS.

El token del agente hereda el alcance efectivo del rol `patient` y queda restringido al paciente del token. No puede administrar usuarios, consultar listados globales, acceder a auditoría, crear atenciones médicas ni consultar pacientes terceros.

## Contrato HTTP

### Generar clave de activación

`POST /api/v1/integrations/agent/activation-code`

Requiere un JWT interno de un paciente activo.

Respuesta:

```json
{
  "code": "123456",
  "expires_at": "2026-10-23T15:05:00Z",
  "expires_in": 300,
  "single_use": true
}
```

Cada generación revoca la clave anterior del paciente. El servidor persiste únicamente un digest HMAC. La clave se consume al emitir el token o queda inutilizable al vencer.

### Emitir token del agente

`POST /api/v1/integrations/agent/token`

Header obligatorio:

```text
X-Confianza-Agent-Key: <clave-configurada-en-el-servidor-del-agente>
```

Payload:

```json
{
  "document_type": "CC",
  "document_number": "100000001",
  "eps": "EPS Confianza Ficticia",
  "activation_code": "123456"
}
```

Respuesta exitosa:

```json
{
  "access_token": "jwt-ficticio",
  "token_type": "bearer",
  "expires_in": 2592000,
  "identity": {
    "user_id": 2,
    "patient_id": 1,
    "full_name": "Mariana Rojas",
    "eps": "EPS Confianza Ficticia"
  }
}
```

El JWT usa una clave distinta a la autenticación interna y contiene `typ=agent`, `aud=agent`, `scope=agent:patient`, `sub` y `session_version`. No existe refresh token. La duración se controla con `AGENT_TOKEN_EXPIRE_MINUTES` y es de 30 días por defecto (`43200` minutos); el código de activación conserva su duración corta de cinco minutos. Los tokens existentes no cambian al modificar la variable: hay que volver a vincular la cuenta para emitir uno nuevo.

## Reglas de seguridad

- La activación requiere una cuenta de paciente activa y una ficha de paciente activa.
- Documento y EPS se normalizan antes de comparar.
- Los errores de API key, identidad y clave responden con `401` genérico.
- Los intentos fallidos se limitan a cinco en cinco minutos por huellas de documento, EPS, IP y cliente.
- Un exceso responde `429` con `Retry-After`.
- Las huellas se generan con HMAC y no conservan documento, EPS, IP o API key en claro.
- El JWT se invalida si el usuario se desactiva, el paciente se desactiva o cambia `session_version`.
- Las operaciones mutantes ejecutadas por el agente registran `channel=agent` en auditoría.
- La API key nunca llega al frontend ni se incluye en ejemplos reales, logs o respuestas.

## Migración y operación

Ejecutar antes de publicar:

```bash
uv run alembic upgrade head
```

Configurar todas las variables `AGENT_*` en el servidor. Rotar `AGENT_ACTIVATION_SECRET` invalida las claves pendientes; rotar `AGENT_JWT_SECRET` invalida los tokens existentes; rotar `AGENT_API_KEY` exige actualizar el cliente del agente.

La migración conserva la tabla histórica de intentos bajo el nombre genérico `agent_auth_attempts` y crea `agent_activation_codes`. La reversión elimina únicamente las estructuras nuevas de esta integración; debe ejecutarse con una copia de seguridad y una ventana de mantenimiento.

## Riesgos y límites

- Una clave de seis dígitos debe entregarse solo por el canal autorizado y tiene una ventana corta porque es una credencial de activación manual.
- La API key única es suficiente para la demostración, pero una futura operación multiinstitución requiere clientes persistidos, rotación independiente y posiblemente mTLS u OAuth.
- La validación de EPS usa inicialmente el campo textual existente en `Patient`; todavía no representa una relación multiinstitución completa.
- La historia clínica contiene datos sintéticos y el producto debe conservar advertencias explícitas de demostración.
