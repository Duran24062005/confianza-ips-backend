# PRD — Integración segura de Waylo mediante API

## Problema y objetivo

Waylo necesita consultar información de un paciente de Confianza IPS sin usar la sesión web interna ni recibir credenciales institucionales. La integración debe permitir una autenticación temporal, trazable y limitada al paciente identificado.

El objetivo es entregar un token de lectura de 15 minutos después de validar el nombre de la cuenta, su correo y un código TOTP global de seis dígitos mostrado exclusivamente a administradores.

## Alcance

Incluye:

- Código TOTP global de Waylo con intervalo de 60 segundos.
- Pantalla administrativa para consultar y copiar el código vigente.
- Intercambio de identidad por token temporal.
- Perfil, ficha administrativa y citas del paciente vinculado.
- Historial de estados de las citas.
- Auditoría de emisión de tokens.
- Rate limit persistido para intentos fallidos.

No incluye:

- Acceso a notas clínicas o documentos.
- Creación, cancelación o reprogramación de citas.
- Acceso a pacientes, usuarios o métricas globales.
- Refresh tokens.
- Gestión de secretos desde la interfaz web.

## Actores y permisos

- **Administrador interno:** puede consultar el código vigente desde la sección de integración. Nunca recibe el secreto TOTP.
- **Waylo:** puede obtener un token temporal mediante el endpoint público de intercambio y usar únicamente los endpoints dedicados de lectura.
- **Paciente:** no puede consultar el código ni emitir tokens Waylo desde la aplicación interna.

La identidad se valida contra `User.full_name` y `User.email`. Los espacios se normalizan y la comparación no distingue mayúsculas. Solo se aceptan usuarios activos con rol `patient`, paciente vinculado y paciente activo.

## Contrato

### Código para administración

`GET /api/v1/integrations/waylo/code`

Requiere un JWT interno de administrador y responde:

```json
{
  "code": "123456",
  "expires_at": "2026-10-22T18:30:00Z",
  "interval_seconds": 60
}
```

El código se calcula con `WAYLO_TOTP_SECRET`; no se persiste ni se devuelve el secreto. La verificación acepta la ventana actual y una ventana adyacente para tolerar pequeñas diferencias de reloj.

### Intercambio Waylo

`POST /api/v1/integrations/waylo/token`

```json
{
  "full_name": "Ana Prueba",
  "email": "patient@confianza.demo",
  "code": "123456"
}
```

La respuesta contiene `access_token`, `token_type`, `expires_in`, `user` y `patient`. El token dura 15 minutos, no tiene refresh token y usa un secreto distinto al JWT interno.

El campo `email` es el único campo de correo del contrato; “email” y “correo” no son propiedades separadas.

### Lecturas disponibles con el token

- `GET /api/v1/integrations/waylo/me`
- `GET /api/v1/integrations/waylo/appointments`
- `GET /api/v1/integrations/waylo/appointments/{appointment_id}`
- `GET /api/v1/integrations/waylo/appointments/{appointment_id}/history`

Los recursos se filtran siempre por el `patient_id` incluido en la cuenta identificada. El token no es válido en los endpoints internos existentes.

## Seguridad y operación

- Las variables `WAYLO_TOTP_SECRET` y `WAYLO_JWT_SECRET` son obligatorias en ambientes desplegados y deben ser valores aleatorios independientes.
- Los intentos fallidos se limitan a cinco por cinco minutos por huella de correo y de IP. La base conserva únicamente huellas HMAC, fecha y resultado.
- Los registros antiguos de intentos se limpian de forma oportunista después de 24 horas.
- Los errores de identidad, código incorrecto, usuario inexistente y usuario no elegible responden de forma uniforme con `401`.
- Un `429` incluye `Retry-After`.
- La auditoría registra la emisión, integración y alcance, pero nunca el código, secreto, token, contraseña, correo o IP en claro.
- Rotar `WAYLO_TOTP_SECRET` invalida inmediatamente los códigos visibles. Rotar `WAYLO_JWT_SECRET` invalida los tokens Waylo existentes.

## Migración y despliegue

Ejecutar antes de publicar:

```bash
uv run alembic upgrade head
```

Configurar en el backend:

```text
WAYLO_TOTP_SECRET=<secreto-base32>
WAYLO_TOTP_INTERVAL_SECONDS=60
WAYLO_JWT_SECRET=<secreto-largo-independiente>
WAYLO_TOKEN_EXPIRE_MINUTES=15
```

No ejecutar pruebas de intercambio contra una base con datos reales sin una autorización explícita. La pantalla administrativa requiere una sesión interna de administrador y no sustituye la configuración de secretos del servidor.

## Riesgos y límites conocidos

- Un código TOTP visible en pantalla sigue siendo una credencial compartida; debe copiarse únicamente hacia el canal autorizado de Waylo.
- El rate limit reduce ataques de adivinación, pero no reemplaza una futura credencial privada de cliente o mTLS si la integración pasa a producción con información clínica real.
- Los datos devueltos incluyen información administrativa sensible del paciente; la integración debe ejecutarse sobre HTTPS y aplicar controles equivalentes en Waylo.
