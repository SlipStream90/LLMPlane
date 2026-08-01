"""GPU / VRAM / CPU telemetry polling (T021, ADR-003).

Alpha samples the host with `pynvml` (falling back to `nvidia-smi`) from a
Celery beat task, writing `GpuSample` rows and pushing a dashboard delta. DCGM
Exporter + Prometheus is the documented Phase 2+ upgrade path; because
`GpuSample` is data-source-agnostic, that swap changes this writer only, not
any reader.

CPU-only hosts are a first-class case, not an error: the task reports "no GPU
detected" once per poll at debug level, still records CPU/RAM via psutil, and
never raises (Article XIV, infrastructure.md 3).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any

from celery import shared_task

from app.models.deployment import GpuSample
from app.models.enums import DeploymentStatus
from app.repositories.deployment import DeploymentRepository, GpuSampleRepository
from app.repositories.provider import ProviderRepository
from app.services.provider_health_service import ProviderHealthService
from workers.db import run_async, session_scope
from workers.notify import publish

logger = logging.getLogger(__name__)


def read_gpu_stats() -> list[dict[str, Any]]:
    """Per-GPU utilisation and VRAM. Empty list when there is no GPU.

    Tries pynvml first (no subprocess, richer data); falls back to parsing
    `nvidia-smi --format=csv` when the bindings are absent but the CLI is
    present — a common state inside slim containers.
    """
    try:
        import pynvml

        pynvml.nvmlInit()
        try:
            samples = []
            for index in range(pynvml.nvmlDeviceGetCount()):
                handle = pynvml.nvmlDeviceGetHandleByIndex(index)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
                samples.append(
                    {
                        "gpu_index": index,
                        "gpu_util_pct": float(util.gpu),
                        "vram_used_mb": int(memory.used / (1024 * 1024)),
                        "vram_total_mb": int(memory.total / (1024 * 1024)),
                    }
                )
            return samples
        finally:
            pynvml.nvmlShutdown()
    except Exception as exc:  # noqa: BLE001 - pynvml raises many distinct types
        logger.debug("pynvml unavailable (%s); trying nvidia-smi.", exc)

    if shutil.which("nvidia-smi") is None:
        return []

    try:
        output = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("nvidia-smi call failed: %s", exc)
        return []

    samples = []
    for line in output.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 4:
            continue
        try:
            samples.append(
                {
                    "gpu_index": int(parts[0]),
                    "gpu_util_pct": float(parts[1]),
                    "vram_used_mb": int(float(parts[2])),
                    "vram_total_mb": int(float(parts[3])),
                }
            )
        except ValueError:
            continue
    return samples


def read_host_stats() -> dict[str, float | int | None]:
    try:
        import psutil

        memory = psutil.virtual_memory()
        return {
            "cpu_util_pct": float(psutil.cpu_percent(interval=None)),
            "ram_used_mb": int(memory.used / (1024 * 1024)),
        }
    except Exception:  # noqa: BLE001
        return {"cpu_util_pct": None, "ram_used_mb": None}


@shared_task(name="workers.tasks.telemetry.poll_gpu_stats")
def poll_gpu_stats() -> dict[str, Any]:
    return run_async(_poll)


async def _poll() -> dict[str, Any]:
    gpus = read_gpu_stats()
    host = read_host_stats()
    sampled_at = datetime.now(timezone.utc)

    async with session_scope() as session:
        deployments = [
            d
            for d in await DeploymentRepository(session).list_all()
            if d.status is DeploymentStatus.RUNNING
        ]
        # Alpha attributes host-level GPU samples to a running deployment when
        # exactly one is running on that GPU; otherwise the sample is recorded
        # at host level (deployment_id NULL). Guessing an attribution when
        # several models share a GPU would produce confidently wrong per-model
        # charts.
        by_gpu: dict[int, uuid.UUID | None] = {}
        for gpu in gpus:
            index = gpu["gpu_index"]
            candidates = [d for d in deployments if d.gpu_index == index]
            by_gpu[index] = candidates[0].id if len(candidates) == 1 else None

        repo = GpuSampleRepository(session)
        if gpus:
            for gpu in gpus:
                await repo.add(
                    GpuSample(
                        deployment_id=by_gpu.get(gpu["gpu_index"]),
                        sampled_at=sampled_at,
                        gpu_index=gpu["gpu_index"],
                        gpu_util_pct=gpu["gpu_util_pct"],
                        vram_used_mb=gpu["vram_used_mb"],
                        vram_total_mb=gpu["vram_total_mb"],
                        cpu_util_pct=host["cpu_util_pct"],
                        ram_used_mb=host["ram_used_mb"],
                    )
                )
        else:
            logger.debug("No GPU detected; recording host CPU/RAM only.")

    await publish(
        "dashboard",
        "telemetry",
        {
            "sampled_at": sampled_at.isoformat(),
            "gpu_available": bool(gpus),
            "gpus": gpus,
            "cpu_util_pct": host["cpu_util_pct"],
            "ram_used_mb": host["ram_used_mb"],
        },
    )
    return {
        "status": "ok",
        "gpu_count": len(gpus),
        "gpu_available": bool(gpus),
    }


@shared_task(name="workers.tasks.telemetry.check_provider_health")
def check_provider_health(provider_id: str) -> dict[str, Any]:
    return run_async(lambda: _check_one(uuid.UUID(provider_id)))


async def _check_one(provider_id: uuid.UUID) -> dict[str, Any]:
    async with session_scope() as session:
        provider = await ProviderRepository(session).get(provider_id)
        if provider is None:
            return {"status": "missing"}
        result = await ProviderHealthService(session).check(provider)
        return {
            "status": result.status.value,
            "latency_ms": result.latency_ms,
            "detail": result.detail,
        }


@shared_task(name="workers.tasks.telemetry.sweep_provider_health")
def sweep_provider_health() -> dict[str, Any]:
    """Celery beat: refresh every active provider's health.

    This is what makes `Provider.health_status` a written fact rather than a
    read-time computation (data-models.md 2).
    """
    return run_async(_sweep)


async def _sweep() -> dict[str, Any]:
    checked: dict[str, str] = {}
    async with session_scope() as session:
        providers = [p for p in await ProviderRepository(session).list_all() if p.is_active]
        service = ProviderHealthService(session)
        for provider in providers:
            try:
                result = await service.check(provider)
                checked[str(provider.id)] = result.status.value
            except Exception:  # noqa: BLE001 - one bad provider, not the sweep
                logger.exception("Health check failed for provider %s", provider.id)

    if checked:
        await publish("dashboard", "provider_health", {"providers": checked})
    return {"status": "ok", "checked": len(checked)}
