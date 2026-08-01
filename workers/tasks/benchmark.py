"""Benchmark run fan-out (T028) — the Celery chord.

Shape (ARCHITECTURE.md 1.3):

    chord(
        header = [run_single_item.s(item_id) for item in run.items],   # parallel
        body   = aggregate_benchmark.s(run_id),                        # callback
    )

The header calls the gateway once per (dataset row x prompt version x model x
temperature) combination; the callback computes the request-derived metrics and
dispatches the RAGAS / DeepEval / judge scorers, then flips the run to
`complete`.

Why a chord rather than hand-rolled orchestration in the API: the callback must
fire exactly once, after every header task has finished, including the ones
that failed. That is precisely what Celery's Canvas provides and what the
methodology brief kept Celery for (1.5).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from celery import chord, shared_task

from app.models.benchmark import BenchmarkRunItem
from app.models.enums import ItemStatus, MetricSource, RunStatus
from app.models.evaluation import EvaluationResult
from app.repositories.benchmark import (
    BenchmarkDatasetRepository,
    BenchmarkRunItemRepository,
    BenchmarkRunRepository,
)
from app.repositories.evaluation import EvaluationResultRepository
from app.repositories.prompt import PromptVersionRepository
from app.repositories.provider import ProviderModelRepository
from app.services.dataset_service import read_dataset
from app.services.gateway_client import GatewayClient, estimate_cost
from workers.db import run_async, session_scope
from workers.notify import publish
from workers.tracing import internal_span

logger = logging.getLogger(__name__)

#: Dataset column names checked, in order, for the input question and the
#: reference answer. Datasets in the wild use all of these spellings.
QUESTION_COLUMNS = ("question", "prompt", "input", "query", "text")
REFERENCE_COLUMNS = ("reference", "answer", "expected", "ground_truth", "output")
CONTEXT_COLUMNS = ("contexts", "context", "retrieved_contexts")

#: Publish progress at most this often (in completed items) to avoid flooding
#: the WebSocket on a large grid.
PROGRESS_EVERY = 5


@shared_task(name="workers.tasks.benchmark.launch_benchmark_run")
def launch_benchmark_run(run_id: str) -> dict[str, Any]:
    """Build and dispatch the chord for an already-materialised run.

    Items were created by the API so `total_items` is exact from the moment the
    run was accepted; this task only schedules them.
    """
    item_ids = run_async(lambda: _prepare(uuid.UUID(run_id)))
    if not item_ids:
        return {"status": "empty", "run_id": run_id}

    header = [run_single_item.s(item_id) for item_id in item_ids]
    chord(header)(aggregate_benchmark.s(run_id))
    return {"status": "dispatched", "run_id": run_id, "items": len(item_ids)}


async def _prepare(run_id: uuid.UUID) -> list[str]:
    async with session_scope() as session:
        runs = BenchmarkRunRepository(session)
        run = await runs.get(run_id)
        if run is None:
            logger.error("launch_benchmark_run: run %s not found", run_id)
            return []
        await runs.mark_running(run)
        items = await BenchmarkRunItemRepository(session).list_for_run(run_id)
        ids = [str(item.id) for item in items]

    await publish(
        f"benchmark:{run_id}",
        "progress",
        {"completed": 0, "total": len(ids), "status": RunStatus.RUNNING.value},
    )
    return ids


@shared_task(name="workers.tasks.benchmark.run_single_item", bind=True, max_retries=2)
def run_single_item(self, item_id: str) -> dict[str, Any]:  # noqa: ANN001
    """One combination: render the prompt, call the gateway, store the result.

    Returns a dict rather than raising on a provider failure — a chord whose
    header task raises does not run its callback, which would leave the run
    stuck in `running` forever. Failure is recorded on the item and reported
    in the return value instead.
    """
    return run_async(lambda: _run_item(uuid.UUID(item_id)))


async def _run_item(item_id: uuid.UUID) -> dict[str, Any]:
    async with session_scope() as session:
        items = BenchmarkRunItemRepository(session)
        item = await items.get(item_id)
        if item is None:
            return {"item_id": str(item_id), "status": "missing"}

        run = await BenchmarkRunRepository(session).get(item.benchmark_run_id)
        if run is None:
            return {"item_id": str(item_id), "status": "missing_run"}

        dataset = await BenchmarkDatasetRepository(session).get(run.dataset_id)
        model = await ProviderModelRepository(session).get(item.provider_model_id)
        version = (
            await PromptVersionRepository(session).get(item.prompt_version_id)
            if item.prompt_version_id
            else None
        )

        project_id = run.project_id
        run_id = run.id
        temperature = item.temperature
        row_index = item.dataset_row_index
        item.status = ItemStatus.RUNNING
        await session.flush()

    if dataset is None or model is None:
        await _fail_item(item_id, "dataset or model no longer exists")
        return {"item_id": str(item_id), "status": "failed"}

    try:
        parsed = read_dataset(dataset.storage_path, dataset.source_format)
        row = parsed.rows[row_index]
    except (FileNotFoundError, IndexError) as exc:
        await _fail_item(item_id, f"dataset row unavailable: {exc}")
        return {"item_id": str(item_id), "status": "failed"}

    question = _first_present(row, QUESTION_COLUMNS) or _join_row(row)
    reference = _first_present(row, REFERENCE_COLUMNS)
    contexts = _contexts(row)
    prompt, system_prompt = _render_prompt(version, row, question)

    with internal_span(
        "benchmark.item", item_id=str(item_id), model_id=model.model_id
    ):
        result = await GatewayClient().chat_completion(
            model_id=model.model_id,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            project_id=project_id,
            origin=f"benchmark:{run_id}",
        )

    cost = result.cost_usd
    if cost is None and result.ok:
        cost = estimate_cost(
            result.input_tokens,
            result.output_tokens,
            model.input_price_per_1m,
            model.output_price_per_1m,
        )

    async with session_scope() as session:
        items = BenchmarkRunItemRepository(session)
        item = await items.get(item_id)
        if item is not None:
            item.response_text = result.response_text
            item.status = ItemStatus.COMPLETE if result.ok else ItemStatus.FAILED
            item.error_message = result.error
            await session.flush()

    await _publish_progress(run_id)

    return {
        "item_id": str(item_id),
        "status": "complete" if result.ok else "failed",
        "project_id": str(project_id),
        "question": question,
        "answer": result.response_text,
        "reference": reference,
        "contexts": contexts,
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost_usd": cost,
        "error": result.error,
    }


@shared_task(name="workers.tasks.benchmark.aggregate_benchmark")
def aggregate_benchmark(results: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    """Chord callback: write computed metrics, dispatch scorers, close the run."""
    return run_async(lambda: _aggregate(results, uuid.UUID(run_id)))


async def _aggregate(results: list[dict[str, Any]], run_id: uuid.UUID) -> dict[str, Any]:
    async with session_scope() as session:
        runs = BenchmarkRunRepository(session)
        run = await runs.get(run_id)
        if run is None:
            return {"status": "missing", "run_id": str(run_id)}
        project_id = run.project_id
        requested_metrics = list(run.metrics or [])
        judge_model_id = run.judge_model_id

    succeeded = [r for r in results if r.get("status") == "complete"]
    failed = [r for r in results if r.get("status") != "complete"]

    # Request-derived metrics are always recorded: they cost nothing extra and
    # they are what the leaderboard's cost/latency columns read.
    computed = 0
    async with session_scope() as session:
        repo = EvaluationResultRepository(session)
        for result in succeeded:
            for metric_name, value in (
                ("latency_ms", result.get("latency_ms")),
                ("cost_usd", result.get("cost_usd")),
                ("input_tokens", result.get("input_tokens")),
                ("output_tokens", result.get("output_tokens")),
            ):
                if value is None:
                    continue
                await repo.add(
                    EvaluationResult(
                        project_id=project_id,
                        benchmark_run_item_id=uuid.UUID(result["item_id"]),
                        metric_name=metric_name,
                        metric_source=MetricSource.COMPUTED,
                        value=float(value),
                    )
                )
                computed += 1

    dispatched: list[str] = []
    if succeeded and requested_metrics:
        payload = [
            {
                "benchmark_run_item_id": r["item_id"],
                "question": r.get("question") or "",
                "answer": r.get("answer") or "",
                "reference": r.get("reference"),
                "contexts": r.get("contexts") or [],
            }
            for r in succeeded
        ]

        from workers.tasks import evaluation as evaluation_tasks

        ragas_wanted = [m for m in requested_metrics if m in evaluation_tasks.RAGAS_METRICS]
        if ragas_wanted:
            evaluation_tasks.ragas_score.delay(str(project_id), payload, ragas_wanted)
            dispatched.append("ragas")

        deepeval_wanted = [
            m for m in requested_metrics if m in evaluation_tasks.DEEPEVAL_METRICS
        ]
        if deepeval_wanted:
            evaluation_tasks.deepeval_score.delay(
                str(project_id), payload, deepeval_wanted
            )
            dispatched.append("deepeval")

        if "llm_judge_score" in requested_metrics and judge_model_id:
            evaluation_tasks.llm_judge_score.delay(
                str(project_id), payload, judge_model_id
            )
            dispatched.append("llm_judge")

    async with session_scope() as session:
        runs = BenchmarkRunRepository(session)
        await runs.refresh_progress(run_id)
        run = await runs.get(run_id)
        if run is not None:
            # A run with some failures is `complete`, not `failed`: partial
            # results are the normal outcome of a multi-provider sweep and are
            # still worth reading. Only a total wipeout is a failed run.
            all_failed = bool(results) and not succeeded
            await runs.mark_complete(
                run,
                failed=all_failed,
                error=(
                    f"all {len(failed)} items failed; see item error messages"
                    if all_failed
                    else None
                ),
            )

    await publish(
        f"benchmark:{run_id}",
        "progress",
        {
            "completed": len(results),
            "total": len(results),
            "status": RunStatus.FAILED.value
            if (results and not succeeded)
            else RunStatus.COMPLETE.value,
            "succeeded": len(succeeded),
            "failed": len(failed),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return {
        "status": "ok",
        "run_id": str(run_id),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "computed_metrics_written": computed,
        "scorers_dispatched": dispatched,
    }


# ---------------------------------------------------------------------------
async def _fail_item(item_id: uuid.UUID, message: str) -> None:
    async with session_scope() as session:
        repo = BenchmarkRunItemRepository(session)
        item = await repo.get(item_id)
        if item is not None:
            item.status = ItemStatus.FAILED
            item.error_message = message[:2000]
            await session.flush()


async def _publish_progress(run_id: uuid.UUID) -> None:
    async with session_scope() as session:
        done, total = await BenchmarkRunRepository(session).refresh_progress(run_id)

    if done % PROGRESS_EVERY and done != total:
        return
    await publish(
        f"benchmark:{run_id}",
        "progress",
        {"completed": done, "total": total, "status": RunStatus.RUNNING.value},
    )


def _first_present(row: dict[str, Any], candidates: tuple[str, ...]) -> str | None:
    for key in candidates:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _join_row(row: dict[str, Any]) -> str:
    """Fallback when no recognised question column exists: use the whole row.

    Better than failing the item — the operator can see in the response what
    was actually sent and fix their column naming.
    """
    return "\n".join(f"{k}: {v}" for k, v in row.items())


def _contexts(row: dict[str, Any]) -> list[str]:
    raw = None
    for key in CONTEXT_COLUMNS:
        if row.get(key) not in (None, ""):
            raw = row[key]
            break
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(c) for c in raw]
    return [str(raw)]


def _render_prompt(
    version: Any, row: dict[str, Any], question: str
) -> tuple[str, str | None]:
    """Substitute `{{var}}` placeholders from the dataset row.

    An unmatched placeholder is left as-is rather than replaced with an empty
    string, so a column-name typo shows up in the recorded prompt instead of
    silently producing a truncated question.
    """
    if version is None:
        return question, None

    content = version.content
    for variable in version.variables or []:
        if variable in row:
            content = content.replace(f"{{{{{variable}}}}}", str(row[variable]))
    # Convention: a template with no declared variables gets the question
    # appended, so a bare system-style template still receives the row.
    if not (version.variables or []):
        content = f"{content}\n\n{question}"
    return content, version.system_prompt
