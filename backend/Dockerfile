# Backend (control-plane API) image.
# Python 3.12 per ARCHITECTURE.md 1.1.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build deps for asyncpg/argon2/cryptography wheels are not needed on slim for
# the pinned versions (manylinux wheels exist), but curl is used by the healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

COPY entrypoint.sh ./

# Non-root: the backend needs no privileged host access. (Deployment control
# talks to the Docker Engine API from `workers`, not from here — see
# ARCHITECTURE.md 4.5 and T012's security review scope.)
#
# BENCHMARK_UPLOAD_DIR defaults to /data/benchmark_uploads. It must exist and be
# owned by appuser before the drop to USER appuser: / is root-owned 755, so
# os.makedirs("/data/...") from uid 10001 raises PermissionError and every
# dataset upload 500s. Mount a persistent volume at /data to survive redeploys —
# without one this directory is ephemeral container storage.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data/benchmark_uploads \
    && chown -R appuser:appuser /app /data \
    && chmod +x /app/entrypoint.sh
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:${PORT:-8000}/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4"]
