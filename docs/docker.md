# Docker: backend Confianza IPS

La imagen ejecuta FastAPI con Uvicorn en el puerto `8000`. Usa Python 3.14 y el
lockfile de `uv` para instalar únicamente dependencias de producción.

## Construir y ejecutar

```bash
docker build -t confianza-ips-backend .
docker run --rm --env-file .env -p 8000:8000 confianza-ips-backend
```

La imagen incluye las migraciones de Alembic, pero no las ejecuta durante el
arranque. Aplícalas desde un proceso operativo controlado:

```bash
docker run --rm --env-file .env confianza-ips-backend \
  alembic upgrade head
```

Después, carga datos ficticios con el seed fuera del arranque de la API. Confirma
`GET /health` para disponibilidad básica y `GET /health/ready` para comprobar la
conexión a la base de datos:

```bash
docker run --rm --env-file .env confianza-ips-backend \
  python scripts/seed.py
```
