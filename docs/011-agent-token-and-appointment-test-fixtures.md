# PRD — Tokens prolongados y cupos de prueba del agente

## Problema y objetivo

Las pruebas del flujo Waylo → Confianza IPS se interrumpen porque el JWT del agente dura poco y porque la agenda demo solo abre algunos días de la semana. El objetivo es mantener la activación manual segura, emitir un token de paciente válido durante al menos un mes y garantizar cupos ficticios suficientes para consultar, apartar, reprogramar y cancelar citas.

## Alcance

- Mantener el código de activación de un solo uso con ventana de cinco minutos.
- Cambiar el valor por defecto de `AGENT_TOKEN_EXPIRE_MINUTES` a `43200` minutos (30 días), con un máximo configurable de 90 días.
- Hacer que el seed idempotente complete la agenda activa de los médicos demo para todos los días, de 08:00 a 16:00 en `America/Bogota`.
- Cubrir el flujo agente de disponibilidad, creación, reprogramación y cancelación.
- Documentar que cancelar es una baja lógica auditada; no se elimina físicamente la cita.

## Contratos y reglas

- Confianza devuelve `expires_in` en segundos junto con el JWT; Waylo persiste esa expiración y no tiene una expiración independiente más corta.
- Cambiar la variable solo afecta tokens nuevos. Una cuenta vinculada debe volver a vincularse después de desplegar la configuración.
- El token sigue limitado al paciente, al alcance `agent:patient` y a las validaciones de estado/sesión.
- El catálogo de citas mantiene `general` y `priority`. “Urgente” es una orientación de atención y no se convierte en un tipo de cita inventado por este cambio.
- Los cambios mutantes requieren la confirmación explícita que ya exige Waylo.

## Validación y riesgos

- Verificar que la respuesta de token sea `2592000` segundos cuando se usa la configuración por defecto.
- Verificar disponibilidad en una fecha futura de cualquier día y el flujo crear → reprogramar → cancelar con el token agente.
- No ejecutar el seed contra una base con datos reales: solo agrega horarios demo faltantes y conserva registros existentes.
- Un token de 30 días amplía la ventana de exposición; la revocación por desactivación y `session_version`, la API key privada y el vínculo por paciente siguen siendo obligatorios.

## Operación

```bash
uv run alembic upgrade head
uv run python scripts/seed.py
```

En el entorno del backend institucional:

```text
AGENT_TOKEN_EXPIRE_MINUTES=43200
```

Después de desplegar, generar un nuevo código desde la cuenta paciente y volver a vincular Confianza IPS desde Waylo. No se debe copiar ningún token ni secreto al frontend, al repositorio o a los logs.
