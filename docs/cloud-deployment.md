# Cloud Deployment (Demo VM)

Deploys the **site only** — frontend, backend API, and the LiteLLM gateway —
to a single cloud VM behind Caddy (automatic HTTPS). Postgres and Redis run
on the same VM as small containers. GPU-backed Celery workers, the beat
scheduler, and the docker-socket-proxy (one-click local model deployment)
are deliberately **not** run here — those stay something each self-hoster
runs on their own machine per `docs/deployment.md`, since they need Docker
socket access and often a GPU.

This uses `docker/docker-compose.cloud.yml`, an override on top of the base
`docker/docker-compose.yml` that:

- tags `workers` / `scheduler` / `docker-socket-proxy` with a `local-only`
  Compose profile so a plain `up` skips them
- passes the public domain into the frontend build as `NEXT_PUBLIC_*` build
  args (these are inlined into the JS bundle at build time — see
  `frontend/Dockerfile` — so they can't be set as a runtime env var)
- adds a `caddy` service that terminates TLS and reverse-proxies
  `/api/*` → backend, `/ws*` → backend, `/gateway/*` → gateway (optional),
  everything else → frontend, per `docker/Caddyfile`

You'll need a domain name pointed at the VM's IP before Caddy can issue a
cert (an A record; a few minutes to propagate).

---

## Option A: GCP (Compute Engine)

### 1. Prerequisites

- `gcloud` CLI installed and authenticated: `gcloud auth login`
- A GCP project with billing enabled: `gcloud config set project <PROJECT_ID>`

### 2. Create the VM

```bash
gcloud compute instances create llmplane-demo \
  --zone=us-central1-a \
  --machine-type=e2-medium \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB \
  --tags=llmplane-web
```

`e2-medium` (2 vCPU / 4GB) is enough for frontend + backend + gateway +
Postgres + Redis at demo traffic levels. Bump to `e2-standard-2` if it's
slow.

### 3. Open firewall ports

```bash
gcloud compute firewall-rules create llmplane-web \
  --allow=tcp:80,tcp:443 \
  --target-tags=llmplane-web \
  --description="LLM Control Plane demo site"
```

SSH (22) is already open by default via the `default-allow-ssh` rule on most
GCP projects — confirm with `gcloud compute firewall-rules list`.

### 4. Reserve a static IP and point DNS

```bash
gcloud compute addresses create llmplane-demo-ip --region=us-central1
gcloud compute addresses describe llmplane-demo-ip --region=us-central1 --format="get(address)"
```

Create an A record for your domain (e.g. `demo.yourdomain.com`) pointing at
that IP, then re-run `instances create` with `--address=llmplane-demo-ip`, or
attach it after the fact via `gcloud compute instances add-access-config`.

### 5. SSH in and install Docker

```bash
gcloud compute ssh llmplane-demo --zone=us-central1-a
```

Then, on the VM:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
```

Continue with the shared **[Common setup](#common-setup-both-clouds)**
section below.

---

## Option B: AWS (EC2)

### 1. Prerequisites

- AWS CLI installed and configured: `aws configure`
- An existing key pair, or create one:
  `aws ec2 create-key-pair --key-name llmplane-demo --query 'KeyMaterial' --output text > llmplane-demo.pem && chmod 400 llmplane-demo.pem`

### 2. Create a security group

```bash
aws ec2 create-security-group \
  --group-name llmplane-web \
  --description "LLM Control Plane demo site"

aws ec2 authorize-security-group-ingress --group-name llmplane-web --protocol tcp --port 22  --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-name llmplane-web --protocol tcp --port 80  --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-name llmplane-web --protocol tcp --port 443 --cidr 0.0.0.0/0
```

Restrict port 22 to your own IP (`<your-ip>/32`) instead of `0.0.0.0/0` if
you want to lock down SSH.

### 3. Launch the instance

```bash
aws ec2 run-instances \
  --image-id ami-0e2c8caa4b6378d8c \
  --count 1 \
  --instance-type t3.medium \
  --key-name llmplane-demo \
  --security-groups llmplane-web \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=30}' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=llmplane-demo}]'
```

The AMI above is Ubuntu 24.04 LTS in `us-east-1` — check
[Ubuntu's AMI locator](https://cloud-images.ubuntu.com/locator/ec2/) for the
current AMI ID in your region, they roll frequently.

### 4. Allocate an Elastic IP and point DNS

```bash
aws ec2 allocate-address
aws ec2 associate-address --instance-id <instance-id> --allocation-id <allocation-id>
```

Create an A record for your domain pointing at that Elastic IP.

### 5. SSH in and install Docker

```bash
ssh -i llmplane-demo.pem ubuntu@<elastic-ip>
```

Then, on the instance:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
```

Continue with the shared **[Common setup](#common-setup-both-clouds)**
section below.

---

## Common setup (both clouds)

### 6. Clone the repo and configure env files

```bash
git clone https://github.com/SlipStream90/LLMPlane.git
cd LLMPlane
cp backend/.env.example backend/.env
cp docker/.env.example docker/.env
```

Generate secrets the same way as local dev (see `docs/deployment.md` step
3), and fill in `backend/.env` / `docker/.env` the same way — with one
addition: set the site domain and public URLs in `docker/.env`:

```bash
cat >> docker/.env <<'EOF'

# ── Cloud demo: public domain ──────────────────────────────────
SITE_DOMAIN=demo.yourdomain.com
PUBLIC_API_URL=https://demo.yourdomain.com/api/v1
PUBLIC_WS_URL=wss://demo.yourdomain.com/ws
PUBLIC_GATEWAY_URL=https://demo.yourdomain.com/gateway
EOF
```

Also set, in `backend/.env`:

```bash
CORS_ORIGINS=https://demo.yourdomain.com
```

### 7. Bring up the stack (site only, no workers)

```bash
cd docker
docker compose -f docker-compose.yml -f docker-compose.cloud.yml up -d --build
```

Caddy requests/renews the TLS cert automatically on first boot — give it a
minute, then check:

```bash
docker compose logs -f caddy
```

### 8. Run migrations and bootstrap an admin key

```bash
docker compose exec backend alembic upgrade head
curl -X POST https://demo.yourdomain.com/api/v1/auth/bootstrap-key \
  -H "Authorization: Bearer <BOOTSTRAP_ADMIN_TOKEN>"
```

### 9. Verify

| Check | URL |
|---|---|
| Frontend | `https://demo.yourdomain.com` |
| Backend health | `https://demo.yourdomain.com/api/api/v1/...` or directly `docker compose exec backend curl localhost:8000/health` |
| Cert issued | `curl -vI https://demo.yourdomain.com 2>&1 \| grep -i "SSL certificate"` |

### 10. What's intentionally missing from this deployment

- **No GPU workers / scheduler** — background eval jobs and one-click local
  model deploys won't run on the demo VM. That's by design: those are the
  features a self-hoster gets by cloning the repo and running the full
  `docker-compose.yml` locally per `docs/deployment.md`.
- **No docker-socket-proxy** — nothing on this VM touches the Docker socket.
- Observability (`prometheus`/`grafana`/`otel-collector`) is still in the
  base compose file and will start along with everything else unless you
  also profile those off — keep them if you want to show the dashboards
  publicly (put Grafana behind its own auth, which it already has), drop
  them with the same `profiles:` trick if you want a leaner VM.

### 11. Updating

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.cloud.yml up -d --build
docker compose exec backend alembic upgrade head
```
