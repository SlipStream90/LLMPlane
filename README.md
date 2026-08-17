# LLMPlane

An all-in-one AI infrastructure platform for deploying, managing, routing, evaluating, and observing Large Language Models.

## Overview

LLMPlane replaces the need for multiple tools (LiteLLM, Promptfoo, Langfuse, Grafana, Ollama, vLLM) with a single integrated platform. It provides OpenRouter-powered inference, one-click local model deployment, multi-model routing, evaluation frameworks, and full observability.

## Features

- **OpenRouter Integration** - Unified LLM access via OpenRouter (OpenAI, Anthropic, Gemini, Groq, Mistral, and more)
- **Local Model Deployment** - Launch Ollama and vLLM models with one click via Docker
- **Multi-Model Routing** - Intelligent routing across providers with load balancing and fallbacks
- **OAuth Authentication** - Sign in with GitHub or Google, plus API key auth
- **Evaluation Framework** - Benchmark models with built-in metrics and custom evals
- **Observability** - OpenTelemetry traces, Grafana Cloud dashboards, Langfuse tracing
- **Database Backups** - Automated backups to Cloudflare R2 every 6 hours
- **Modern UI** - Real-time dashboards, 3D command center, and visualizations

## Tech Stack

**Frontend**
- Next.js 16, React 19, TypeScript
- Tailwind CSS 4, Radix UI, shadcn/ui
- ECharts, React Flow, Monaco Editor
- TanStack Query & Table

**Backend**
- FastAPI, SQLAlchemy, Alembic
- PostgreSQL, Redis
- Celery workers with GPU support
- OpenTelemetry, Langfuse

**Infrastructure**
- Docker Compose (self-hosted) or Vercel + Railway (cloud)
- OpenRouter for LLM inference
- Grafana Cloud for metrics/logs
- Cloudflare R2 for backups

## Quick Start

### Prerequisites

- An [OpenRouter](https://openrouter.ai) account and API key
- Docker & Docker Compose (for self-hosted) OR Vercel + Railway accounts (for cloud)

### Option A: Docker Compose (Self-Hosted)

```bash
git clone <repo-url>
cd LLMPlane
cp backend/.env.example backend/.env
cp docker/.env.example docker/.env

# Generate secrets
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Update .env files with generated values + your OPENROUTER_API_KEY

cd docker
docker compose up -d --build
```

Access:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Grafana: http://localhost:3001

### Option B: Vercel + Railway (Cloud, $0 for personal use)

See [docs/deployment.md](docs/deployment.md) for the complete step-by-step guide.

**TL;DR:**
1. Create Railway project → add Postgres + Redis → deploy backend
2. Create Vercel project → deploy frontend
3. Set environment variables (see docs/deployment.md)
4. Bootstrap admin key
5. Done

## Project Structure

```
LLMPlane/
├── backend/              # FastAPI backend API
│   ├── app/              # Application code
│   ├── alembic/          # Database migrations
│   └── entrypoint.sh     # Docker entrypoint (runs migrations)
├── frontend/             # Next.js frontend
│   ├── app/              # App router pages
│   ├── components/       # React components
│   └── lib/              # Utilities and API client
├── workers/              # Celery background workers
│   └── tasks/            # Backup, benchmark tasks
├── docker/               # Docker Compose and configs
│   ├── grafana/          # Grafana provisioning
│   ├── prometheus/       # Prometheus config + alerts
│   ├── loki/             # Loki log aggregation
│   └── promtail/         # Promtail log shipping
├── k8s/                  # Kubernetes Helm chart
├── scripts/              # Deploy and restore scripts
├── docs/                 # Documentation
└── .github/              # CI/CD workflows
```

## API

The backend exposes an OpenAI-compatible API:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://your-backend.up.railway.app/api/v1",
    api_key="your-api-key"
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}]
)
```

## Environment Variables

See `backend/.env.example` for all configuration options.

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `FERNET_SECRET_KEY` | Encryption key for provider credentials |
| `BOOTSTRAP_ADMIN_TOKEN` | One-time token to create first API key |
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM inference |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub OAuth (optional) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth (optional) |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Langfuse tracing (optional) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Grafana Cloud OTLP endpoint (optional) |

## Deployment

See [docs/deployment.md](docs/deployment.md) for detailed instructions on:
- Docker Compose (self-hosted)
- Vercel + Railway (managed cloud)
- Environment variables reference
- Production hardening checklist

## License

MIT
