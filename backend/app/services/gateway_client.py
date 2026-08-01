"""HTTP client for the gateway (LiteLLM Proxy sibling container, ADR-001).

`backend` never imports `litellm` and never calls a provider directly. Every
completion — playground, benchmark, evaluation judging — goes through the same
gateway the user's own SDK calls, so routing policy, retries, budgets and OTel
instrumentation apply uniformly to platform-originated traffic too.

Cost: LiteLLM returns its computed cost on the `x-litellm-response-cost`
response header. When that header is absent (older tags, or a model with no
pricing registered), `cost_usd` is None and the caller falls back to the
`ProviderModel` price catalog — see `estimate_cost`.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.tracing import current_trace_id, llm_span, record_llm_result

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CompletionResult:
    """Outcome of one gateway call. A failure is a value, not an exception —
    callers fan out over many models and must be able to record per-model
    failure without aborting the batch (Article XIV)."""

    model_id: str
    ok: bool
    response_text: str | None = None
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None
    latency_ms: int = 0
    trace_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class GatewayClient:
    """Thin async wrapper over the gateway's OpenAI-compatible surface."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_s: float | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.gateway_base_url).rstrip("/")
        self._api_key = api_key or settings.litellm_master_key
        self.timeout_s = timeout_s or settings.gateway_timeout_s

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    async def chat_completion(
        self,
        *,
        model_id: str,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        project_id: uuid.UUID | None = None,
        origin: str = "api",
        timeout_s: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> CompletionResult:
        """One non-streaming completion. Never raises for an upstream failure."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        # Tag platform-originated traffic so dashboards can separate it from a
        # user's own SDK calls (Request.tags).
        headers = self._headers({"x-llmplane-origin": origin})
        if project_id:
            headers["x-llmplane-project-id"] = str(project_id)

        started = time.perf_counter()
        with llm_span(
            "chat",
            system="llmplane-gateway",
            request_model=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            project_id=project_id,
            origin=origin,
        ) as span:
            owns_client = client is None
            http = client or httpx.AsyncClient(timeout=timeout_s or self.timeout_s)
            try:
                response = await http.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=body,
                    headers=headers,
                    timeout=timeout_s or self.timeout_s,
                )
                latency_ms = int((time.perf_counter() - started) * 1000)

                if response.status_code >= 400:
                    detail = _safe_error_text(response)
                    record_llm_result(span, latency_ms=latency_ms, error=detail)
                    return CompletionResult(
                        model_id=model_id,
                        ok=False,
                        error=f"gateway returned {response.status_code}: {detail}",
                        latency_ms=latency_ms,
                        trace_id=current_trace_id(),
                    )

                payload = response.json()
                text = _first_message_content(payload)
                usage = payload.get("usage") or {}
                cost = _header_cost(response)

                record_llm_result(
                    span,
                    response_model=payload.get("model"),
                    input_tokens=usage.get("prompt_tokens"),
                    output_tokens=usage.get("completion_tokens"),
                    cost_usd=cost,
                    latency_ms=latency_ms,
                )
                return CompletionResult(
                    model_id=model_id,
                    ok=True,
                    response_text=text,
                    input_tokens=int(usage.get("prompt_tokens") or 0),
                    output_tokens=int(usage.get("completion_tokens") or 0),
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    trace_id=current_trace_id(),
                    raw=payload,
                )
            except httpx.TimeoutException:
                latency_ms = int((time.perf_counter() - started) * 1000)
                record_llm_result(span, latency_ms=latency_ms, error="timeout")
                return CompletionResult(
                    model_id=model_id,
                    ok=False,
                    error=f"timed out after {timeout_s or self.timeout_s:.0f}s",
                    latency_ms=latency_ms,
                    trace_id=current_trace_id(),
                )
            except httpx.HTTPError as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                record_llm_result(span, latency_ms=latency_ms, error=str(exc))
                return CompletionResult(
                    model_id=model_id,
                    ok=False,
                    error=f"gateway unreachable: {exc}",
                    latency_ms=latency_ms,
                    trace_id=current_trace_id(),
                )
            finally:
                if owns_client:
                    await http.aclose()

    async def list_models(self) -> list[str]:
        """Model ids the gateway currently serves (`GET /v1/models`)."""
        async with httpx.AsyncClient(timeout=10.0) as http:
            response = await http.get(
                f"{self.base_url}/v1/models", headers=self._headers()
            )
            response.raise_for_status()
            data = response.json().get("data", [])
            return [m["id"] for m in data if "id" in m]

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as http:
                response = await http.get(f"{self.base_url}/health/liveliness")
                return response.status_code < 400
        except httpx.HTTPError:
            return False


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    input_price_per_1m: Decimal | float | None,
    output_price_per_1m: Decimal | float | None,
) -> float | None:
    """Fallback cost from the local price catalog.

    Returns None rather than 0.0 when pricing is unknown — a missing price and
    a genuinely free call are different facts, and showing "$0.00" for the
    former quietly corrupts every cost aggregate downstream.
    """
    if input_price_per_1m is None and output_price_per_1m is None:
        return None
    in_price = float(input_price_per_1m or 0)
    out_price = float(output_price_per_1m or 0)
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000


def _first_message_content(payload: dict[str, Any]) -> str | None:
    choices = payload.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    content = message.get("content")
    return content if isinstance(content, str) else None


def _header_cost(response: httpx.Response) -> float | None:
    raw = response.headers.get("x-litellm-response-cost")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _safe_error_text(response: httpx.Response, limit: int = 500) -> str:
    """Upstream error text, truncated.

    Provider errors occasionally echo request material back; truncating bounds
    both log noise and the blast radius of that.
    """
    try:
        payload = response.json()
        error = payload.get("error")
        if isinstance(error, dict):
            return str(error.get("message", error))[:limit]
        return str(error or payload)[:limit]
    except ValueError:
        return response.text[:limit]
