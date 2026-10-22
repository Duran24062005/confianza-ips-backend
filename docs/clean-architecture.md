# Refactorización de arquitectura

## Problema

Los routers originales combinaban transporte HTTP, consultas SQLAlchemy, reglas de negocio, auditoría y transacciones. Esto hacía difícil probar los casos de uso sin levantar toda la API y convertía errores de infraestructura, como una base sin migraciones, en respuestas `500` poco accionables.

## Decisiones

- Los routers son adaptadores HTTP y no contienen el caso de uso de autenticación.
- Los servicios de `application` coordinan operaciones y expresan resultados independientes de HTTP.
- Las reglas puras de citas viven en `domain/appointment_policy.py`.
- El repositorio SQLAlchemy de usuarios vive en `infrastructure/persistence/repositories.py`.
- Los errores de base no se ocultan ni activan migraciones implícitas: se traducen a `503 DATABASE_NOT_READY` y se corrigen mediante Alembic explícito.
- `/health` continúa siendo un endpoint de vida que no requiere base; `/health/ready` verifica conectividad y la tabla mínima `users`.

## Límites actuales

La migración de los demás agregados hacia servicios de aplicación se realizará por verticales para evitar duplicar lógica o romper el contrato REST. `models.py`, `schemas.py` y `routers/` permanecen como puntos compatibles durante esa transición.

## Verificación

```bash
uv run ruff format --check src scripts migrations tests
uv run ruff check src scripts migrations tests
uv run pytest -q
uv run uvicorn confianza_ips_backend.main:app --reload
curl http://localhost:8000/health/ready
```
