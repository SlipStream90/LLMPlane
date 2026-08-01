"""Repository layer — one class per aggregate root (ARCHITECTURE.md 3.1).

Routes and Celery tasks both go through these; neither builds SQL inline. That
is what makes the "modular monolith today, separable services later" claim in
ARCHITECTURE.md 1 actually true rather than aspirational.
"""

from app.repositories.base import BaseRepository, Page, decode_cursor, encode_cursor
from app.repositories.benchmark import (
    BenchmarkDatasetRepository,
    BenchmarkRunItemRepository,
    BenchmarkRunRepository,
)
from app.repositories.deployment import DeploymentRepository, GpuSampleRepository
from app.repositories.evaluation import EvaluationResultRepository
from app.repositories.experiment import ExperimentRepository, ExperimentRunRepository
from app.repositories.playground import (
    PlaygroundComparisonRepository,
    PlaygroundResponseRepository,
)
from app.repositories.prompt import (
    PromptRepository,
    PromptVersionRepository,
    extract_variables,
)
from app.repositories.provider import ProviderModelRepository, ProviderRepository
from app.repositories.request import RequestRepository
from app.repositories.routing import RoutingPolicyRepository
from app.repositories.tenancy import (
    APIKeyRepository,
    OrganizationRepository,
    ProjectRepository,
)

__all__ = [
    "APIKeyRepository",
    "BaseRepository",
    "BenchmarkDatasetRepository",
    "BenchmarkRunItemRepository",
    "BenchmarkRunRepository",
    "DeploymentRepository",
    "EvaluationResultRepository",
    "ExperimentRepository",
    "ExperimentRunRepository",
    "GpuSampleRepository",
    "OrganizationRepository",
    "Page",
    "PlaygroundComparisonRepository",
    "PlaygroundResponseRepository",
    "ProjectRepository",
    "PromptRepository",
    "PromptVersionRepository",
    "ProviderModelRepository",
    "ProviderRepository",
    "RequestRepository",
    "RoutingPolicyRepository",
    "decode_cursor",
    "encode_cursor",
    "extract_variables",
]
