"""Contract tests for the versioned FastAPI boundary."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from workflow_ai.api import ApiServices, create_app
from workflow_ai.config import Settings
from workflow_ai.errors import (
    CostCeilingError,
    DocumentError,
    DocumentTooLargeError,
    InputValidationError,
    ProviderError,
    RateLimitError,
    WorkflowValidationError,
)
from workflow_ai.logging_config import RequestIdFilter, sanitize_request_id
from workflow_ai.models import GenerationRequest, GenerationResult, Workflow, WorkflowStep


@contextmanager
def _client(tmp_path: Path, **overrides: Any) -> Iterator[TestClient]:
    values: dict[str, Any] = {
        "database_path": str(tmp_path / "api.db"),
        "llm_model": "gpt-4o-mini",
        "llm_api_key": None,
        "llm_base_url": None,
    }
    values.update(overrides)
    settings = Settings(**values)
    services = ApiServices.build(settings)
    with TestClient(create_app(settings=settings, services=services)) as client:
        yield client


def _payload(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "description": "Customer registers. Places order. Makes payment. Generate invoice.",
        "category": "Business Organizations",
        "additional_context": "",
        "session_id": "api-contract",
        "persist": True,
    }
    payload.update(changes)
    return payload


def _generate(client: TestClient, *, headers: dict[str, str] | None = None) -> str:
    response = client.post("/api/v1/workflows/generate", json=_payload(), headers=headers)
    assert response.status_code == 201, response.text
    project_id = response.json()["project_id"]
    assert isinstance(project_id, str)
    return project_id


def test_openapi_docs_health_and_ready(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.get("/health").json() == {"status": "ok"}
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json() == {"status": "ready", "provider": "rule"}

        schema = client.get("/openapi.json").json()
        assert schema["info"]["title"] == "AI Workflow Generator API"
        assert "/api/v1/workflows/generate" in schema["paths"]
        assert "/api/v1/workflows/{project_id}/export" in schema["paths"]
        assert client.get("/docs").status_code == 200


def test_ai_setup_endpoints_are_honest_without_provider_configuration(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        status = client.get("/api/v1/ai/status")
        assert status.status_code == 200
        assert status.json()["configured"] is False
        assert "not AI" in status.json()["message"]

        tested = client.post("/api/v1/ai/test")
        assert tested.status_code == 200
        assert tested.json()["connected"] is False
        assert tested.json()["available_models"] == []


def test_openai_connection_uses_default_endpoint_when_base_url_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    class Models:
        @staticmethod
        def list() -> Any:
            return SimpleNamespace(data=[SimpleNamespace(id="gpt-4o-mini")])

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)
            self.models = Models()
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **request: captured.update(chat_request=request)
                )
            )

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)
    with _client(tmp_path, llm_api_key="test-key") as client:
        response = client.post("/api/v1/ai/test")

    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["generation_ready"] is True
    assert response.json()["model_available"] is True
    assert captured["base_url"] is None


def test_ollama_connection_check_disables_thinking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.models = SimpleNamespace(
                list=lambda: SimpleNamespace(data=[SimpleNamespace(id="qwen3.5:4b")])
            )

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)
    monkeypatch.setattr(
        "workflow_ai.api.app.ollama_chat_completion",
        lambda **request: captured.update(request),
    )
    with _client(
        tmp_path,
        llm_base_url="http://host.docker.internal:11434/v1",
        llm_model="qwen3.5:4b",
    ) as client:
        response = client.post("/api/v1/ai/test")

    assert response.status_code == 200
    assert response.json()["generation_ready"] is True
    assert captured["base_url"] == "http://host.docker.internal:11434/v1"
    assert captured["max_tokens"] == 32
    assert captured["timeout"] == 120
    assert captured["context_tokens"] == 4_096
    assert captured["json_mode"] is True


def test_ai_connection_reports_provider_credit_exhaustion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.models = SimpleNamespace(
                list=lambda: SimpleNamespace(data=[SimpleNamespace(id="gpt-4o-mini")])
            )

            def create(**request: Any) -> None:
                raise type("RateLimitError", (Exception,), {})(
                    "You have no credits remaining"
                )

            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)
    with _client(tmp_path, llm_api_key="test-key") as client:
        response = client.post("/api/v1/ai/test")

    assert response.status_code == 200
    assert response.json()["connected"] is False
    assert response.json()["generation_ready"] is False
    assert "no API credits" in response.json()["message"]


def test_generation_rejects_empty_briefs_with_a_useful_message(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.post("/api/v1/workflows/generate", json=_payload(description="a"))

        assert response.status_code == 422
        assert "clear action" in response.json()["message"]
        assert client.get("/api/v1/workflows").json()["items"] == []


def test_document_only_upload_requests_ai_analysis_and_never_offline_draft(
    tmp_path: Path,
) -> None:
    with _client(tmp_path) as client:
        response = client.post(
            "/api/v1/workflows/generate-upload",
            data={"category": "Business Organizations", "description": ""},
            files={
                "file": ("refund-process.txt", b"Support checks refund eligibility.", "text/plain")
            },
        )

        assert response.status_code == 502
        assert "Document analysis needs a connected AI model" in response.json()["message"]
        assert client.get("/api/v1/workflows").json()["items"] == []


def test_document_upload_passes_extracted_text_and_guidance_to_generator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _client(tmp_path) as client:
        observed: list[GenerationRequest] = []

        def capture(request: GenerationRequest) -> GenerationResult:
            observed.append(request)
            return GenerationResult(
                workflow=Workflow(
                    title="Refund process",
                    domain="business",
                    steps=[WorkflowStep(id="s1", title="Review the refund request")],
                ),
                provider="llm",
                model="test-model",
            )

        monkeypatch.setattr(client.app.state.services.generation, "generate", capture)
        response = client.post(
            "/api/v1/workflows/generate-upload",
            data={
                "category": "Business Organizations",
                "description": "Focus on the refund process.",
                "additional_context": "Follow the approved refund policy.",
                "session_id": "document-contract",
            },
            files={
                "file": (
                    "refund-process.txt",
                    b"Support checks eligibility and issues a refund.",
                    "text/plain",
                )
            },
            headers={"X-Owner-Id": "document-contract"},
        )

        assert response.status_code == 201, response.text
        assert len(observed) == 1
        assert observed[0].document_text == "Support checks eligibility and issues a refund."
        assert observed[0].description == "Focus on the refund process."
        assert observed[0].additional_context == "Follow the approved refund policy."
        assert observed[0].require_ai is True
        project_id = response.json()["project_id"]
        assert client.delete(
            f"/api/v1/workflows/{project_id}", headers={"X-Owner-Id": "document-contract"}
        ).json()["ok"] is True


def test_generate_list_get_and_all_exports_are_consistent(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        project_id = _generate(client)
        title = client.get(f"/api/v1/workflows/{project_id}").json()["workflow"]["title"]

        listed = client.get("/api/v1/workflows")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()["items"]] == [project_id]

        expected = {
            "json": "application/json",
            "csv": "text/csv",
            "pdf": "application/pdf",
            "markdown": "text/markdown",
            "mermaid": "text/plain",
        }
        bodies: dict[str, bytes] = {}
        for export_format, media_type in expected.items():
            response = client.get(
                f"/api/v1/workflows/{project_id}/export",
                params={"format": export_format},
            )
            assert response.status_code == 200, response.text
            assert response.headers["content-type"].startswith(media_type)
            assert 'attachment; filename="' in response.headers["content-disposition"]
            bodies[export_format] = response.content

        exported = json.loads(bodies["json"])
        assert exported["title"] == title
        assert len(exported["steps"]) >= 3
        assert b"step_id,title,type" in bodies["csv"]
        assert bodies["pdf"].startswith(b"%PDF")
        assert b"flowchart TD" in bodies["mermaid"]
        assert f"# {title}".encode() in bodies["markdown"]


def test_generate_can_be_stateless(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.post("/api/v1/workflows/generate", json=_payload(persist=False))
        assert response.status_code == 201
        assert response.json()["project"] is None
        assert response.json()["project_id"] is None
        assert client.get("/api/v1/workflows").json()["items"] == []


def test_owner_header_scopes_projects(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        alice = {"X-Owner-Id": "alice"}
        bob = {"X-Owner-Id": "bob"}
        project_id = _generate(client, headers=alice)

        alice_items = client.get("/api/v1/workflows", headers=alice).json()["items"]
        assert [item["id"] for item in alice_items] == [project_id]
        assert client.get("/api/v1/workflows", headers=bob).json()["items"] == []

        forbidden = client.get(f"/api/v1/workflows/{project_id}", headers=bob)
        assert forbidden.status_code == 422
        assert forbidden.json()["error"] == "validation_error"
        assert client.get(f"/api/v1/workflows/{project_id}", headers=alice).status_code == 200

        bad_owner = client.get("/api/v1/workflows", headers={"X-Owner-Id": "x" * 129})
        assert bad_owner.status_code == 400
        assert bad_owner.json()["error"] == "invalid_owner_id"


def test_validated_update_endpoints_reuse_services(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        project_id = _generate(client)
        base = f"/api/v1/workflows/{project_id}"
        original_count = len(client.get(base).json()["workflow"]["steps"])

        renamed = client.patch(base, json={"title": "Renamed workflow"})
        assert renamed.status_code == 200
        assert renamed.json()["title"] == "Renamed workflow"

        patched = client.patch(
            f"{base}/steps/s1",
            json={"title": "Updated first step", "step_type": "decision"},
        )
        assert patched.status_code == 200
        assert patched.json()["workflow"]["steps"][0]["title"] == "Updated first step"

        branch = client.put(
            f"{base}/steps/s1/branch",
            json={"condition": "Payment failed?", "on_true": "s2", "on_false": "s3"},
        )
        assert branch.status_code == 200
        decision = branch.json()["workflow"]["steps"][0]
        assert decision["condition"] == "Payment failed?"
        assert decision["on_false"] == "s3"

        added = client.post(f"{base}/steps", json={"title": "Archive the order"})
        assert added.status_code == 201
        new_step = added.json()["workflow"]["steps"][-1]
        assert new_step["title"] == "Archive the order"

        moved = client.post(f"{base}/steps/{new_step['id']}/move", json={"direction": -1})
        assert moved.status_code == 200
        assert moved.json()["workflow"]["steps"][-2]["id"] == new_step["id"]

        deleted = client.delete(f"{base}/steps/{new_step['id']}")
        assert deleted.status_code == 200
        assert len(deleted.json()["workflow"]["steps"]) == original_count

        workflow = client.get(base).json()["workflow"]
        workflow["steps"][1]["depends_on"] = ["missing_step"]
        invalid = client.put(base, json={"workflow": workflow})
        assert invalid.status_code == 502
        assert invalid.json()["error"] == "workflow_validation_error"

        assert client.delete(base).json()["ok"] is True
        assert client.get(base).status_code == 422


def test_execution_endpoints_record_transitions(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        project_id = _generate(client)
        base = f"/api/v1/workflows/{project_id}"

        started = client.post(f"{base}/runs")
        assert started.status_code == 201
        assert started.json()["runs"][0]["outcome"] == "in_progress"

        updated = client.patch(
            f"{base}/runs/steps/s1", json={"status": "done", "notes": "completed"}
        )
        assert updated.status_code == 200
        run = updated.json()["runs"][0]
        assert run["transitions"][0]["step_id"] == "s1"
        assert run["transitions"][0]["notes"] == "completed"

        finished = client.post(f"{base}/runs/finish", json={"outcome": "completed"})
        assert finished.status_code == 200
        assert finished.json()["runs"][0]["outcome"] == "completed"

        runs = client.get(f"{base}/runs")
        assert runs.status_code == 200
        assert len(runs.json()) == 1


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (InputValidationError("secret detail"), 422, "validation_error"),
        (RateLimitError(), 429, "rate_limited"),
        (CostCeilingError(), 402, "cost_ceiling_reached"),
        (
            DocumentTooLargeError("secret detail", "Document is too large."),
            413,
            "document_too_large",
        ),
        (DocumentError("secret detail", "Document could not be read."), 422, "document_error"),
        (ProviderError("secret detail"), 502, "provider_error"),
        (WorkflowValidationError("secret detail"), 502, "workflow_validation_error"),
        (RuntimeError("top-secret"), 500, "internal_error"),
    ],
)
def test_typed_errors_map_to_safe_envelopes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    with _client(tmp_path) as client:

        def failing_generate(_request: Any) -> None:
            raise error

        monkeypatch.setattr(client.app.state.services.generation, "generate", failing_generate)
        response = client.post("/api/v1/workflows/generate", json=_payload())

        assert response.status_code == expected_status, response.text
        body = response.json()
        assert body["error"] == expected_code
        assert body["request_id"]
        assert "secret" not in response.text.lower()
        assert "top-secret" not in response.text.lower()


def test_request_validation_and_http_errors_use_envelopes(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        invalid = client.post("/api/v1/workflows/generate", json={"description": "Only one field"})
        assert invalid.status_code == 422
        body = invalid.json()
        assert body["error"] == "request_validation_error"
        assert any(item["field"] == "body.category" for item in body["details"])
        assert "input" not in body

        missing = client.get("/api/v1/workflows/does-not-exist")
        assert missing.status_code == 422
        assert missing.json()["error"] == "validation_error"

        unknown = client.get("/not-a-route")
        assert unknown.status_code == 404
        assert unknown.json()["error"] == "http_error"


def test_request_id_linking_and_metrics(tmp_path: Path) -> None:
    class Capture(logging.Handler):
        def __init__(self) -> None:
            super().__init__()
            self.messages: list[str] = []

        def emit(self, record: logging.LogRecord) -> None:
            self.messages.append(self.format(record))

    handler = Capture()
    handler.setFormatter(logging.Formatter("%(request_id)s"))
    handler.addFilter(RequestIdFilter())
    package_logger = logging.getLogger("workflow_ai")
    package_logger.addHandler(handler)
    try:
        with _client(tmp_path) as client:
            assert client.get("/health").status_code == 200
            response = client.post(
                "/api/v1/workflows/generate",
                json=_payload(),
                headers={"X-Request-ID": "req-contract-1"},
            )
            assert response.headers["X-Request-ID"] == "req-contract-1"
            assert response.json()["request_id"] == "req-contract-1"
            assert "req-contract-1" in handler.messages

            metrics = client.get("/api/v1/metrics")
            assert metrics.status_code == 200
            snapshot = metrics.json()
            assert snapshot["requests"]["total"] >= 2
            assert snapshot["generation"]["total"] == 1
            assert snapshot["generation"]["fallbacks"] == 0
            assert snapshot["generation"]["fallback_rate"] == 0.0
    finally:
        package_logger.removeHandler(handler)

    assert sanitize_request_id("bad\nid") == "bad-id"
    assert sanitize_request_id(None) is None


def test_generated_request_id_is_echoed(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.post("/api/v1/workflows/generate", json=_payload())
        assert len(response.headers["X-Request-ID"]) == 12
        assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_request_size_limit_is_enforced_before_routing(tmp_path: Path) -> None:
    with _client(tmp_path, max_upload_bytes=128) as client:
        response = client.post(
            "/api/v1/workflows/generate", json=_payload(additional_context="x" * 200)
        )
        assert response.status_code == 413
        assert response.json()["error"] == "request_too_large"
