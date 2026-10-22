# Arquitectura

Confianza es un monolito modular FastAPI desplegado como una única función Python en Vercel. El frontend React + Vite vive en otro repositorio y consume únicamente el contrato REST bajo `/api/v1`.

## Capas

- `routers`: HTTP, códigos de estado y autorización de entrada.
- `schemas`: contratos Pydantic.
- `models`: persistencia SQLAlchemy.
- `audit`: registro transversal de operaciones.
- `security`: JWT, contraseñas y roles.
- `scripts`: seed explícito para datos ficticios.

## Consistencia de citas

El servicio valida disponibilidad antes de escribir. PostgreSQL añade restricciones de exclusión sobre rangos de tiempo para resolver carreras concurrentes; el error de integridad se traduce a HTTP 409.

## Despliegue

Vercel ejecuta el entrypoint configurado en `pyproject.toml`. Las migraciones no forman parte del ciclo de request. Neon usa conexión pooled para la API y conexión directa para operaciones administrativas cuando sea necesario.
