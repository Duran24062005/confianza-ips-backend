 # Confianza IPS Backend

API institucional ficticia construida con FastAPI, SQLAlchemy y PostgreSQL.

## Desarrollo local

1. Copia `.env.example` como `.env` y configura una base PostgreSQL local o una base de pruebas aislada.
2. Instala dependencias con `uv sync`.
3. Ejecuta las migraciones: `uv run alembic upgrade head`.
4. Carga datos ficticios: `uv run python scripts/seed.py`.
5. Inicia el servidor: `uv run uvicorn confianza_ips_backend.main:app --reload`.

La documentación interactiva está disponible en `/docs` mientras `APP_ENV` no sea `production`.

## Cuentas de demostración

El seed crea cuentas ficticias con la contraseña `Confianza123!`:

- `admin@confianza.demo`
- `recepcion@confianza.demo`
- `laura.medica@confianza.demo`
- `mariana.paciente@confianza.demo`

No utilizar estos datos en un entorno con información real.

## Contrato

La especificación OpenAPI generada por FastAPI es la fuente de verdad para el frontend. Los endpoints están bajo `/api/v1` y el servicio expone `/health` para smoke tests.

## Migraciones y despliegue

Las migraciones se ejecutan explícitamente antes de publicar. No se ejecutan automáticamente durante una request de Vercel. `DATABASE_URL` debe apuntar al endpoint pooled de Neon para la aplicación y `DATABASE_URL_UNPOOLED` queda reservado para tareas administrativas o migraciones.
