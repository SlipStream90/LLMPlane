"""Enumerations shared by models, schemas and workers.

These are Python `StrEnum`s persisted as native Postgres enum types (except
where data-models.md explicitly calls for an open string with an app-level
allowlist — see `MetricName`).
"""

from __future__ import annotations

from enum import StrEnum


class ProviderType(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROQ = "groq"
    MISTRAL = "mistral"
    COHERE = "cohere"
    OPENROUTER = "openrouter"
    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"
    OLLAMA = "ollama"
    VLLM = "vllm"
    #: Generic escape hatch for any provider backed by a plugin that isn't one
    #: of the first-party types above (ADR-003). Real identity/behavior comes
    #: from `Provider.plugin_id`, not from proliferating enum values.
    CUSTOM = "custom"


#: Providers backed by a locally-deployed container rather than a hosted API.
LOCAL_PROVIDER_TYPES = frozenset({ProviderType.OLLAMA, ProviderType.VLLM})


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class DeploymentBackend(StrEnum):
    OLLAMA = "ollama"
    VLLM = "vllm"


class DeploymentStatus(StrEnum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class RoutingStrategy(StrEnum):
    """Alpha strategy set (data-models.md 2).

    `custom_python` and `ai_router` are Phase 2+ and deliberately absent — an
    enum value with no implementation behind it is a promise the API cannot
    keep.
    """

    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    FALLBACK = "fallback"
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    COST_THRESHOLD = "cost_threshold"
    LATENCY_THRESHOLD = "latency_threshold"


class RequestStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class DatasetFormat(StrEnum):
    CSV = "csv"
    JSON = "json"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class ItemStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class MetricSource(StrEnum):
    RAGAS = "ragas"
    DEEPEVAL = "deepeval"
    PROMPTFOO = "promptfoo"
    COMPUTED = "computed"
    LLM_JUDGE = "llm_judge"
    HUMAN = "human"


class ApiKeyScope(StrEnum):
    GATEWAY = "gateway"
    ADMIN = "admin"


#: App-level allowlist for `EvaluationResult.metric_name`.
#: data-models.md keeps this column an open string on purpose (the RAGAS /
#: DeepEval / Promptfoo metric sets evolve faster than a DB enum can be
#: migrated) — validation happens here, in application code.
METRIC_NAME_ALLOWLIST: frozenset[str] = frozenset(
    {
        # computed from the request itself
        "latency_ms",
        "cost_usd",
        "input_tokens",
        "output_tokens",
        "ttft_ms",
        "tokens_per_second",
        # RAGAS
        "faithfulness",
        "answer_relevance",
        "context_precision",
        "context_recall",
        # DeepEval
        "hallucination_score",
        "bias_score",
        "toxicity_score",
        "answer_correctness",
        # classic text-overlap metrics
        "bleu",
        "rouge",
        "bert_score",
        # judge / human
        "llm_judge_score",
        "human_rating",
    }
)
