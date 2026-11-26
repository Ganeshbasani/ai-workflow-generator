"""FastAPI application: versioned HTTP routes over the existing services."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, File, Form, Query, Response, UploadFile, status
from fastapi.staticfiles import StaticFiles

from ..config import Settings, get_settings, is_ollama_endpoint, resolve_api_key
from ..errors import InputValidationError, WorkflowError
from ..exporters import (
    to_csv,
    to_flowchart_pdf,
    to_json,
    to_markdown,
    to_mermaid,
    to_pdf,
    to_steps_pdf,
)
from ..ingest import extract_text
from ..models import GenerationRequest, Workflow
from ..providers.ollama_api import chat_completion as ollama_chat_completion
from .dependencies import (
    ApiServices,
    get_metrics,
    get_owner_id,
    get_request_id,
    get_services,
)
from .errors import register_error_handlers
from .metrics import Metrics
from .middleware import RequestContextMiddleware
from .schemas import (
    ActionResponse,
    AddStepRequest,
    BranchRequest,
    ExportFormat,
    FinishRunRequest,
    GenerateWorkflowRequest,
    GenerateWorkflowResponse,
    MoveStepRequest,
    Project,
    ProjectListResponse,
    RenameRequest,
    ReplaceWorkflowRequest,
    RunRecord,
    StepPatch,
    StepStatusRequest,
)

_EXPORTERS: dict[ExportFormat, Callable[[Workflow], bytes | str]] = {
    ExportFormat.json: to_json,
    ExportFormat.csv: to_csv,
    ExportFormat.pdf: to_pdf,
    ExportFormat.steps_pdf: to_steps_pdf,
    ExportFormat.flowchart_pdf: to_flowchart_pdf,
    ExportFormat.markdown: to_markdown,
    ExportFormat.mermaid: to_mermaid,
}
_MEDIA_TYPES: dict[ExportFormat, str] = {
    ExportFormat.json: "application/json",
    ExportFormat.csv: "text/csv; charset=utf-8",
    ExportFormat.pdf: "application/pdf",
    ExportFormat.steps_pdf: "application/pdf",
    ExportFormat.flowchart_pdf: "application/pdf",
    ExportFormat.markdown: "text/markdown; charset=utf-8",
    ExportFormat.mermaid: "text/plain; charset=utf-8",
}
_EXTENSIONS: dict[ExportFormat, str] = {
    ExportFormat.json: "json",
    ExportFormat.csv: "csv",
    ExportFormat.pdf: "pdf",
    ExportFormat.steps_pdf: "steps.pdf",
    ExportFormat.flowchart_pdf: "flowchart.pdf",
    ExportFormat.markdown: "md",
    ExportFormat.mermaid: "mmd",
}
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9_-]+")

ServicesDep = Annotated[ApiServices, Depends(get_services)]
OwnerDep = Annotated[str | None, Depends(get_owner_id)]
RequestIdDep = Annotated[str, Depends(get_request_id)]
MetricsDep = Annotated[Metrics, Depends(get_metrics)]
ExportFormatDep = Annotated[ExportFormat, Query(alias="format")]


def _safe_filename(title: str) -> str:
    """Keep Content-Disposition headers ASCII-only and injection-free."""
    cleaned = _UNSAFE_FILENAME.sub("_", title).strip("_")[:80]
    return cleaned or "workflow"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    services: ApiServices = app.state.services
    services.close()


def _register_routes(app: FastAPI, settings: Settings) -> None:
    router = APIRouter(prefix="/api/v1")

    @router.get(
        "/ai/status",
        response_model=dict[str, Any],
        summary="Report configured AI provider without exposing credentials",
        tags=["generation"],
    )
    def ai_status() -> dict[str, Any]:
        api_key = resolve_api_key(settings)
        configured = bool(api_key or settings.llm_base_url)
        local_ollama = bool(
            settings.llm_base_url
            and ("11434" in settings.llm_base_url or "ollama" in settings.llm_base_url.lower())
        )
        provider = "Ollama" if local_ollama else "OpenAI-compatible API"
        message = (
            f"{provider} configured · {settings.llm_model}"
            if configured
            else "No AI endpoint is configured. Offline drafts are text extraction, not AI."
        )
        return {
            "configured": configured,
            "provider": provider if configured else "Not connected",
            "model": settings.llm_model,
            "message": message,
        }

    @router.post(
        "/ai/test",
        response_model=dict[str, Any],
        summary="Test the configured model endpoint and enumerate available models",
        tags=["generation"],
    )
    def test_ai_connection() -> dict[str, Any]:
        api_key = resolve_api_key(settings)
        if not api_key and not settings.llm_base_url:
            return {
                **ai_status(),
                "connected": False,
                "message": "Configure LLM_BASE_URL or LLM_API_KEY before testing the connection.",
                "available_models": [],
            }
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=api_key or "ollama",
                base_url=settings.llm_base_url or None,
                timeout=min(settings.request_timeout_seconds, 8),
                max_retries=0,
            )
            models = sorted(model.id for model in client.models.list().data)
        except Exception:
            endpoint = ai_status()["provider"]
            return {
                **ai_status(),
                "connected": False,
                "generation_ready": False,
                "message": f"The configured {endpoint} endpoint could not be reached. Check the endpoint URL and network access.",
                "available_models": [],
            }

        model_available = settings.llm_model in models
        if not model_available:
            return {
                **ai_status(),
                "connected": True,
                "generation_ready": False,
                "model_available": False,
                "available_models": models[:30],
                "message": (
                    f"Connected, but {settings.llm_model} is not available. Choose one of the "
                    "listed models and restart the app."
                ),
            }

        try:
            if is_ollama_endpoint(settings.llm_base_url):
                assert settings.llm_base_url is not None
                ollama_chat_completion(
                    base_url=settings.llm_base_url,
                    model=settings.llm_model,
                    messages=[{"role": "user", "content": "Reply with OK."}],
                    # A cold local model may need time to load before its first token.
                    # A readiness probe can cold-load a local model even when
                    # normal generation requests use a shorter timeout.
                    timeout=max(120, min(settings.request_timeout_seconds, 300)),
                    temperature=0,
                    max_tokens=32,
                    context_tokens=settings.ollama_context_tokens,
                    json_mode=True,
                )
            else:
                client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[{"role": "user", "content": "Reply with OK."}],
                    max_tokens=8,
                    temperature=0,
                )
        except Exception as exc:
            if type(exc).__name__ == "RateLimitError":
                if "no credits remaining" in str(exc).lower():
                    message = (
                        "The API key is accepted, but this OpenAI account has no API credits. "
                        "Add credits in OpenAI billing or use a provider with an active quota."
                    )
                else:
                    message = (
                        "The model endpoint is reachable, but its usage limit was reached. "
                        "Check the account quota or try again later."
                    )
            else:
                message = (
                    "The endpoint is reachable, but the model could not generate a response. "
                    "Check the key's model access and provider configuration."
                )
            return {
                **ai_status(),
                "connected": False,
                "generation_ready": False,
                "model_available": True,
                "available_models": models[:30],
                "message": message,
            }

        return {
            **ai_status(),
            "connected": True,
            "generation_ready": True,
            "model_available": model_available,
            "available_models": models[:30],
            "message": f"Connected. Model {settings.llm_model} is ready for generation.",
        }

    @router.post(
        "/workflows/generate",
        response_model=GenerateWorkflowResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Generate and optionally persist a workflow",
        description="Runs the same generation service as the UI; no business logic is duplicated.",
        tags=["generation"],
    )
    def generate_workflow(
        payload: GenerateWorkflowRequest,
        services: ServicesDep,
        owner_id: OwnerDep,
        request_id: RequestIdDep,
        metrics: MetricsDep,
    ) -> GenerateWorkflowResponse:
        domain_request = GenerationRequest(
            description=payload.description,
            category=payload.category,
            additional_context=payload.additional_context,
            document_text=payload.document_text,
            require_ai=bool(payload.document_text.strip()),
            session_id=payload.session_id,
            request_id=request_id,
        )
        try:
            result = services.generation.generate(domain_request)
        except WorkflowError:
            metrics.record_generation_error()
            raise

        metrics.record_generation(result)
        project = None
        if payload.persist:
            project = services.projects.create_from_result(
                result,
                owner_id=owner_id,
                prompt=payload.description or "Analyze uploaded process document",
                category=payload.category,
            )
        return GenerateWorkflowResponse(
            result=result,
            project=project,
            project_id=project.id if project else None,
            request_id=request_id,
        )

    @router.post(
        "/workflows/generate-upload",
        response_model=GenerateWorkflowResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Generate a workflow using uploaded PDF or TXT context",
        tags=["generation"],
    )
    def generate_workflow_upload(
        services: ServicesDep,
        owner_id: OwnerDep,
        request_id: RequestIdDep,
        metrics: MetricsDep,
        category: Annotated[str, Form(min_length=1, max_length=100)],
        description: Annotated[str, Form(max_length=4_000)] = "",
        additional_context: Annotated[str, Form(max_length=20_000)] = "",
        session_id: Annotated[str, Form(max_length=128)] = "anonymous",
        file: Annotated[UploadFile | None, File()] = None,
    ) -> GenerateWorkflowResponse:
        document_context = extract_text(file, settings) if file is not None else ""
        if file is not None and not document_context.strip():
            raise InputValidationError(
                "The uploaded document contains no extractable text.",
                user_message=(
                    "We couldn't find readable text in that document. Try a text-based PDF "
                    "or TXT file; scanned PDFs need OCR before upload."
                ),
            )
        payload = GenerateWorkflowRequest(
            description=description,
            category=category,
            additional_context=additional_context[: settings.max_context_chars],
            document_text=document_context[: settings.max_context_chars],
            session_id=session_id,
            persist=True,
        )
        return generate_workflow(payload, services, owner_id, request_id, metrics)

    @router.get(
        "/workflows",
        response_model=ProjectListResponse,
        summary="List saved workflows for the current owner",
        tags=["projects"],
    )
    def list_workflows(
        services: ServicesDep,
        owner_id: OwnerDep,
    ) -> ProjectListResponse:
        return ProjectListResponse(items=services.projects.list_projects(owner_id))

    @router.get(
        "/workflows/{project_id}",
        response_model=Project,
        summary="Load one saved workflow",
        tags=["projects"],
    )
    def get_workflow(
        project_id: str,
        services: ServicesDep,
        owner_id: OwnerDep,
    ) -> Project:
        return services.projects.load(project_id, owner_id)

    @router.patch(
        "/workflows/{project_id}",
        response_model=Project,
        summary="Rename a saved workflow",
        tags=["projects"],
    )
    def rename_workflow(
        project_id: str,
        payload: RenameRequest,
        services: ServicesDep,
        owner_id: OwnerDep,
    ) -> Project:
        return services.projects.rename(project_id, payload.title, owner_id)

    @router.put(
        "/workflows/{project_id}",
        response_model=Project,
        summary="Replace a workflow graph (re-validated)",
        tags=["editing"],
    )
    def replace_workflow(
        project_id: str,
        payload: ReplaceWorkflowRequest,
        services: ServicesDep,
        owner_id: OwnerDep,
    ) -> Project:
        return services.editor.replace_workflow(project_id, payload.workflow, owner_id)

    @router.delete(
        "/workflows/{project_id}",
        response_model=ActionResponse,
        summary="Delete a saved workflow",
        tags=["projects"],
    )
    def delete_workflow(
        project_id: str,
        services: ServicesDep,
        owner_id: OwnerDep,
        request_id: RequestIdDep,
    ) -> ActionResponse:
        if not services.projects.delete(project_id, owner_id):
            raise InputValidationError("The selected workflow no longer exists.")
        return ActionResponse(request_id=request_id)

    @router.post(
        "/workflows/{project_id}/steps",
        response_model=Project,
        status_code=status.HTTP_201_CREATED,
        summary="Append a step",
        tags=["editing"],
    )
    def add_step(
        project_id: str,
        payload: AddStepRequest,
        services: ServicesDep,
        owner_id: OwnerDep,
    ) -> Project:
        return services.editor.add_step(
            project_id,
            payload.title,
            owner_id,
            step_type=payload.step_type,
            owner_role=payload.owner_role,
        )

    @router.patch(
        "/workflows/{project_id}/steps/{step_id}",
        response_model=Project,
        summary="Patch one step (re-validated)",
        tags=["editing"],
    )
    def patch_step(
        project_id: str,
        step_id: str,
        payload: StepPatch,
        services: ServicesDep,
        owner_id: OwnerDep,
    ) -> Project:
        return services.editor.update_step(project_id, step_id, owner_id, **payload.kwargs())

    @router.delete(
        "/workflows/{project_id}/steps/{step_id}",
        response_model=Project,
        summary="Delete a step and clean its references",
        tags=["editing"],
    )
    def delete_step(
        project_id: str,
        step_id: str,
        services: ServicesDep,
        owner_id: OwnerDep,
    ) -> Project:
        return services.editor.delete_step(project_id, step_id, owner_id)

    @router.post(
        "/workflows/{project_id}/steps/{step_id}/move",
        response_model=Project,
        summary="Move a step one position",
        tags=["editing"],
    )
    def move_step(
        project_id: str,
        step_id: str,
        payload: MoveStepRequest,
        services: ServicesDep,
        owner_id: OwnerDep,
    ) -> Project:
        return services.editor.move_step(project_id, step_id, payload.direction, owner_id)

    @router.put(
        "/workflows/{project_id}/steps/{step_id}/branch",
        response_model=Project,
        summary="Set or clear a decision step's branch targets",
        tags=["editing"],
    )
    def set_branch(
        project_id: str,
        step_id: str,
        payload: BranchRequest,
        services: ServicesDep,
        owner_id: OwnerDep,
    ) -> Project:
        return services.editor.set_branch(
            project_id,
            step_id,
            owner_id,
            condition=payload.condition,
            on_true=payload.on_true,
            on_false=payload.on_false,
        )

    @router.get(
        "/workflows/{project_id}/export",
        response_class=Response,
        summary="Export a saved workflow in any supported format",
        tags=["exports"],
    )
    def export_workflow(
        project_id: str,
        services: ServicesDep,
        owner_id: OwnerDep,
        format: ExportFormatDep = ExportFormat.json,
    ) -> Response:
        project = services.projects.load(project_id, owner_id)
        content = _EXPORTERS[format](project.workflow)
        if isinstance(content, str):
            content = content.encode("utf-8")
        filename = f"{_safe_filename(project.display_title)}.{_EXTENSIONS[format]}"
        return Response(
            content=content,
            media_type=_MEDIA_TYPES[format],
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.post(
        "/workflows/{project_id}/runs",
        response_model=Project,
        status_code=status.HTTP_201_CREATED,
        summary="Start (or resume) a run",
        tags=["execution"],
    )
    def start_run(
        project_id: str,
        services: ServicesDep,
        owner_id: OwnerDep,
    ) -> Project:
        return services.runs.start_run(project_id, owner_id)

    @router.get(
        "/workflows/{project_id}/runs",
        response_model=list[RunRecord],
        summary="List run records",
        tags=["execution"],
    )
    def list_runs(
        project_id: str,
        services: ServicesDep,
        owner_id: OwnerDep,
    ) -> list[RunRecord]:
        return services.runs.list_runs(project_id, owner_id)

    @router.patch(
        "/workflows/{project_id}/runs/steps/{step_id}",
        response_model=Project,
        summary="Record a step status change",
        tags=["execution"],
    )
    def set_step_status(
        project_id: str,
        step_id: str,
        payload: StepStatusRequest,
        services: ServicesDep,
        owner_id: OwnerDep,
    ) -> Project:
        return services.runs.set_step_status(
            project_id, step_id, payload.status, owner_id, notes=payload.notes
        )

    @router.post(
        "/workflows/{project_id}/runs/finish",
        response_model=Project,
        summary="Close the open run",
        tags=["execution"],
    )
    def finish_run(
        project_id: str,
        payload: FinishRunRequest,
        services: ServicesDep,
        owner_id: OwnerDep,
    ) -> Project:
        return services.runs.finish_run(
            project_id, owner_id, outcome=payload.outcome, notes=payload.notes
        )

    @router.get(
        "/metrics",
        response_model=dict[str, Any],
        summary="Request, token, cost and fallback metrics",
        tags=["operations"],
    )
    def get_metrics_snapshot(metrics: MetricsDep) -> dict[str, Any]:
        return metrics.snapshot()

    app.include_router(router)

    @app.get(
        "/health",
        response_model=dict[str, str],
        summary="Liveness probe",
        tags=["operations"],
    )
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/ready",
        response_model=dict[str, str],
        summary="Readiness probe",
        tags=["operations"],
    )
    def ready(services: ServicesDep) -> dict[str, str]:
        return {"status": "ready", "provider": services.generation.provider_name}


def create_app(
    *,
    settings: Settings | None = None,
    services: ApiServices | None = None,
    metrics: Metrics | None = None,
) -> FastAPI:
    """Build the API application with injectable services for tests."""
    config = settings or get_settings()
    service_stack = services or ApiServices.build(config)
    metric_store = metrics or Metrics()

    app = FastAPI(
        title="AI Workflow Generator API",
        version="1.0.0",
        description=(
            "Versioned HTTP boundary over the same generation, persistence, "
            "editing, execution and export services used by the React workflow studio. "
            "Pass `X-Owner-Id` to scope projects; `X-Request-ID` is echoed on every "
            "response and attached to service logs."
        ),
        lifespan=_lifespan,
    )
    app.state.services = service_stack
    app.state.metrics = metric_store
    app.state.settings = config

    register_error_handlers(app)
    app.add_middleware(
        RequestContextMiddleware,
        max_request_bytes=config.max_upload_bytes,
        metrics=metric_store,
    )
    _register_routes(app, config)
    web_dist = Path(__file__).resolve().parents[3] / "web" / "dist"
    if web_dist.is_dir():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    return app
