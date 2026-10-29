# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.22-python3.14-bookworm-slim AS builder
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev

FROM python:3.14-slim-bookworm AS runner
WORKDIR /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

COPY --from=builder /app/.venv /app/.venv
COPY src ./src
COPY migrations ./migrations
COPY scripts ./scripts
COPY alembic.ini pyproject.toml README.md ./

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["sh", "-c", "exec uvicorn confianza_ips_backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
