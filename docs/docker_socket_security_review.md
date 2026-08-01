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

- Deployed model containers join the `internal` network only
- No host network mode
- Port mapping: only the assigned port range (e.g., 8100-8199)

### 4.5 Container Naming

Prefix all containers with `llmplane-` for easy identification:
```
llmplane-ollama-{deployment_id_short}
llmplane-vllm-{deployment_id_short}
```

## 5. Docker Compose Configuration

```yaml
backend:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
```

This grants full Docker API access. The mitigation is in the application layer (allow-listed images only).

## 6. Future Hardening (Phase 2+)

- Use Docker's `AuthorizationPlugin` to enforce image allow-list at the Docker daemon level
- Consider `docker-socket-proxy` (technovessel/docker-socket-proxy) as an intermediary
- Move to Kubernetes with PodSecurityPolicies for production deployments
- Implement audit logging for all Docker API calls

## 7. Sign-off

This document reviews the security implications of Docker socket access for local model deployment control. The accept-list approach (fixed image templates only, no arbitrary image names from request body) is the minimum viable security boundary for alpha.

**Approved for implementation with the constraints documented above.**
