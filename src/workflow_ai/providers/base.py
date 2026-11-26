"""Provider contract shared by the rule engine and (later) LLM providers."""

from __future__ import annotations

from typing import Protocol

from ..models import GenerationRequest, Workflow


class WorkflowProvider(Protocol):
    """Anything that can turn a generation request into a workflow graph."""

    name: str

    def generate(self, request: GenerationRequest) -> Workflow:
        """Generate a workflow. Implementations may raise ProviderError."""
        ...
