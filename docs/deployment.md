# Deployment Guide

Steps to deploy LLM Control Plane (backend, frontend, workers, gateway, and
observability stack) via Docker Compose.

## 1. Prerequisites

- Docker & Docker Compose v2
- Node.js >= 22 (only needed for local frontend dev, not for Docker deploy)
- Python 3.13+ (only needed for local backend dev, not for Docker deploy)
- (Optional, for GPU workers) NVIDIA drivers + `nvidia-container-toolkit` —
  the `workers` service in `docker/docker-compose.yml` reserves an NVIDIA GPU
  device by default.

## 2. Clone and configure environment files

```bash
git clone <repo-url>
cd LLMPlane
cp backend/.env.example backend/.env
cp docker/.env.example docker/.env
```

## 3. Generate secrets

```bash
# Fernet key (encrypts stored provider credentials) — used for FERNET_SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Random tokens — used for BOOTSTRAP_ADMIN_TOKEN and LITELLM_MASTER_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Generate a **separate** token for `BOOTSTRAP_ADMIN_TOKEN` and for
`LITELLM_MASTER_KEY` — do not reuse the same value.

## 4. Fill in the `.env` files

**`docker/.env`**

| Variable | Notes |
|---|---|
| `POSTGRES_PASSWORD` | Postgres password |
| `FERNET_SECRET_KEY` | From step 3 |
| `BOOTSTRAP_ADMIN_TOKEN` | From step 3 |
| `LITELLM_MASTER_KEY` | From step 3 — must match `backend/.env` |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_AUTH_HEADER` | Only if using Langfuse Cloud tracing (get from cloud.langfuse.com → Settings → API Keys). `LANGFUSE_AUTH_HEADER` is base64 of `PUBLIC_KEY:SECRET_KEY` |
| `GRAFANA_PASSWORD` | Grafana admin password |
| `NVIDIA_VISIBLE_DEVICES` | Optional, only if using GPU workers |

**`backend/.env`**

| Variable | Notes |
|---|---|
| `DATABASE_URL` | Set the password to match `POSTGRES_PASSWORD` above |
| `FERNET_SECRET_KEY` | Same value as `docker/.env` |
| `BOOTSTRAP_ADMIN_TOKEN` | Same value as `docker/.env` |
| `LITELLM_MASTER_KEY` | Same value as `docker/.env` |
| `CORS_ORIGINS` | Set to your deployed frontend origin(s) in production |
| `ENVIRONMENT` | `dev` / `staging` / `prod` |
| `LLMPLANE_OLLAMA_IMAGE_TAG` / `LLMPLANE_VLLM_IMAGE_TAG` | Pin to a specific tag rather than `latest` for production — check for yanked releases before deploying |

Double-check `FERNET_SECRET_KEY` and `LITELLM_MASTER_KEY` are **identical**
across `docker/.env` and `backend/.env`; drift between the two causes
gateway auth failures and decrypt errors on stored credentials.

## 5. Build and start the stack

```bash
cd docker
docker compose up -d --build
```

This brings up: `postgres`, `redis`, `docker-socket-proxy`, `gateway`
(LiteLLM proxy), `backend`, `workers`, `scheduler`, `frontend`,
`prometheus`, `grafana`, `otel-collector`.

Watch startup and confirm all services report healthy:

```bash
docker compose ps
docker compose logs -f backend
```

## 6. Run database migrations

The backend container does not auto-migrate on boot. Apply Alembic
migrations once Postgres is healthy:

```bash
docker compose exec backend alembic upgrade head
```

## 7. Bootstrap an admin API key

Alpha builds have no login flow — use the bootstrap token to mint the first
admin key:

```bash
curl -X POST http://localhost:8000/api/v1/auth/bootstrap-key \
  -H "Authorization: Bearer <BOOTSTRAP_ADMIN_TOKEN>"
```

Store the returned key securely; it's needed for authenticated API calls.

## 8. Verify the deployment

| Service | URL | Check |
|---|---|---|
| Frontend | http://localhost:3000 | Loads UI |
| Backend API | http://localhost:8000/health | Returns 200 |
| Gateway (LiteLLM) | http://localhost:4000/health | Returns 200 |
| Grafana | http://localhost:3001 | Login with `admin` / `GRAFANA_PASSWORD` |
| Prometheus | http://localhost:9090 | Targets all `UP` |

Smoke-test the OpenAI-compatible gateway:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer <LITELLM_MASTER_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "ping"}]}'
```

## 9. Production hardening checklist

- [ ] Replace all `changeme_*` / `REPLACE_WITH_*` placeholder values — the
      compose file falls back to insecure defaults (e.g.
      `POSTGRES_PASSWORD:-llmplane_dev`, `GRAFANA_PASSWORD:-admin`) if unset.
- [ ] Pin `LLMPLANE_OLLAMA_IMAGE_TAG` / `LLMPLANE_VLLM_IMAGE_TAG` and the
      LiteLLM gateway image tag rather than tracking `latest`.
- [ ] Put `postgres`, `redis`, `docker-socket-proxy`, and the observability
      ports behind a firewall or VPN — the compose file binds them to
      `127.0.0.1` by default, but confirm this holds if you change host
      networking.
- [ ] Review `docs/docker_socket_security_review.md` before exposing the
      `docker-socket-proxy` service beyond local Docker deploys — it proxies
      the host Docker socket for one-click model deployment.
- [ ] Set `CORS_ORIGINS` in `backend/.env` to the real frontend origin(s),
      not `http://localhost:3000`.
- [ ] Set `ENVIRONMENT=prod` and review `LOG_LEVEL`.
- [ ] Configure `REQUEST_RETENTION_DAYS` / `GPU_SAMPLE_RETENTION_HOURS` to
      your data retention policy.
- [ ] Set up TLS termination (reverse proxy / load balancer) in front of the
      frontend, backend, and gateway — none of the services terminate TLS
      themselves.
- [ ] Confirm the `workers` service's GPU reservation matches your host
      (drop the `deploy.resources` block if running CPU-only).

## 10. Updating a running deployment

```bash
git pull
cd docker
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

## 11. Tearing down

```bash
cd docker
docker compose down          # stop and remove containers
docker compose down -v       # also remove volumes (destroys DB data)
```
