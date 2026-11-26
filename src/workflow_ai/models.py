"""Typed domain models — the single source of truth for every consumer."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class StepType(StrEnum):
    """Semantic kind of a workflow step."""

    start = "start"
    task = "task"
    decision = "decision"
    approval = "approval"
    notification = "notification"
    end = "end"


class StepStatus(StrEnum):
    """Execution state of a workflow step."""

    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    blocked = "blocked"
    skipped = "skipped"


class WorkflowStep(BaseModel):
    """A single node in the workflow graph."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    step_type: StepType = StepType.task
    owner_role: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    condition: str | None = None
    on_true: str | None = None
    on_false: str | None = None
    estimated_duration: str | None = None
    system_hint: str | None = None
    # Execution state (Phase 3). Defaults keep generated graphs unchanged.
    status: StepStatus = StepStatus.pending
    notes: str = ""
    # Why this step exists (Phase 4). Optional so old payloads stay valid.
    rationale: str | None = None

    @property
    def display_text(self) -> str:
        """Short human-readable line used by the card-based UI."""
        return self.title


class Workflow(BaseModel):
    """A complete, validated workflow graph."""

    id: str = Field(default_factory=lambda: f"wf_{uuid4().hex[:12]}")
    title: str
    domain: str
    summary: str = ""
    steps: list[WorkflowStep] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    suggested_improvements: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def step_titles(self) -> list[str]:
        """Convenience view for legacy consumers during the migration."""
        return [step.title for step in self.steps]


class GenerationRequest(BaseModel):
    """Provider-agnostic generation input."""

    description: str
    category: str
    additional_context: str = ""
    document_text: str = ""
    require_ai: bool = False
    session_id: str = "anonymous"
    # Correlation id supplied by an HTTP boundary; service logs reuse it.
    request_id: str | None = None


class GenerationResult(BaseModel):
    """Generation outcome, including provenance and degradation metadata."""

    workflow: Workflow
    provider: str
    requested_provider: str | None = None
    model: str | None = None
    degraded: bool = False
    fallback_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    attempts: int = 1
    tokens_in: int = 0
    tokens_out: int = 0
    estimated_cost_usd: float = 0.0


class GenerationMetadata(BaseModel):
    """Provenance captured at generation time (never logged verbatim)."""

    category: str
    prompt: str
    provider: str
    requested_provider: str | None = None
    model: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: float = 0.0
    attempts: int = 1
    degraded: bool = False
    fallback_reason: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_result(
        cls, result: GenerationResult, *, category: str, prompt: str
    ) -> GenerationMetadata:
        """Build provenance from a generation result and its original input."""
        return cls(
            category=category,
            prompt=prompt,
            provider=result.provider,
            requested_provider=result.requested_provider,
            model=result.model,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            estimated_cost_usd=result.estimated_cost_usd,
            latency_ms=result.latency_ms,
            attempts=result.attempts,
            degraded=result.degraded,
            fallback_reason=result.fallback_reason,
        )


class StepTransition(BaseModel):
    """One recorded execution-state change for a step."""

    step_id: str
    status: StepStatus
    notes: str = ""
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunRecord(BaseModel):
    """A single execution run of a saved workflow."""

    id: str = Field(default_factory=lambda: f"run_{uuid4().hex[:12]}")
    project_id: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    outcome: str = "in_progress"
    transitions: list[StepTransition] = Field(default_factory=list)
    notes: str = ""


class Project(BaseModel):
    """A durable workflow plus its provenance, runs and session ownership."""

    id: str = Field(default_factory=lambda: f"prj_{uuid4().hex[:12]}")
    owner_id: str | None = None
    workflow: Workflow
    title: str = ""
    metadata: GenerationMetadata | None = None
    runs: list[RunRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def display_title(self) -> str:
        """Renameable display title, falling back to the generated title."""
        return self.title or self.workflow.title

    def touch(self) -> None:
        """Mark the project as modified."""
        self.updated_at = datetime.now(UTC)
