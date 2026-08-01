# LLM Control Plane

An all-in-one AI infrastructure platform for deploying, managing, routing, evaluating, and observing Large Language Models.

## Overview

LLM Control Plane replaces the need for multiple tools (LiteLLM, Promptfoo, Langfuse, Grafana, Ollama, vLLM) with a single integrated platform. It provides an OpenAI-compatible gateway, one-click local model deployment, multi-model routing, evaluation frameworks, and full observability.

## Features

- **Unified Gateway** - OpenAI-compatible API (`POST /v1/chat/completions`) supporting OpenAI, Anthropic, Gemini, Groq, Mistral, Cohere, Ollama, vLLM, and local HuggingFace models
- **Local Model Deployment** - Launch Ollama and vLLM models with one click via Docker
- **Multi-Model Routing** - Intelligent routing across providers with load balancing and fallbacks
- **Evaluation Framework** - Benchmark models with built-in metrics and custom evals
- **Observability** - OpenTelemetry traces, Prometheus metrics, and Grafana dashboards
- **Modern UI** - Real-time dashboards, graphs, and visualizations

## Tech Stack

**Frontend**
- Next.js 16, React 19, TypeScript
- Tailwind CSS 4, Radix UI
- ECharts, React Flow, Monaco Editor
- TanStack Query & Table

**Backend**
- FastAPI, SQLAlchemy, Alembic
- PostgreSQL, Redis
- Celery workers with GPU support
- OpenTelemetry, Prometheus

**Infrastructure**
- Docker Compose
- LiteLLM Proxy (gateway)
- Grafana, Prometheus, OTel Collector

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Node.js >= 22
- Python 3.13+

### Quick Start

1. Clone the repository:
```bash
git clone <repo-url>
cd LLMPlane
```

2. Copy environment files:
```bash
cp backend/.env.example backend/.env
cp docker/.env.example docker/.env
```

3. Generate required secrets:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

4. Update `.env` files with generated values.

5. Start all services:
```bash
cd docker
docker compose up -d
```

6. Access the application:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Gateway: http://localhost:4000
- Grafana: http://localhost:3001

### Development

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Workers:**
```bash
cd workers
pip install -r requirements.txt
celery -A celery_app worker --loglevel=info
```

## Project Structure

```
LLMPlane/
├── backend/          # FastAPI backend API
├── frontend/         # Next.js frontend
├── workers/          # Celery background workers
├── docker/           # Docker Compose and config
│   ├── gateway/      # LiteLLM proxy config
│   ├── grafana/      # Grafana provisioning
│   ├── prometheus/   # Prometheus config
│   └── otel-collector/ # OpenTelemetry config
├── docs/             # Documentation
├── scripts/          # Utility scripts
└── prd.md            # Product Requirements Document
```

## API

The gateway exposes an OpenAI-compatible API:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:4000/v1",
    api_key="your-key"
)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

## Environment Variables

See `backend/.env.example` for all configuration options.

Key variables:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `FERNET_SECRET_KEY` - Encryption key for secrets
- `BOOTSTRAP_ADMIN_TOKEN` - Initial admin token
- `LITELLM_MASTER_KEY` - Gateway authentication key

## License

MIT