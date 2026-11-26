"""Dependency injection for the API: one service stack per application."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from ..config import Settings
from ..factory import build_generation_stack
from ..persistence import ProjectRepository, SqliteProjectRepository
from ..services import GenerationService, ProjectService, RunService, WorkflowEditor
from .metrics import Metrics


@dataclass(slots=True)
class ApiServices:
    """The exact same services the Streamlit UI uses, injected into routes."""

    generation: GenerationService
    projects: ProjectService
    editor: WorkflowEditor
    runs: RunService
    repository: ProjectRepository | None = None

    @classmethod
    def build(cls, settings: Settings) -> ApiServices:
        """Compose the offline/AI generation chain plus persisted project stack."""
        generation, _badge = build_generation_stack(settings)
        repository = SqliteProjectRepository(settings.database_path)
        projects = ProjectService(repository)
        return cls(
            generation=generation,
            projects=projects,
            editor=WorkflowEditor(projects),
            runs=RunService(projects),
            repository=repository,
        )

    def close(self) -> None:
        """Release repository resources on application shutdown."""
        close = getattr(self.repository, "close", None)
        if callable(close):
            close()


def get_services(request: Request) -> ApiServices:
    """Return the application's service stack."""
    services = getattr(request.app.state, "services", None)
    if not isinstance(services, ApiServices):
        raise RuntimeError("API services are not configured")
    return services


def get_owner_id(request: Request) -> str | None:
    """Return the optional owner scope established by middleware."""
    owner_id = getattr(request.state, "owner_id", None)
    return owner_id if isinstance(owner_id, str) else None


def get_request_id(request: Request) -> str:
    """Return the correlation id established by middleware."""
    request_id = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) else "-"


def get_metrics(request: Request) -> Metrics:
    """Return the application's metrics registry."""
    metrics = getattr(request.app.state, "metrics", None)
    if not isinstance(metrics, Metrics):
        raise RuntimeError("API metrics are not configured")
    return metrics
