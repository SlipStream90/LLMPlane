# Docker Socket Security Review — LLM Control Plane (Alpha)

**Task:** T012  
**Status:** APPROVED  
**Priority:** HIGH — highest blast-radius surface in the system

---

## 1. Context

The `backend` and `workers` containers need Docker socket access to manage local model deployments (Ollama/vLLM containers). This is the most dangerous permission in the system because Docker socket access is equivalent to root on the host.

## 2. Threat Model

| Threat | Severity | Mitigation |
|---|---|---|
| Arbitrary container execution | CRITICAL | Allow-listed image templates only |
| Container escape to host | HIGH | Scoped Docker context, no `--privileged` |
| Resource exhaustion (crypto mining) | HIGH | Resource limits, image allow-list |
| Supply chain (malicious image) | HIGH | Pin images to official repos only |
| Lateral movement to other services | MEDIUM | Isolated Docker network |

## 3. Allowed Image Templates

Only these images may be deployed via the control plane:

| Backend Type | Allowed Image | Registry |
|---|---|---|
| `ollama` | `ollama/ollama:latest` | Docker Hub (official) |
| `vllm` | `vllm/vllm-openai:latest` | Docker Hub (official) |

**No other images are permitted.** The request body must never contain an arbitrary `image` field. The `backend_type` enum (`ollama` | `vllm`) maps to a fixed image template in the deployment service.

## 4. Implementation Constraints

### 4.1 No Arbitrary Image Names

```python
# WRONG — never do this
container = docker.run(image=request.image_name)

# CORRECT — fixed mapping
IMAGE_MAP = {
    "ollama": "ollama/ollama:latest",
    "vllm": "vllm/vllm-openai:latest",
}
container = docker.run(image=IMAGE_MAP[deployment.backend_type])
```

### 4.2 Scoped Docker Context

- Use the Docker SDK's `tls_config` with minimal permissions
- Mount Docker socket as read-write only where strictly necessary
- Never expose Docker socket to the frontend

### 4.3 Resource Limits

All deployed containers must have:
- Memory limits (`--memory`)
- CPU limits (`--cpus`)
- GPU device requests (scoped, not `--privileged`)
- Restart policy: `unless-stopped` (no `always`)

### 4.4 Network Isolation

- Deployed model containers join the `llcp-internal` network only
- No host network mode
- Port mapping: only the assigned port range (e.g., 8100-8199)

### 4.5 Container Naming

Prefix all containers with `llmplane-` for easy identification:
```
llmplane-ollama-{deployment_id_short}
llmplane-vllm-{deployment_id_short}
```

## 5. Docker Compose Configuration — IMPLEMENTED

The Docker socket proxy is now implemented using `tecnativa/docker-socket-proxy`:

```yaml
docker-socket-proxy:
  image: tecnativa/docker-socket-proxy:latest
  restart: unless-stopped
  environment:
    CONTAINERS: 1   # Allow container management
    EXEC: 0          # Block exec into containers
    VOLUMES: 0       # Block volume management
    NETWORKS: 0      # Block network management
    INFO: 1          # Allow system info
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
  ports:
    - "127.0.0.1:2375:2375"
  networks:
    - llcp-internal
```

**Backend and workers** connect to Docker via the proxy:
```yaml
environment:
  - DOCKER_HOST=http://docker-socket-proxy:2375
```

The direct socket mount (`docker_socket` volume) has been removed from both `backend` and `workers` services.

## 6. Defense-in-Depth Summary

| Layer | Status | Description |
|---|---|---|
| Docker socket proxy | IMPLEMENTED | `tecnativa/docker-socket-proxy` with `CONTAINERS=1, EXEC=0, VOLUMES=0` |
| Image allow-list | IMPLEMENTED | Fixed `IMAGE_MAP` — no arbitrary images from request body |
| Resource limits | IMPLEMENTED | Memory, CPU, GPU device requests on all deployed containers |
| Network isolation | IMPLEMENTED | `llcp-internal` network — no host mode |
| Container naming | IMPLEMENTED | `llmplane-` prefix for all managed containers |
| Authorization plugin | DEFERRED | Phase 2+ — Docker `AuthorizationPlugin` for daemon-level enforcement |

## 7. Future Hardening (Phase 2+)

- Use Docker's `AuthorizationPlugin` to enforce image allow-list at the Docker daemon level
- Move to Kubernetes with PodSecurityPolicies for production deployments
- Implement audit logging for all Docker API calls
- Add network policy enforcement for inter-container communication

## 8. Sign-off

This document reviews the security implications of Docker socket access for local model deployment control. The socket proxy approach (technativa/docker-socket-proxy with scoped permissions) combined with the application-layer allow-list provides the minimum viable security boundary for alpha.

**Approved for implementation with the constraints documented above.**
