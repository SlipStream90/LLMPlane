"""SQLAlchemy models.

Importing this package imports every model module, which is what makes
`Base.metadata` complete for Alembic autogenerate. `workers/` imports these
same classes (ARCHITECTURE.md 3.2) rather than owning a second schema copy.
"""

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.benchmark import BenchmarkDataset, BenchmarkRun, BenchmarkRunItem
from app.models.deployment import Deployment, GpuSample
from app.models.enums import (
    METRIC_NAME_ALLOWLIST,
    ApiKeyScope,
    DatasetFormat,
    DeploymentBackend,
    DeploymentStatus,
    HealthStatus,
    ItemStatus,
    MetricSource,
    ProviderType,
    RequestStatus,
    RoutingStrategy,
    RunStatus,
)
from app.models.evaluation import EvaluationResult
from app.models.experiment import Experiment, ExperimentRun
from app.models.playground import PlaygroundComparison, PlaygroundResponse
from app.models.prompt import Prompt, PromptVersion
from app.models.provider import Provider, ProviderModel
from app.models.request import Request
from app.models.routing import RoutingPolicy
from app.models.tenancy import APIKey, Organization, Project

__all__ = [
    "METRIC_NAME_ALLOWLIST",
    "APIKey",
    "ApiKeyScope",
    "Base",
    "BenchmarkDataset",
    "BenchmarkRun",
    "BenchmarkRunItem",
    "DatasetFormat",
    "Deployment",
    "DeploymentBackend",
    "DeploymentStatus",
    "EvaluationResult",
    "Experiment",
    "ExperimentRun",
    "GpuSample",
    "HealthStatus",
    "ItemStatus",
    "MetricSource",
    "Organization",
    "PlaygroundComparison",
    "PlaygroundResponse",
    "Project",
    "Prompt",
    "PromptVersion",
    "Provider",
    "ProviderModel",
    "ProviderType",
    "Request",
    "RequestStatus",
    "RoutingPolicy",
    "RoutingStrategy",
    "RunStatus",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
]
