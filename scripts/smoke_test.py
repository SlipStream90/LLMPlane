#!/usr/bin/env python3
"""End-to-end smoke test (T047).

Validates the Phase 0 exit criteria: a request through the gateway is routed to
a provider, the response comes back, the completion is logged, and the
dashboard reflects it.

    python scripts/smoke_test.py \
        --backend http://localhost:8000 \
        --gateway http://localhost:4000 \
        --model gpt-4.1

Auth: pass `--api-key`, or `--bootstrap-token` to mint one on the spot.

Reporting rule for this script (Article V): every step prints PASS, FAIL or
SKIP with the reason. A step that could not run is never counted as a pass, and
the exit code is non-zero if any step failed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field

import httpx

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


@dataclass
class Report:
    steps: list[tuple[str, str, str]] = field(default_factory=list)

    def record(self, name: str, status: str, detail: str = "") -> None:
        self.steps.append((name, status, detail))
        symbol = {PASS: "[ok]", FAIL: "[!!]", SKIP: "[--]"}[status]
        print(f"{symbol} {status:4}  {name}" + (f"\n         {detail}" if detail else ""))

    @property
    def failed(self) -> bool:
        return any(status == FAIL for _, status, _ in self.steps)

    def summary(self) -> str:
        counts = {PASS: 0, FAIL: 0, SKIP: 0}
        for _, status, _ in self.steps:
            counts[status] += 1
        return (
            f"\n{counts[PASS]} passed, {counts[FAIL]} failed, {counts[SKIP]} skipped."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM Control Plane smoke test")
    parser.add_argument("--backend", default=os.getenv("BACKEND_URL", "http://localhost:8000"))
    parser.add_argument("--gateway", default=os.getenv("GATEWAY_URL", "http://localhost:4000"))
    parser.add_argument("--api-key", default=os.getenv("LLMPLANE_API_KEY"))
    parser.add_argument("--bootstrap-token", default=os.getenv("BOOTSTRAP_ADMIN_TOKEN"))
    parser.add_argument(
        "--model",
        default=os.getenv("SMOKE_MODEL"),
        help="Model id to call. Omit to auto-pick the first registered model.",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument(
        "--ingest-wait",
        type=float,
        default=15.0,
        help=(
            "Seconds to wait for the request to appear in the dashboard. "
            "Ingest is asynchronous by design (ADR-004)."
        ),
    )
    args = parser.parse_args()

    report = Report()
    client = httpx.Client(timeout=args.timeout)

    # 1. Backend health -----------------------------------------------------
    try:
        response = client.get(f"{args.backend}/health")
        response.raise_for_status()
        report.record("backend /health", PASS)
    except httpx.HTTPError as exc:
        report.record("backend /health", FAIL, str(exc))
        print(report.summary())
        return 1

    # 2. Backend readiness (per-dependency) --------------------------------
    try:
        ready = client.get(f"{args.backend}/ready").json()
        if ready.get("ready"):
            report.record("backend /ready", PASS, json.dumps(ready))
        else:
            report.record("backend /ready", FAIL, json.dumps(ready))
    except httpx.HTTPError as exc:
        report.record("backend /ready", FAIL, str(exc))

    # 3. Authentication -----------------------------------------------------
    api_key = args.api_key
    if not api_key and args.bootstrap_token:
        try:
            response = client.post(
                f"{args.backend}/api/v1/auth/bootstrap-key",
                headers={"X-Bootstrap-Token": args.bootstrap_token},
                json={"project_name": "Smoke Test", "project_slug": "smoke-test"},
            )
            if response.status_code == 201:
                api_key = response.json()["api_key"]["key"]
                report.record("bootstrap API key", PASS)
            else:
                report.record(
                    "bootstrap API key",
                    FAIL,
                    f"HTTP {response.status_code}: {response.text[:200]}",
                )
        except httpx.HTTPError as exc:
            report.record("bootstrap API key", FAIL, str(exc))

    if not api_key:
        report.record(
            "authenticate",
            FAIL,
            "No --api-key and no usable --bootstrap-token; the rest of the test "
            "cannot run.",
        )
        print(report.summary())
        return 1
    report.record("authenticate", PASS)
    auth = {"Authorization": f"Bearer {api_key}"}

    # 4. Providers registered ----------------------------------------------
    model_id = args.model
    try:
        providers = client.get(f"{args.backend}/api/v1/providers", headers=auth).json()
        if providers:
            report.record("providers registered", PASS, f"{len(providers)} provider(s)")
        else:
            report.record(
                "providers registered",
                FAIL,
                "No providers connected. Add one via POST /api/v1/providers first.",
            )
    except httpx.HTTPError as exc:
        report.record("providers registered", FAIL, str(exc))
        providers = []

    if not model_id:
        try:
            catalog = client.get(
                f"{args.backend}/api/v1/providers/model-catalog", headers=auth
            ).json()
            if catalog:
                model_id = catalog[0]["model_id"]
                report.record("resolve model", PASS, f"using '{model_id}'")
            else:
                report.record(
                    "resolve model",
                    FAIL,
                    "No models registered. Register one via "
                    "POST /api/v1/providers/{id}/models or pass --model.",
                )
        except httpx.HTTPError as exc:
            report.record("resolve model", FAIL, str(exc))

    # 5. Baseline dashboard count ------------------------------------------
    baseline = None
    try:
        summary = client.get(
            f"{args.backend}/api/v1/dashboard/summary", headers=auth
        ).json()
        baseline = summary["requests_today"]
        report.record("dashboard baseline", PASS, f"requests_today={baseline}")
    except (httpx.HTTPError, KeyError) as exc:
        report.record("dashboard baseline", FAIL, str(exc))

    # 6. Gateway completion (the actual OpenAI-compatible call) -------------
    marker = uuid.uuid4().hex[:8]
    if not model_id:
        report.record("gateway completion", SKIP, "no model id resolved")
    else:
        try:
            response = client.post(
                f"{args.gateway}/v1/chat/completions",
                headers={**auth, "Content-Type": "application/json"},
                json={
                    "model": model_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Reply with exactly: smoke-{marker}",
                        }
                    ],
                    "temperature": 0.0,
                    "max_tokens": 32,
                },
            )
            if response.status_code < 400:
                text = response.json()["choices"][0]["message"]["content"]
                report.record("gateway completion", PASS, f"response: {text[:80]!r}")
            else:
                report.record(
                    "gateway completion",
                    FAIL,
                    f"HTTP {response.status_code}: {response.text[:300]}",
                )
        except httpx.HTTPError as exc:
            report.record("gateway completion", FAIL, str(exc))

    # 7. Ingest -> dashboard delta -----------------------------------------
    # Eventually consistent by design (ADR-004): poll rather than assert once.
    if baseline is None:
        report.record("dashboard delta", SKIP, "no baseline captured")
    else:
        deadline = time.time() + args.ingest_wait
        observed = baseline
        while time.time() < deadline:
            try:
                observed = client.get(
                    f"{args.backend}/api/v1/dashboard/summary", headers=auth
                ).json()["requests_today"]
            except (httpx.HTTPError, KeyError):
                pass
            if observed > baseline:
                break
            time.sleep(1.0)

        if observed > baseline:
            report.record(
                "dashboard delta",
                PASS,
                f"requests_today {baseline} -> {observed}",
            )
        else:
            report.record(
                "dashboard delta",
                FAIL,
                f"No new request row within {args.ingest_wait:.0f}s. The gateway "
                "may not be emitting completion events to the Redis stream "
                "'requests:completed' (see backend/app/services/"
                "request_ingest_service.py for the event contract), or the "
                "backend consumer is disabled.",
            )

    # 8. Traces list --------------------------------------------------------
    try:
        traces = client.get(
            f"{args.backend}/api/v1/traces?limit=5", headers=auth
        ).json()
        count = len(traces.get("data", []))
        if count:
            report.record("traces list", PASS, f"{count} recent trace(s)")
        else:
            report.record(
                "traces list", FAIL, "No request rows exist yet — see previous step."
            )
    except httpx.HTTPError as exc:
        report.record("traces list", FAIL, str(exc))

    client.close()
    print(report.summary())
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
