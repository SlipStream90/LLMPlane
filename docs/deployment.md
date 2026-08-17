# Deployment Guide

Two deployment options for LLMPlane:

- **Option A**: Docker Compose (self-hosted, local or VPS)
- **Option B**: Vercel + Railway (managed cloud, recommended for production)

---

## Prerequisites (Both Options)

- An [OpenRouter](https://openrouter.ai) account and API key
- A [GitHub](https://github.com) account (for OAuth and repo access)
- Python 3.13+ and Node.js >= 22 (for local dev only, not required for deployment)

---

# Option A: Docker Compose (Self-Hosted)

Run the full stack on your own machine or a VPS.

## A1. Prerequisites

- Docker & Docker Compose v2
- (Optional, for GPU workers) NVIDIA drivers + `nvidia-container-toolkit`

## A2. Clone and configure

```bash
git clone <repo-url>
cd LLMPlane
cp backend/.env.example backend/.env
cp docker/.env.example docker/.env
```

## A3. Generate secrets

```bash
# Fernet key (encrypts stored provider credentials)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Random token (bootstrap admin key)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## A4. Get your OpenRouter API key

1. Go to [openrouter.ai](https://openrouter.ai) and sign up / log in
2. Go to **Keys** → **Create Key**
3. Copy the key (starts with `sk-or-...`)
4. Add credit to your account (pay-per-use pricing)

## A5. Set up Grafana Cloud (observability)

1. Go to [grafana.com/auth/sign-up](https://grafana.com/auth/sign-up) and create a free account
2. You get a managed Grafana stack with:
   - **Grafana**: `https://<your-stack>.grafana.net`
   - **Prometheus**: `https://prometheus-prod-XX.grafana.net`
   - **Loki**: `https://logs-prod-XX.grafana.net`
3. Go to **Grafana** → **Security** → **API Keys** → **Add API key**
   - Role: **Viewer** (for dashboard embedding)
   - Copy the key
4. Go to **Prometheus** → **Details** → copy the **Remote Write** endpoint

## A6. Set up Langfuse (LLM tracing, optional)

1. Go to [cloud.langfuse.com](https://cloud.langfuse.com) and sign up
2. Create a new project → name it `LLMPlane`
3. Go to **Settings** → **API Keys** → **Create API Key**
4. Copy **Public Key** (`pk-lf-...`) and **Secret Key** (`sk-lf-...`)

## A7. Fill in `docker/.env`

| Variable | Value |
|---|---|
| `POSTGRES_PASSWORD` | Any strong password |
| `FERNET_SECRET_KEY` | From step A3 |
| `BOOTSTRAP_ADMIN_TOKEN` | From step A3 |
| `OPENROUTER_API_KEY` | From step A4 |
| `GRAFANA_PASSWORD` | Any password for local Grafana |
| `LANGFUSE_PUBLIC_KEY` | From step A6 (optional) |
| `LANGFUSE_SECRET_KEY` | From step A6 (optional) |

## A8. Fill in `backend/.env`

| Variable | Value |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://llmplane:<POSTGRES_PASSWORD>@postgres:5432/llmplane` |
| `FERNET_SECRET_KEY` | Same as `docker/.env` |
| `BOOTSTRAP_ADMIN_TOKEN` | Same as `docker/.env` |
| `OPENROUTER_API_KEY` | Same as `docker/.env` |
| `CORS_ORIGINS` | `http://localhost:3000` |
| `ENVIRONMENT` | `dev` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | From step A5 (Grafana Cloud OTLP endpoint) |
| `OTEL_SERVICE_NAME` | `llmplane-backend` |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` |
| `LANGFUSE_PUBLIC_KEY` | From step A6 |
| `LANGFUSE_SECRET_KEY` | From step A6 |

## A9. Build and start

```bash
cd docker
docker compose up -d --build
```

This brings up: `postgres`, `redis`, `docker-socket-proxy`, `backend`, `workers`, `scheduler`, `frontend`, `prometheus`, `grafana`, `otel-collector`.

Watch startup:

```bash
docker compose ps
docker compose logs -f backend
```

## A10. Bootstrap admin key

```bash
curl -X POST http://localhost:8000/api/v1/auth/bootstrap-key \
  -H "Authorization: Bearer <BOOTSTRAP_ADMIN_TOKEN>"
```

Save the returned `secret_key` — this is your master API key.

## A11. Verify

| Service | URL | Check |
|---|---|---|
| Frontend | http://localhost:3000 | Loads UI |
| Backend API | http://localhost:8000/health | Returns 200 |
| Local Grafana | http://localhost:3001 | Login with `admin` / `GRAFANA_PASSWORD` |
| Local Prometheus | http://localhost:9090 | Targets all `UP` |
| Grafana Cloud | `https://<your-stack>.grafana.net` | Dashboards showing metrics |

## A12. Updating

```bash
git pull
cd docker
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

## A13. Tearing down

```bash
cd docker
docker compose down          # stop containers
docker compose down -v       # also remove volumes (destroys DB data)
```

---

# Option B: Vercel + Railway (Managed Cloud)

Frontend on Vercel, backend on Railway. ~$5-8/month total.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Vercel (free)                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Next.js Frontend                                 │  │
│  │  https://your-app.vercel.app                      │  │
│  └───────────────────────┬───────────────────────────┘  │
└──────────────────────────┼──────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────┐
│               Railway ($5/mo free credit)                │
│  ┌───────────────────────▼───────────────────────────┐  │
│  │  FastAPI Backend                                  │  │
│  │  your-app.up.railway.app                          │  │
│  └──────┬───────────────┬────────────────────────────┘  │
│         │               │                               │
│  ┌──────▼──────┐ ┌──────▼──────┐                       │
│  │ PostgreSQL   │ │ Redis       │                       │
│  │ (plugin)     │ │ (plugin)    │                       │
│  └─────────────┘ └─────────────┘                       │
└─────────────────────────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  OpenRouter  │
                    │  (pay-per-use)│
                    └─────────────┘
```

> **Cost**: $0 for personal/testing use. Railway's $5/month free credit covers
> the backend + databases at minimal traffic.

## B1. Generate secrets

```bash
# Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Bootstrap token
python -c "import secrets; print(secrets.token_urlsafe(32))"

# LiteLLM master key (for backend auth)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy all 3 outputs.

## B2. Get your OpenRouter API key

1. Go to [openrouter.ai](https://openrouter.ai) and sign up / log in
2. Go to **Keys** → **Create Key**
3. Copy the key (starts with `sk-or-...`)
4. Add credit to your account

## B3. Set up Grafana Cloud

1. Go to [grafana.com/auth/sign-up](https://grafana.com/auth/sign-up) and create a free account
2. You get:
   - **Grafana**: `https://<your-stack>.grafana.net`
   - **Prometheus**: `https://prometheus-prod-XX.grafana.net`
3. Go to **Grafana** → **Security** → **API Keys** → **Add API key**
   - Role: **Viewer**
   - Copy the key
4. Go to **Prometheus** → **Details** → copy the **Remote Write** endpoint

## B4. Set up Langfuse (optional)

1. Go to [cloud.langfuse.com](https://cloud.langfuse.com) and sign up
2. Create a project → **Settings** → **API Keys** → create key
3. Copy **Public Key** and **Secret Key**

## B5. Create Railway account

1. Go to [railway.app](https://railway.app)
2. Click **Login** → sign in with GitHub
3. You get **$5/month free credit**

## B6. Create PostgreSQL on Railway

1. In Railway Dashboard, click **New Project** → **Provision PostgreSQL**
2. Click the Postgres service → **Variables** tab
3. Copy the `DATABASE_URL` value

## B7. Create Redis on Railway

1. In the same project, click **New** → **Database** → **Redis**
2. Click the Redis service → **Variables** tab
3. Copy the `REDIS_URL` value

## B8. Create Backend Service on Railway

1. In your Railway project, click **New** → **GitHub Repo**
2. Select your `LLMPlane` repo
3. Click the service → **Settings**:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4`
4. Go to **Variables** tab and add:

```
DATABASE_URL=<from step B6>
REDIS_URL=<from step B7>
FERNET_SECRET_KEY=<from step B1>
BOOTSTRAP_ADMIN_TOKEN=<from step B1>
OPENROUTER_API_KEY=<from step B2>
ENVIRONMENT=prod
LOG_LEVEL=INFO
CORS_ORIGINS=https://your-app.vercel.app
ENABLE_STREAM_CONSUMER=false
OTEL_EXPORTER_OTLP_ENDPOINT=<from step B3>
OTEL_SERVICE_NAME=llmplane-backend
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=<from step B4>
LANGFUSE_SECRET_KEY=<from step B4>
BENCHMARK_UPLOAD_DIR=/tmp/benchmark_uploads
REQUEST_RETENTION_DAYS=90
GPU_SAMPLE_RETENTION_HOURS=72
```

5. Go to **Settings** → **Networking** → **Generate Domain**
6. Copy the generated URL (e.g. `llmplane-backend.up.railway.app`)

## B9. Set up OAuth (optional)

### GitHub OAuth

1. Go to [github.com/settings/developers](https://github.com/settings/developers)
2. Click **New OAuth App**
3. Fill in:
   - **Application name**: `LLMPlane`
   - **Homepage URL**: `https://your-app.vercel.app`
   - **Authorization callback URL**: `https://llmplane-backend.up.railway.app/api/v1/auth/oauth/github/callback`
4. Click **Register application**
5. Copy **Client ID**
6. Click **Generate a new client secret** → copy it immediately

### Google OAuth

1. Go to [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials)
2. **+ Create Credentials** → **OAuth client ID**
3. Configure consent screen if prompted (External, app name `LLMPlane`)
4. Create OAuth client ID:
   - Application type: **Web application**
   - Name: `LLMPlane`
   - Authorized redirect URIs: `https://llmplane-backend.up.railway.app/api/v1/auth/oauth/google/callback`
5. Copy **Client ID** and **Client Secret**

### Add OAuth to Railway

Go back to Railway **Variables** and add:

```
GITHUB_CLIENT_ID=<from above>
GITHUB_CLIENT_SECRET=<from above>
GOOGLE_CLIENT_ID=<from above>
GOOGLE_CLIENT_SECRET=<from above>
OAUTH_CALLBACK_BASE_URL=https://llmplane-backend.up.railway.app
```

**Redeploy** the service after adding OAuth vars.

## B10. Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com)
2. Click **Add New** → **Project**
3. Import your `LLMPlane` repo
4. Configure:
   - **Framework Preset**: Next.js
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `.next`
5. Click **Environment Variables** and add:

```
NEXT_PUBLIC_API_URL=https://llmplane-backend.up.railway.app/api/v1
NEXT_PUBLIC_WS_URL=wss://llmplane-backend.up.railway.app/ws
NEXT_PUBLIC_GRAFANA_URL=https://your-stack.grafana.net
NEXT_PUBLIC_LANGFUSE_URL=https://cloud.langfuse.com
```

6. Click **Deploy**

## B11. Update CORS

Go back to Railway → your backend service → **Variables**:

Update `CORS_ORIGINS` with your actual Vercel URL:

```
CORS_ORIGINS=https://your-actual-app.vercel.app
```

Redeploy the backend.

## B12. Bootstrap admin key

```bash
curl -X POST https://llmplane-backend.up.railway.app/api/v1/auth/bootstrap-key \
  -H "Content-Type: application/json" \
  -d '{"token": "<BOOTSTRAP_ADMIN_TOKEN>", "name": "first-key"}'
```

Save the returned `secret_key` — that's your master API key.

## B13. Verify

1. Open your Vercel URL: `https://your-app.vercel.app`
2. You should see the LLMPlane dashboard
3. If OAuth is set up, click **Sign in with GitHub** or **Sign in with Google**
4. If using API keys, paste your bootstrap key in the API Key Settings modal
5. Check Grafana Cloud for metrics: `https://your-stack.grafana.net`

## B14. Updating

### Backend (Railway)

Railway auto-deploys on push to your repo. Just `git push`.

### Frontend (Vercel)

Vercel auto-deploys on push to your repo. Just `git push`.

### Manual deploy

```bash
# Backend
railway up --service backend

# Frontend
vercel --prod
```

---

# Complete Environment Variables Reference

## Railway Backend Variables

```
# ── Database (auto-injected by Railway plugins) ──────────────
DATABASE_URL=postgresql://...
REDIS_URL=redis://...

# ── Secrets ──────────────────────────────────────────────────
FERNET_SECRET_KEY=<fernet_key>
BOOTSTRAP_ADMIN_TOKEN=<bootstrap_token>

# ── OpenRouter ───────────────────────────────────────────────
OPENROUTER_API_KEY=sk-or-...

# ── App ──────────────────────────────────────────────────────
ENVIRONMENT=prod
LOG_LEVEL=INFO
CORS_ORIGINS=https://your-app.vercel.app
ENABLE_STREAM_CONSUMER=false

# ── Grafana Cloud ────────────────────────────────────────────
OTEL_EXPORTER_OTLP_ENDPOINT=https://prometheus-prod-XX.grafana.net/api/v1/otlp
OTEL_SERVICE_NAME=llmplane-backend

# ── Langfuse ─────────────────────────────────────────────────
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

# ── OAuth ────────────────────────────────────────────────────
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
OAUTH_CALLBACK_BASE_URL=https://llmplane-backend.up.railway.app

# ── Retention ────────────────────────────────────────────────
REQUEST_RETENTION_DAYS=90
GPU_SAMPLE_RETENTION_HOURS=72
BENCHMARK_UPLOAD_DIR=/tmp/benchmark_uploads
```

## Vercel Frontend Variables

```
NEXT_PUBLIC_API_URL=https://llmplane-backend.up.railway.app/api/v1
NEXT_PUBLIC_WS_URL=wss://llmplane-backend.up.railway.app/ws
NEXT_PUBLIC_GRAFANA_URL=https://your-stack.grafana.net
NEXT_PUBLIC_LANGFUSE_URL=https://cloud.langfuse.com
```

## Docker `.env` Variables (Self-Hosted)

```
POSTGRES_PASSWORD=<any_password>
FERNET_SECRET_KEY=<fernet_key>
BOOTSTRAP_ADMIN_TOKEN=<bootstrap_token>
OPENROUTER_API_KEY=sk-or-...
GRAFANA_PASSWORD=<any_password>
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

## Docker `backend/.env` Variables (Self-Hosted)

```
DATABASE_URL=postgresql+asyncpg://llmplane:<password>@postgres:5432/llmplane
REDIS_URL=redis://redis:6379/0
FERNET_SECRET_KEY=<same_as_docker_env>
BOOTSTRAP_ADMIN_TOKEN=<same_as_docker_env>
OPENROUTER_API_KEY=<same_as_docker_env>
CORS_ORIGINS=http://localhost:3000
ENVIRONMENT=dev
OTEL_EXPORTER_OTLP_ENDPOINT=<grafana_cloud_otlp_endpoint>
OTEL_SERVICE_NAME=llmplane-backend
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=<langfuse_key>
LANGFUSE_SECRET_KEY=<langfuse_secret>
```

---

# Cost Summary

| Service | Docker (Self-Hosted) | Vercel + Railway |
|---|---|---|
| Frontend | $0 (your server) | $0 (Vercel Hobby) |
| Backend | $0 (your server) | $0 (Railway $5/mo free credit) |
| PostgreSQL | $0 (your server) | $0 (covered by free credit) |
| Redis | $0 (your server) | $0 (covered by free credit) |
| Grafana Cloud | $0 (free tier) | $0 (free tier) |
| Langfuse | $0 (free tier) | $0 (free tier) |
| OpenRouter | Pay-per-use | Pay-per-use |
| **Total** | **$0 + server cost** | **$0** (within free credit) |

> Railway gives $5/month free credit. At minimal traffic (testing/personal use),
> the backend + Postgres + Redis cost ~$3-4/month, well within the free tier.
> You only start paying if you exceed the credit or add paid add-ons.
