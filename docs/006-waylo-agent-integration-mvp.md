# PRD: Contrato Confianza IPS para Waylo (MVP)

**Estado:** aprobado para integración
**Fecha:** 2026-10-26
**Repositorio:** `confianza-ips-backend`

## Propósito

Confianza IPS funciona como la plataforma institucional. Waylo no debe copiar su base,
simular sus respuestas ni recibir credenciales de pacientes en el navegador. El backend
adaptador de Waylo usa una credencial server-to-server y un código temporal emitido por
Confianza para obtener un token limitado al paciente.

## Flujo institucional

1. El paciente autenticado en Confianza genera un código de activación de seis dígitos.
2. El código es de un solo uso y expira en cinco minutos.
3. Waylo envía tipo/número de documento, EPS, código y `X-Confianza-Agent-Key`.
4. Confianza valida identidad, EPS, paciente activo y código.
5. Confianza devuelve un token de agente limitado al paciente.
6. Waylo usa ese token para lecturas autorizadas.

## Endpoints consumidos por Waylo

### Activación

`POST /api/v1/integrations/agent/token`

Payload esperado:

```json
{
  "document_type": "CC",
  "document_number": "1032456789",
  "eps": "Confianza",
  "activation_code": "123456"
}
```

Header obligatorio para Waylo:

```text
X-Confianza-Agent-Key: <AGENT_API_KEY>
```

La respuesta contiene `access_token`, `expires_in` e `identity.patient_id`.

### Paciente

`GET /api/v1/patients/me` con `Authorization: Bearer <agent_token>`.

La respuesta se limita al paciente dueño del token.

### Citas

`GET /api/v1/appointments` con el mismo token.

La autorización de agente filtra las citas al paciente autenticado.

## Seguridad y responsabilidades

- `AGENT_API_KEY`, `AGENT_ACTIVATION_SECRET` y `AGENT_JWT_SECRET` viven solo en el
  backend de Confianza.
- La API key no se entrega al paciente ni al frontend de Waylo.
- El código se almacena como digest, se consume una sola vez y se audita sin guardar el
  secreto en claro.
- El token de agente no concede administración ni acceso global.
- Los errores de autenticación deben continuar devolviendo `401` y no revelar si falló
  documento, EPS o código.

## Alcance del MVP

Confianza soporta para Waylo activación, perfil de paciente y lectura de citas. No se
incluyen todavía disponibilidad, creación, cancelación, reprogramación, historia clínica
ni documentos clínicos en el flujo ciudadano.

El contrato actual no expone sexo, sede primaria, tipo de cita ni nombre de sede en las
formas que el adaptador canónico necesita. Esos campos quedan fuera de la UI del MVP y
se documentan como brechas futuras, no se inventan ni se derivan.

## Configuración de despliegue

En el entorno de Confianza deben estar presentes los tres secretos `AGENT_*`. El valor de
`AGENT_API_KEY` debe coincidir exactamente con `CONFIANZA_AGENT_KEY` del backend adaptador.
Los valores se actualizan fuera del repositorio y se rotan si estuvieron expuestos.

## Validaciones de aceptación

- El flujo de emisión existente genera códigos de seis dígitos, de un solo uso y con
  expiración.
- Un token emitido puede consultar `/patients/me` y `/appointments` solo para su paciente.
- Un token inválido, expirado o usado no obtiene datos.
- El backend de Waylo puede consumir el contrato sin recibir respuestas incompatibles.
- La prueba de integración se ejecuta contra una base sintética aislada.

## Impacto en este repositorio

El MVP no cambia las reglas de afiliación, roles ni permisos de Confianza. La integración
consume endpoints ya existentes. Cualquier cambio futuro al contrato debe actualizar este
documento y el adaptador de Waylo antes de desplegar.
