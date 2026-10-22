# Arquitectura

Confianza es un monolito modular FastAPI desplegado como una única función Python en Vercel. El frontend React + Vite vive en otro repositorio y consume únicamente el contrato REST bajo `/api/v1`.

## Capas

La aplicación usa una arquitectura por capas con dependencias dirigidas hacia el dominio:

- `api`: dependencias HTTP, composición de servicios y traducción de errores técnicos a respuestas públicas.
- `routers`: adaptadores HTTP; validan entrada, autorizan el actor y convierten el resultado al contrato Pydantic.
- `application`: casos de uso y servicios, sin conocimiento de rutas HTTP.
- `domain`: reglas puras de negocio, como transiciones de citas, permisos y estados activos.
- `infrastructure`: adaptadores SQLAlchemy, repositorios y comprobaciones de preparación de la base.
- `schemas`: contratos Pydantic de entrada y salida.
- `models`: entidades persistidas SQLAlchemy; se mantiene como módulo de compatibilidad mientras se migra cada agregado.
- `audit` y `security`: capacidades transversales aisladas.
- `scripts`: migraciones y seed explícitos para datos ficticios.

La primera vertical refactorizada es autenticación: `routers/auth.py` solo adapta HTTP, `application/services/authentication.py` coordina el caso de uso, `application/ports.py` define la dependencia mínima y `infrastructure/persistence/repositories.py` encapsula la consulta SQLAlchemy. Las reglas de citas se comparten desde `domain/appointment_policy.py` para evitar duplicarlas entre disponibilidad y cambios de estado.

## Consistencia de citas

El servicio valida disponibilidad antes de escribir. PostgreSQL añade restricciones de exclusión sobre rangos de tiempo para resolver carreras concurrentes; el error de integridad se traduce a HTTP 409.

## Despliegue

Vercel ejecuta el módulo `src.confianza_ips_backend.main:app`, configurado en `pyproject.toml`. Las migraciones no forman parte del ciclo de request. Neon usa conexión pooled para la API y conexión directa para operaciones administrativas cuando sea necesario. Una base sin esquema se reporta como `503 DATABASE_NOT_READY` y se corrige ejecutando Alembic antes de publicar tráfico.
