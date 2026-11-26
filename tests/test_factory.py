"""Composition-root tests: honest mode selection and clean degradation."""

from __future__ import annotations

from workflow_ai import factory
from workflow_ai.config import Settings
from workflow_ai.errors import ProviderConfigError
from workflow_ai.factory import build_generation_stack
from workflow_ai.models import GenerationRequest


def test_offline_without_credentials(monkeypatch: object) -> None:
    monkeypatch.setattr(factory, "resolve_api_key", lambda settings: None)  # type: ignore[attr-defined]
    service, badge = build_generation_stack(Settings())

    assert badge == "🛠 Offline (rule-based)"
    result = service.generate(
        GenerationRequest(description="Process the order", category="Business Organizations")
    )
    assert result.provider == "rule"
    assert result.degraded is False


def test_ai_mode_with_key(monkeypatch: object) -> None:
    monkeypatch.setattr(factory, "resolve_api_key", lambda settings: "test-key")  # type: ignore[attr-defined]
    service, badge = build_generation_stack(Settings())

    assert badge == "⚡ AI"
    assert service._provider.name == "llm"  # type: ignore[attr-defined]
    assert service._fallback is not None  # type: ignore[attr-defined]


def test_ollama_endpoint_needs_no_key(monkeypatch: object) -> None:
    monkeypatch.setattr(factory, "resolve_api_key", lambda settings: None)  # type: ignore[attr-defined]
    service, badge = build_generation_stack(
        Settings(llm_base_url="http://localhost:11434/v1", llm_model="llama3.1")
    )

    assert badge == "⚡ AI"
    assert service._provider.model == "llama3.1"  # type: ignore[attr-defined]


def test_missing_sdk_degrades_to_offline(monkeypatch: object) -> None:
    monkeypatch.setattr(factory, "resolve_api_key", lambda settings: "test-key")  # type: ignore[attr-defined]

    def no_sdk(*args: object, **kwargs: object) -> None:
        raise ProviderConfigError("openai not installed")

    monkeypatch.setattr(factory, "LLMProvider", no_sdk)  # type: ignore[attr-defined]
    service, badge = build_generation_stack(Settings())

    assert badge == "🛠 Offline (rule-based)"
    assert service._provider.name == "rule"  # type: ignore[attr-defined]
