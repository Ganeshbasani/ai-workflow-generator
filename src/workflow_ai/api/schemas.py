"""HTTP request/response contracts for ``/api/v1``.

These schemas are a transport boundary only: they delegate every mutation to
the same validated services used by the Streamlit UI.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models import GenerationResult, Project, RunRecord, StepStatus, StepType, Workflow


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExportFormat(StrEnum):
    """Supported export formats (same exporters as the UI)."""

    json = "json"
    csv = "csv"
    pdf = "pdf"
    steps_pdf = "steps_pdf"
    flowchart_pdf = "flowchart_pdf"
    markdown = "markdown"
    mermaid = "mermaid"


class GenerateWorkflowRequest(_StrictModel):
    description: str = Field(default="", max_length=4_000)
    category: str = Field(min_length=1, max_length=100)
    additional_context: str = Field(default="", max_length=20_000)
    document_text: str = Field(default="", max_length=20_000)
    session_id: str = Field(default="anonymous", max_length=128)
    # Mirrors the Streamlit behaviour: generation also creates a saved project.
    persist: bool = True

    @model_validator(mode="after")
    def require_process_source(self) -> GenerateWorkflowRequest:
        if not self.description.strip() and not self.document_text.strip():
            raise ValueError("Add a process description or upload a document.")
        return self


class GenerateWorkflowResponse(BaseModel):
    result: GenerationResult
    project: Project | None = None
    project_id: str | None = None
    request_id: str


class ProjectListResponse(BaseModel):
    items: list[Project]


class RenameRequest(_StrictModel):
    title: str = Field(min_length=1, max_length=200)


class StepPatch(_StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4_000)
    step_type: StepType | None = None
    owner_role: str | None = Field(default=None, max_length=200)
    depends_on: list[str] | None = None
    condition: str | None = Field(default=None, max_length=500)
    on_true: str | None = Field(default=None, max_length=100)
    on_false: str | None = Field(default=None, max_length=100)
    estimated_duration: str | None = Field(default=None, max_length=100)

    def kwargs(self) -> dict[str, Any]:
        """Return only supplied fields; ``None`` means 'leave unchanged'."""
        return self.model_dump(exclude_unset=True, exclude_none=True)


class AddStepRequest(_StrictModel):
    title: str = Field(min_length=1, max_length=200)
    step_type: StepType = StepType.task
    owner_role: str | None = Field(default=None, max_length=200)


class MoveStepRequest(_StrictModel):
    direction: Literal[-1, 1]


class BranchRequest(_StrictModel):
    condition: str | None = Field(default=None, max_length=500)
    on_true: str | None = Field(default=None, max_length=100)
    on_false: str | None = Field(default=None, max_length=100)


class ReplaceWorkflowRequest(_StrictModel):
    workflow: Workflow


class StepStatusRequest(_StrictModel):
    status: StepStatus
    notes: str = Field(default="", max_length=1_000)


class FinishRunRequest(_StrictModel):
    outcome: str = Field(default="completed", max_length=50)
    notes: str = Field(default="", max_length=1_000)


class ActionResponse(BaseModel):
    ok: bool = True
    request_id: str


__all__ = [
    "ActionResponse",
    "AddStepRequest",
    "BranchRequest",
    "ExportFormat",
    "FinishRunRequest",
    "GenerateWorkflowRequest",
    "GenerateWorkflowResponse",
    "MoveStepRequest",
    "Project",
    "ProjectListResponse",
    "RenameRequest",
    "ReplaceWorkflowRequest",
    "RunRecord",
    "StepPatch",
    "StepStatusRequest",
]
