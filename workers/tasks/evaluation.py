"""Evaluation scoring tasks (T026).

Three scorers, matching the roles the methodology brief assigns each library
(1.6 — they are complementary, not competing):

  * `ragas_score`     — RAG metrics (faithfulness, answer relevance, context
                        precision/recall). Needs retrieved contexts.
  * `deepeval_score`  — hallucination / bias / toxicity, the CI-gate metrics.
  * `llm_judge_score` — a rubric-scored judge call through the gateway, which
                        is the only scorer that works with no reference answer
                        and no contexts.

Every scorer:
  * writes `EvaluationResult` rows with the right `metric_source`;
  * validates metric names against `METRIC_NAME_ALLOWLIST` before writing;
  * degrades loudly. A missing optional library or a judge failure records the
    reason and returns partial results — it never fails a whole benchmark run
    for one unscoreable item (Article XIV).

Version note: RAGAS/DeepEval were `[UNVERIFIED]` in the methodology brief.
Pinned in workers/requirements.txt against PyPI on 2026-08-01 (ragas 0.4.3,
deepeval 4.1.5). Both are imported lazily inside the task bodies so their
import cost and their optional dependencies stay off every other task's path.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from celery import shared_task

from app.models.enums import METRIC_NAME_ALLOWLIST, MetricSource
from app.models.evaluation import EvaluationResult
from app.repositories.evaluation import EvaluationResultRepository
from workers.db import run_async, session_scope
from workers.tracing import internal_span

logger = logging.getLogger(__name__)

#: Metric name -> RAGAS metric attribute. Kept explicit so a RAGAS rename
#: surfaces as a KeyError here rather than as silently missing scores.
RAGAS_METRICS = {
    "faithfulness": "faithfulness",
    "answer_relevance": "answer_relevancy",
    "context_precision": "context_precision",
    "context_recall": "context_recall",
}

DEEPEVAL_METRICS = ("hallucination_score", "bias_score", "toxicity_score")

JUDGE_SYSTEM_PROMPT = (
    "You are a strict evaluation judge. Score the assistant's answer from 0.0 "
    "to 1.0 on correctness, relevance and helpfulness. Respond with JSON only, "
    'in the form {"score": <float 0-1>, "rationale": "<one sentence>"}. '
    "Do not include any text outside the JSON object."
)


@shared_task(name="workers.tasks.evaluation.ragas_score")
def ragas_score(
    project_id: str,
    items: list[dict[str, Any]],
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    """Score RAG metrics for a batch of benchmark run items.

    `items` entries: `{benchmark_run_item_id, question, answer, contexts[],
    reference?}`.
    """
    wanted = [m for m in (metrics or list(RAGAS_METRICS)) if m in RAGAS_METRICS]
    if not wanted:
        return {"status": "skipped", "reason": "no RAGAS metrics requested"}

    scorable = [i for i in items if i.get("contexts")]
    skipped = len(items) - len(scorable)
    if not scorable:
        return {
            "status": "skipped",
            "reason": (
                "RAGAS metrics require retrieved contexts; none of the "
                f"{len(items)} items carried any."
            ),
        }

    try:
        from datasets import Dataset  # noqa: PLC0415 - deliberate lazy import
        from ragas import evaluate
        import ragas.metrics as ragas_metrics
    except ImportError as exc:
        logger.error("RAGAS scoring unavailable: %s", exc)
        return {"status": "unavailable", "reason": f"ragas import failed: {exc}"}

    with internal_span("evaluation.ragas", item_count=len(scorable)):
        dataset = Dataset.from_dict(
            {
                "question": [i.get("question", "") for i in scorable],
                "answer": [i.get("answer", "") for i in scorable],
                "contexts": [list(i.get("contexts") or []) for i in scorable],
                "ground_truth": [i.get("reference", "") for i in scorable],
            }
        )
        try:
            result = evaluate(
                dataset,
                metrics=[getattr(ragas_metrics, RAGAS_METRICS[m]) for m in wanted],
            )
            frame = result.to_pandas()
        except Exception as exc:  # noqa: BLE001 - scoring failure is data, not a crash
            logger.exception("RAGAS evaluation failed")
            return {"status": "error", "reason": str(exc)}

    rows: list[tuple[str, str, float, dict[str, Any] | None]] = []
    for position, item in enumerate(scorable):
        for metric in wanted:
            column = RAGAS_METRICS[metric]
            if column not in frame.columns:
                continue
            value = frame.iloc[position][column]
            if value is None or (isinstance(value, float) and value != value):  # NaN
                continue
            rows.append((item["benchmark_run_item_id"], metric, float(value), None))

    written = run_async(
        lambda: _write_results(uuid.UUID(project_id), MetricSource.RAGAS, rows)
    )
    return {"status": "ok", "written": written, "skipped_no_context": skipped}


@shared_task(name="workers.tasks.evaluation.deepeval_score")
def deepeval_score(
    project_id: str,
    items: list[dict[str, Any]],
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    """Score DeepEval metrics (hallucination / bias / toxicity)."""
    wanted = [m for m in (metrics or list(DEEPEVAL_METRICS)) if m in DEEPEVAL_METRICS]
    if not wanted:
        return {"status": "skipped", "reason": "no DeepEval metrics requested"}

    try:
        from deepeval.metrics import (  # noqa: PLC0415 - deliberate lazy import
            BiasMetric,
            HallucinationMetric,
            ToxicityMetric,
        )
        from deepeval.test_case import LLMTestCase
    except ImportError as exc:
        logger.error("DeepEval scoring unavailable: %s", exc)
        return {"status": "unavailable", "reason": f"deepeval import failed: {exc}"}

    factories = {
        "hallucination_score": HallucinationMetric,
        "bias_score": BiasMetric,
        "toxicity_score": ToxicityMetric,
    }

    rows: list[tuple[str, str, float, dict[str, Any] | None]] = []
    failures: list[str] = []

    with internal_span("evaluation.deepeval", item_count=len(items)):
        for item in items:
            contexts = list(item.get("contexts") or [])
            test_case = LLMTestCase(
                input=item.get("question", ""),
                actual_output=item.get("answer", ""),
                context=contexts or None,
                retrieval_context=contexts or None,
            )
            for metric_name in wanted:
                # HallucinationMetric is defined against a context; without one
                # it has nothing to contradict, so skip rather than emit a
                # meaningless zero.
                if metric_name == "hallucination_score" and not contexts:
                    continue
                try:
                    metric = factories[metric_name]()
                    metric.measure(test_case)
                    rows.append(
                        (
                            item["benchmark_run_item_id"],
                            metric_name,
                            float(metric.score),
                            {"reason": getattr(metric, "reason", None)},
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - per-metric isolation
                    failures.append(f"{metric_name}: {exc}")
                    logger.warning(
                        "DeepEval metric '%s' failed for item %s: %s",
                        metric_name,
                        item.get("benchmark_run_item_id"),
                        exc,
                    )

    written = run_async(
        lambda: _write_results(uuid.UUID(project_id), MetricSource.DEEPEVAL, rows)
    )
    return {
        "status": "ok" if not failures else "partial",
        "written": written,
        "failures": failures[:20],
    }


@shared_task(name="workers.tasks.evaluation.llm_judge_score")
def llm_judge_score(
    project_id: str,
    items: list[dict[str, Any]],
    judge_model_id: str,
) -> dict[str, Any]:
    """Rubric-score each answer with a judge model, through the gateway.

    Judging goes through the gateway like all other inference (ADR-001), so the
    judge call is itself routed, budgeted, traced and logged — a judge that
    bypassed the gateway would be invisible in cost analytics while still
    spending money.
    """
    return run_async(
        lambda: _judge(uuid.UUID(project_id), items, judge_model_id)
    )


async def _judge(
    project_id: uuid.UUID, items: list[dict[str, Any]], judge_model_id: str
) -> dict[str, Any]:
    from app.services.gateway_client import GatewayClient  # lazy: httpx client

    gateway = GatewayClient()
    rows: list[tuple[str, str, float, dict[str, Any] | None]] = []
    failures: list[str] = []

    for item in items:
        prompt = (
            f"Question:\n{item.get('question', '')}\n\n"
            f"Assistant answer:\n{item.get('answer', '')}\n"
        )
        if item.get("reference"):
            prompt += f"\nReference answer:\n{item['reference']}\n"

        result = await gateway.chat_completion(
            model_id=judge_model_id,
            prompt=prompt,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            temperature=0.0,
            project_id=project_id,
            origin="evaluation",
        )
        if not result.ok or not result.response_text:
            failures.append(f"{item.get('benchmark_run_item_id')}: {result.error}")
            continue

        parsed = _parse_judge_response(result.response_text)
        if parsed is None:
            failures.append(
                f"{item.get('benchmark_run_item_id')}: judge returned unparseable output"
            )
            continue

        score, rationale = parsed
        rows.append(
            (
                item["benchmark_run_item_id"],
                "llm_judge_score",
                score,
                {"rationale": rationale, "judge_model_id": judge_model_id},
            )
        )

    written = await _write_results(project_id, MetricSource.LLM_JUDGE, rows)
    return {
        "status": "ok" if not failures else "partial",
        "written": written,
        "failures": failures[:20],
    }


def _parse_judge_response(text: str) -> tuple[float, str | None] | None:
    """Extract `{"score": ..., "rationale": ...}` from a judge reply.

    Judges wrap JSON in prose or code fences often enough that a strict
    `json.loads` on the whole reply throws away usable scores; the regex
    fallback recovers the first JSON object in the text.
    """
    candidates = [text.strip()]
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or "score" not in payload:
            continue
        try:
            score = float(payload["score"])
        except (TypeError, ValueError):
            continue
        # Clamp rather than reject: a judge that answers 1.2 meant "excellent".
        score = min(max(score, 0.0), 1.0)
        rationale = payload.get("rationale")
        return score, str(rationale) if rationale is not None else None
    return None


async def _write_results(
    project_id: uuid.UUID,
    source: MetricSource,
    rows: list[tuple[str, str, float, dict[str, Any] | None]],
) -> int:
    """Persist scores, dropping any metric name outside the allowlist."""
    if not rows:
        return 0

    written = 0
    async with session_scope() as session:
        repo = EvaluationResultRepository(session)
        for item_id, metric_name, value, meta in rows:
            if metric_name not in METRIC_NAME_ALLOWLIST:
                logger.warning(
                    "Refusing to write unknown metric '%s' (source=%s).",
                    metric_name,
                    source.value,
                )
                continue
            await repo.add(
                EvaluationResult(
                    project_id=project_id,
                    benchmark_run_item_id=uuid.UUID(str(item_id)),
                    metric_name=metric_name,
                    metric_source=source,
                    value=value,
                    meta=meta,
                )
            )
            written += 1
    return written
