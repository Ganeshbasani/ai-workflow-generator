"""Unit tests for generation orchestration."""

from __future__ import annotations

from typing import Any

import pytest

from workflow_ai.config import Settings
from workflow_ai.errors import (
    DocumentAnalysisError,
    DocumentAnalysisUnavailableError,
    InputValidationError,
    ProviderConnectionError,
    ProviderError,
    ProviderQuotaError,
    ProviderTimeoutError,
    WorkflowValidationError,
)
from workflow_ai.models import GenerationRequest, Workflow, WorkflowStep
from workflow_ai.providers import RuleProvider
from workflow_ai.services import GenerationService


def _service(provider: Any | None = None) -> GenerationService:
    settings = Settings()
    return GenerationService(provider or RuleProvider(settings), settings)


def _request() -> GenerationRequest:
    return GenerationRequest(
        description="Start. Process payment. Generate invoice.",
        category="Business Organizations",
    )


def test_result_contains_provider_and_timing() -> None:
    result = _service().generate(_request())

    assert result.provider == "rule"
    assert result.degraded is False
    assert result.latency_ms >= 0
    assert [step.title for step in result.workflow.steps] == [
        "Start",
        "Process payment",
        "Generate invoice",
    ]


def test_input_errors_propagate() -> None:
    with pytest.raises(InputValidationError):
        _service().generate(GenerationRequest(description="", category="Hospitals"))


def test_invalid_workflow_is_rejected() -> None:
    class BadProvider:
        name = "bad"

        def generate(self, request: GenerationRequest) -> Workflow:
            return Workflow(
                title="Bad",
                domain="general",
                steps=[
                    WorkflowStep(id="s1", title="A"),
                    WorkflowStep(id="s1", title="B"),
                ],
            )

    with pytest.raises(WorkflowValidationError, match="unique"):
        _service(BadProvider()).generate(_request())


def test_unexpected_provider_errors_are_wrapped() -> None:
    class BrokenProvider:
        name = "broken"

        def generate(self, request: GenerationRequest) -> Workflow:
            raise RuntimeError("secret database details")

    with pytest.raises(ProviderError, match="Workflow generation failed"):
        _service(BrokenProvider()).generate(_request())


def test_empty_workflow_is_rejected_instead_of_being_saved() -> None:
    with pytest.raises(InputValidationError) as error:
        _service().generate(GenerationRequest(description="a", category="Hospitals"))
    assert "clear action" in error.value.user_message


def test_meta_request_is_rejected_before_provider_runs() -> None:
    class ShouldNotRunProvider:
        name = "must-not-run"

        def generate(self, request: GenerationRequest) -> Workflow:
            raise AssertionError("Provider must not receive a generic meta request")

    with pytest.raises(InputValidationError) as error:
        _service(ShouldNotRunProvider()).generate(
            GenerationRequest(description="Create the workflow", category="Software Industries")
        )
    assert "clear action" in error.value.user_message


def test_document_analysis_requires_ai_and_never_falls_back_to_rules() -> None:
    class BrokenAIProvider:
        name = "llm"

        def generate(self, request: GenerationRequest) -> Workflow:
            raise ProviderError("connection refused")

    class MustNotFallback:
        name = "rule"

        def generate(self, request: GenerationRequest) -> Workflow:
            raise AssertionError("Document text must never be treated as rule input")

    settings = Settings()
    service = GenerationService(BrokenAIProvider(), settings, fallback=MustNotFallback())
    with pytest.raises(DocumentAnalysisError) as error:
        service.generate(
            GenerationRequest(
                description="",
                category="Business Organizations",
                document_text="Support checks refund eligibility and issues a refund.",
                require_ai=True,
            )
        )
    assert "No offline workflow was created" in error.value.user_message

    offline = _service()
    with pytest.raises(DocumentAnalysisUnavailableError):
        offline.generate(
            GenerationRequest(
                description="",
                category="Business Organizations",
                document_text="Support checks refund eligibility.",
                require_ai=True,
            )
        )


def test_document_analysis_reports_provider_quota_without_offline_fallback() -> None:
    class QuotaProvider:
        name = "llm"

        def generate(self, request: GenerationRequest) -> Workflow:
            raise ProviderQuotaError("provider quota")

    settings = Settings()
    service = GenerationService(QuotaProvider(), settings, fallback=RuleProvider(settings))
    with pytest.raises(DocumentAnalysisError) as error:
        service.generate(
            GenerationRequest(
                description="",
                category="Business Organizations",
                document_text="Support checks refund eligibility.",
                require_ai=True,
            )
        )
    assert "no available quota or credits" in error.value.user_message
    assert "No offline workflow was created" in error.value.user_message


def test_document_analysis_explains_ollama_timeout_without_offline_fallback() -> None:
    class SlowOllamaProvider:
        name = "llm"

        def generate(self, request: GenerationRequest) -> Workflow:
            raise ProviderTimeoutError("local request timeout")

    settings = Settings(llm_base_url="http://host.docker.internal:11434/v1")
    service = GenerationService(SlowOllamaProvider(), settings, fallback=RuleProvider(settings))
    with pytest.raises(DocumentAnalysisError) as error:
        service.generate(
            GenerationRequest(
                description="",
                category="Business Organizations",
                document_text="Support checks refund eligibility.",
                require_ai=True,
            )
        )

    assert "local Ollama model took too long" in error.value.user_message
    assert "smaller model" in error.value.user_message
    assert "No offline workflow was created" in error.value.user_message


def test_document_analysis_explains_local_ollama_connection_failure() -> None:
    class DisconnectedOllamaProvider:
        name = "llm"

        def generate(self, request: GenerationRequest) -> Workflow:
            raise ProviderConnectionError("connection refused")

    settings = Settings(llm_base_url="http://host.docker.internal:11434/v1")
    service = GenerationService(
        DisconnectedOllamaProvider(), settings, fallback=RuleProvider(settings)
    )
    with pytest.raises(DocumentAnalysisError) as error:
        service.generate(
            GenerationRequest(
                description="",
                category="Business Organizations",
                document_text="Support checks refund eligibility.",
                require_ai=True,
            )
        )

    assert "could not reach Ollama" in error.value.user_message
    assert "host.docker.internal:11434/v1" in error.value.user_message
    assert "No offline workflow was created" in error.value.user_message


def test_document_analysis_explains_invalid_model_output_without_fallback() -> None:
    class InvalidOutputProvider:
        name = "llm"

        def generate(self, request: GenerationRequest) -> Workflow:
            raise ProviderError("workflow response failed schema validation")

    settings = Settings(llm_base_url="http://host.docker.internal:11434/v1")
    service = GenerationService(InvalidOutputProvider(), settings, fallback=RuleProvider(settings))
    with pytest.raises(DocumentAnalysisError) as error:
        service.generate(
            GenerationRequest(
                description="",
                category="Business Organizations",
                document_text="Support checks refund eligibility.",
                require_ai=True,
            )
        )

    assert "complete, valid workflow" in error.value.user_message
    assert "shorter document focused on one process" in error.value.user_message
    assert "No offline workflow was created" in error.value.user_message
