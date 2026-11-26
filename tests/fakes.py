"""Deterministic fakes for the OpenAI-compatible client interface.

No network, no API key, no cost. Used by unit tests and the eval harness.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from workflow_ai.models import GenerationResult, Project, Workflow, WorkflowStep


class FakeCompletions:
    """A ``chat.completions`` stand-in that replays scripted responses."""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("No scripted response left")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    """Minimal object exposing the SDK-shaped ``chat.completions.create``."""

    def __init__(self, responses: list[Any]) -> None:
        self.completions = FakeCompletions(responses)
        self.chat = SimpleNamespace(completions=self.completions)


def completion(content: str, *, tokens_in: int = 120, tokens_out: int = 60) -> Any:
    """Build a response object with the fields the provider reads."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=tokens_in, completion_tokens=tokens_out),
    )


def sample_result() -> GenerationResult:
    """A small, valid generation result for persistence/service tests."""
    workflow = Workflow(
        title="Business Organizations Workflow",
        domain="business",
        summary="Two steps.",
        steps=[
            WorkflowStep(id="s1", title="Process the order", depends_on=[]),
            WorkflowStep(id="s2", title="Generate the invoice", depends_on=["s1"]),
        ],
    )
    return GenerationResult(
        workflow=workflow,
        provider="rule",
        latency_ms=12.5,
        attempts=1,
        tokens_in=100,
        tokens_out=40,
        estimated_cost_usd=0.0001,
    )


def sample_project(owner_id: str | None = None) -> Project:
    """A saved project with realistic provenance metadata."""
    from workflow_ai.models import GenerationMetadata

    result = sample_result()
    return Project(
        owner_id=owner_id,
        workflow=result.workflow,
        metadata=GenerationMetadata.from_result(
            result, category="Business Organizations", prompt="Process the order. Invoice."
        ),
    )
