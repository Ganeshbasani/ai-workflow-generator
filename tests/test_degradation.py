"""Degradation-ladder tests: every failure path is typed and covered."""

from __future__ import annotations

import pytest

from workflow_ai.config import Settings
from workflow_ai.errors import (
    CostCeilingError,
    ProviderError,
    RateLimitError,
    WorkflowValidationError,
)
from workflow_ai.limits import CostTracker, RateLimiter
from workflow_ai.models import GenerationRequest, Workflow, WorkflowStep
from workflow_ai.providers import RuleProvider
from workflow_ai.services import GenerationService


class FailingProvider:
    name = "llm"
    model = "gpt-4o-mini"
    last_tokens_in = 100
    last_tokens_out = 50
    last_cost_usd = 0.01
    last_attempts = 3

    def __init__(self, error: Exception | None = None, workflow: Workflow | None = None) -> None:
        self.error = error
        self.workflow = workflow

    def generate(self, request: GenerationRequest) -> Workflow:
        if self.error is not None:
            raise self.error
        assert self.workflow is not None
        return self.workflow


def _request() -> GenerationRequest:
    return GenerationRequest(
        description="Start. Process payment.",
        category="Business Organizations",
        session_id="degradation-test",
    )


def _service(  # type: ignore[type-arg]
    primary: object, *, fallback: object | None = None, **settings: object
) -> GenerationService:
    return GenerationService(
        primary,  # type: ignore[arg-type]
        Settings(**settings),  # type: ignore[arg-type]
        fallback=fallback if fallback is not None else RuleProvider(Settings()),  # type: ignore[arg-type]
        rate_limiter=RateLimiter(),
        cost_tracker=CostTracker(),
    )


def test_falls_back_on_provider_error() -> None:
    primary = FailingProvider(error=ProviderError("sk-secret-key leaked internally"))
    result = _service(primary).generate(_request())

    assert result.provider == "rule"
    assert result.requested_provider == "llm"
    assert result.degraded is True
    assert "sk-secret-key" not in str(result)
    assert result.fallback_reason
    assert result.attempts == 4  # 3 LLM attempts + 1 fallback
    assert result.tokens_in == 100
    assert result.estimated_cost_usd == pytest.approx(0.01)
    assert result.workflow.step_titles()


def test_falls_back_on_invalid_graph() -> None:
    invalid = Workflow(
        title="Bad",
        domain="general",
        steps=[WorkflowStep(id="s1", title="A"), WorkflowStep(id="s1", title="B")],
    )
    result = _service(FailingProvider(workflow=invalid)).generate(_request())

    assert result.degraded is True
    assert result.provider == "rule"
    assert result.workflow.steps


def test_no_fallback_propagates_typed_error() -> None:
    service = GenerationService(FailingProvider(error=ProviderError("down")), Settings())  # type: ignore[arg-type]
    with pytest.raises(ProviderError, match="down"):
        service.generate(_request())

    service = GenerationService(
        FailingProvider(error=WorkflowValidationError("bad graph")),  # type: ignore[arg-type]
        Settings(),
    )
    with pytest.raises(WorkflowValidationError, match="bad graph"):
        service.generate(_request())


def test_rate_limit_blocks_before_provider() -> None:
    service = GenerationService(
        FailingProvider(error=ProviderError("should not be called")),  # type: ignore[arg-type]
        Settings(max_requests_per_session=0),
        fallback=RuleProvider(Settings()),
        rate_limiter=RateLimiter(),
        cost_tracker=CostTracker(),
    )
    with pytest.raises(RateLimitError):
        service.generate(_request())


def test_cost_ceiling_blocks_before_provider() -> None:
    tracker = CostTracker()
    tracker.record(5.0)
    service = GenerationService(
        RuleProvider(Settings()),  # type: ignore[arg-type]
        Settings(daily_cost_ceiling_usd=1.0),
        rate_limiter=RateLimiter(),
        cost_tracker=tracker,
    )
    with pytest.raises(CostCeilingError):
        service.generate(_request())


def test_successful_primary_is_not_degraded() -> None:
    result = _service(RuleProvider(Settings()), fallback=FailingProvider()).generate(_request())

    assert result.degraded is False
    assert result.provider == "rule"
    assert result.fallback_reason is None
    assert result.attempts == 1
