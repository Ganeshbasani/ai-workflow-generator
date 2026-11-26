"""Unit tests for the native Ollama chat adapter."""

from __future__ import annotations

import json
from typing import Any

import pytest

from workflow_ai.providers.ollama_api import chat_completion


def test_native_chat_disables_thinking_and_requests_json(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        @staticmethod
        def read() -> bytes:
            return json.dumps(
                {
                    "message": {"content": '{"title": "Example"}'},
                    "prompt_eval_count": 12,
                    "eval_count": 4,
                }
            ).encode()

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("workflow_ai.providers.ollama_api.urlopen", fake_urlopen)

    response = chat_completion(
        base_url="http://host.docker.internal:11434/v1",
        model="qwen3.5:4b",
        messages=[{"role": "user", "content": "Make a workflow."}],
        timeout=120,
        temperature=0,
        max_tokens=2_000,
        context_tokens=4_096,
        json_mode=True,
    )

    assert captured["url"] == "http://host.docker.internal:11434/api/chat"
    assert captured["payload"]["think"] is False
    assert captured["payload"]["format"] == "json"
    assert captured["payload"]["options"]["num_predict"] == 2_000
    assert captured["payload"]["options"]["num_ctx"] == 4_096
    assert response.choices[0].message.content == '{"title": "Example"}'
    assert response.usage.prompt_tokens == 12
    assert response.usage.completion_tokens == 4


def test_native_chat_rejects_empty_assistant_content(monkeypatch: Any) -> None:
    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        @staticmethod
        def read() -> bytes:
            return b'{"message":{"content":""}}'

    monkeypatch.setattr(
        "workflow_ai.providers.ollama_api.urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(ValueError, match="no assistant content"):
        chat_completion(
            base_url="http://host.docker.internal:11434/v1",
            model="qwen3.5:4b",
            messages=[{"role": "user", "content": "Reply with OK."}],
            timeout=20,
            temperature=0,
            max_tokens=8,
        )
