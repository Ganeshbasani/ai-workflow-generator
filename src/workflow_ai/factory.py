"""Composition root: choose the provider chain and build the service."""

from __future__ import annotations

from .config import Settings, resolve_api_key
from .errors import ProviderConfigError
from .persistence import SqliteProjectRepository
from .providers import LLMProvider, RuleProvider, WorkflowProvider
from .services import GenerationService, ProjectService, RunService, WorkflowEditor


def build_generation_stack(settings: Settings) -> tuple[GenerationService, str]:
    """Return ``(service, badge_label)`` for the current configuration.

    AI mode is used only when a key or a compatible endpoint is configured
    *and* the SDK is importable. Every other case degrades cleanly to the
    deterministic offline engine with an honest UI badge.
    """
    api_key = resolve_api_key(settings)
    if api_key or settings.llm_base_url:
        try:
            primary: WorkflowProvider = LLMProvider(settings, api_key=api_key)
        except ProviderConfigError:
            primary = RuleProvider(settings)
        else:
            service = GenerationService(primary, settings, fallback=RuleProvider(settings))
            return service, "⚡ AI"

    return GenerationService(RuleProvider(settings), settings), "🛠 Offline (rule-based)"


def build_project_stack(
    settings: Settings,
) -> tuple[ProjectService, WorkflowEditor, RunService]:
    """Return ``(projects, editor, runs)`` backed by the configured database."""
    repository = SqliteProjectRepository(settings.database_path)
    projects = ProjectService(repository)
    return projects, WorkflowEditor(projects), RunService(projects)
