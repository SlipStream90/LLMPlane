# Celery worker image.
#
# Build context is the repository root (both `backend/` and `workers/` are
# copied), because workers import the backend's models and repositories rather
# than owning a second schema copy (ARCHITECTURE.md 3.2):
#
#   docker build -f workers/Dockerfile -t llmplane-workers .
#
# This container is the one that holds the Docker socket and GPU access. Keep
# that privilege here and out of the API container.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend:/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
COPY workers/requirements.txt ./workers/requirements.txt
RUN pip install --no-cache-dir -r workers/requirements.txt

COPY backend/app ./backend/app
COPY workers ./workers

# Runs as root: the Docker socket and NVIDIA device nodes are not readable by
# an unprivileged user in the default Compose setup. This is the trade-off
# ARCHITECTURE.md 4.5 flags and task T012 was raised to review — narrowing it
# (socket proxy, scoped Docker context, or a docker group with a matching GID)
# is that review's call to make, not an assumption to bake in here.
CMD ["celery", "-A", "workers.celery_app.celery_app", "worker", \
     "--loglevel=INFO", "--queues=default,deployment,benchmark,evaluation", \
     "--concurrency=4"]
