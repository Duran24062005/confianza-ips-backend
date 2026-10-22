 # Confianza IPS Backend

API institucional ficticia construida con FastAPI, SQLAlchemy y PostgreSQL.

## Desarrollo local

1. Copia `.env.example` como `.env` y configura una base PostgreSQL local o una base de pruebas aislada.
2. Instala dependencias con `uv sync`.
3. Ejecuta las migraciones: `uv run alembic upgrade head`.
4. Carga datos ficticios: `uv run python scripts/seed.py`.
5. Inicia el servidor: `uv run uvicorn confianza_ips_backend.main:app --reload`.

Las migraciones son obligatorias antes del primer login. Si la base no está disponible o no contiene el esquema, la API responde `503 DATABASE_NOT_READY` en lugar de producir un `500` ambiguo. Puedes comprobar la preparación con `GET /health/ready`.

La documentación interactiva está disponible en `/docs` mientras `APP_ENV` no sea `production`.

## Integración Waylo

Waylo puede consultar el perfil administrativo y las citas de un paciente mediante los endpoints dedicados bajo `/api/v1/integrations/waylo`. El intercambio recibe `full_name`, `email` y `code`; `email` es el único campo de correo del contrato. El token emitido dura 15 minutos y no habilita escritura, historia clínica ni recursos globales.

Configura en el backend los secretos independientes de la integración:

```text
WAYLO_TOTP_SECRET=<secreto-base32>
WAYLO_TOTP_INTERVAL_SECONDS=60
WAYLO_JWT_SECRET=<secreto-largo-independiente>
WAYLO_TOKEN_EXPIRE_MINUTES=15
```

Después de aplicar las migraciones, un administrador puede consultar el código vigente en `/app/integraciones/waylo` del frontend. El código cambia cada 60 segundos y la interfaz muestra su vencimiento; nunca se expone el secreto TOTP.

La especificación completa, incluyendo permisos, límites, errores y rotación de secretos, está en [`docs/003-waylo-agent-api-integration.md`](docs/003-waylo-agent-api-integration.md).

## Integración continua

El workflow `.github/workflows/ci.yml` se ejecuta en cada `push` o `pull_request` hacia `main`, y también puede iniciarse manualmente. Verifica formato, lint, pruebas aisladas con SQLite y construcción del paquete mediante Python 3.14 y uv 0.12.22.

El CI no usa Neon ni ejecuta migraciones o seed contra infraestructura externa. Para reproducirlo localmente:

```bash
uv sync --locked --group dev
uv run ruff format --check src scripts migrations tests
uv run ruff check src scripts migrations tests
uv run pytest -q
uv build
```

## Cuentas de demostración

El seed crea cuentas ficticias con la contraseña `Confianza123!`:

- `admin@confianza.demo`
- `recepcion@confianza.demo`
- `laura.medica@confianza.demo`
- `mariana.paciente@confianza.demo`

No utilizar estos datos en un entorno con información real.

El seed es idempotente y crea una línea de tiempo sintética con citas solicitadas, confirmadas, completadas, canceladas y no asistidas. Las fechas se calculan alrededor del día de ejecución para que el dashboard de 7, 30 y 90 días tenga datos demostrables. Los registros existentes no se eliminan.

## Contrato

La especificación OpenAPI generada por FastAPI es la fuente de verdad para el frontend. Los endpoints están bajo `/api/v1` y el servicio expone `/health` para smoke tests.

## Migraciones y despliegue

Las migraciones se ejecutan explícitamente antes de publicar. No se ejecutan automáticamente durante una request de Vercel. `DATABASE_URL` debe apuntar al endpoint pooled de Neon para la aplicación y `DATABASE_URL_UNPOOLED` queda reservado para tareas administrativas o migraciones.

En el proyecto backend de Vercel, `CORS_ORIGINS` debe contener los orígenes completos separados por coma. Para la demo actual:

```text
http://localhost:5173,https://confianza-ips-frontend.vercel.app
```

El frontend desplegado no puede usar `http://localhost:8000`: en el navegador del usuario esa dirección apunta a su propio equipo y los navegadores bloquean el acceso desde un sitio HTTPS. En el proyecto frontend de Vercel configura `VITE_API_BASE_URL` con la URL pública del backend, por ejemplo `https://confianza-ips-backend.vercel.app/api/v1`. Como Vite incrusta las variables `VITE_*` durante el build, cada cambio requiere un nuevo despliegue.

Después de actualizar ambas variables, valida `GET /health` y una petición OPTIONS a `/api/v1/auth/login` desde el dominio frontend antes de probar el login.

Para resolver una base Neon recién creada, ejecuta desde el repositorio backend con las variables del entorno administrativo:

```bash
uv run alembic upgrade head
uv run python scripts/seed.py
```

No ejecutes el seed contra una base con datos reales.
## Capacidades de demostración

Además del dashboard operativo existente, la API expone `GET /api/v1/dashboard/analytics?days=7|30|90` para construir tendencias y distribuciones desde citas persistidas. El resultado aplica alcance por rol y agrupa los días en `America/Bogota`.

El perfil autenticado puede actualizar su nombre visible con `PATCH /api/v1/auth/me`. La operación registra auditoría; los datos administrativos del paciente continúan en `/api/v1/patients/me`.
