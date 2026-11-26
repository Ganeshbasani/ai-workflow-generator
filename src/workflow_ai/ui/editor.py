"""Pure helpers that bridge the inline editor table to validated services.

The DataFrame is only a view. Every save rebuilds typed ``WorkflowStep`` objects
from the original graph and hands the result to ``WorkflowEditor``, which runs
the shared DAG validation before persisting.
"""

from __future__ import annotations

import math

import pandas as pd

from ..errors import InputValidationError
from ..models import Project, StepStatus, StepType, Workflow, WorkflowStep
from ..services.editing import WorkflowEditor

COLUMNS = (
    "id",
    "title",
    "step_type",
    "depends_on",
    "condition",
    "on_true",
    "on_false",
    "status",
    "notes",
)


def _text(value: object) -> str:
    """Normalise a DataFrame cell (including NaN / pd.NA) to plain text."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    result = str(value).strip()
    return "" if result.lower() in {"nan", "none", "<na>"} else result


def steps_to_frame(workflow: Workflow) -> pd.DataFrame:
    """Project workflow steps into an editable table."""
    rows = [
        {
            "id": step.id,
            "title": step.title,
            "step_type": step.step_type.value,
            "depends_on": ", ".join(step.depends_on),
            "condition": step.condition or "",
            "on_true": step.on_true or "",
            "on_false": step.on_false or "",
            "status": step.status.value,
            "notes": step.notes,
        }
        for step in workflow.steps
    ]
    if not rows:
        return pd.DataFrame(columns=list(COLUMNS))
    return pd.DataFrame(rows, columns=list(COLUMNS))


def _optional(value: object) -> str | None:
    return _text(value) or None


def frame_to_workflow(workflow: Workflow, frame: pd.DataFrame) -> Workflow:
    """Rebuild a workflow from edited rows, preserving unexposed step fields."""
    by_id = {step.id: step for step in workflow.steps}
    rebuilt: list[WorkflowStep] = []
    for row in frame.to_dict(orient="records"):
        step_id = _text(row.get("id"))
        original = by_id.get(step_id)
        if original is None:
            raise InputValidationError("An edited step no longer exists. Reload and try again.")
        try:
            step_type = StepType(_text(row.get("step_type")) or original.step_type.value)
            status = StepStatus(_text(row.get("status")) or original.status.value)
        except ValueError as exc:
            raise InputValidationError("Choose a valid step type and status.") from exc
        title = _text(row.get("title"))
        if not title:
            raise InputValidationError("A step title cannot be empty.")
        depends_on = [
            item.strip()
            for item in _text(row.get("depends_on")).split(",")
            if item.strip()
        ]
        rebuilt.append(
            original.model_copy(
                update={
                    "title": title[:200],
                    "step_type": step_type,
                    "depends_on": depends_on,
                    "condition": _optional(row.get("condition")),
                    "on_true": _optional(row.get("on_true")),
                    "on_false": _optional(row.get("on_false")),
                    "status": status,
                    "notes": _text(row.get("notes"))[:1_000],
                }
            )
        )
    if len(rebuilt) != len(workflow.steps):
        raise InputValidationError("The editor must keep every step. Use delete instead.")
    return workflow.model_copy(update={"steps": rebuilt})


def reorder_workflow(workflow: Workflow, order: list[str]) -> Workflow:
    """Reorder steps by id and rebuild the linear dependency chain."""
    if sorted(order) != sorted(step.id for step in workflow.steps):
        raise InputValidationError("The reordered steps no longer match the workflow.")
    by_id = {step.id: step for step in workflow.steps}
    ordered = [by_id[step_id] for step_id in order]
    rebuilt = [
        step.model_copy(update={"depends_on": [ordered[i - 1].id] if i else []})
        for i, step in enumerate(ordered)
    ]
    return workflow.model_copy(update={"steps": rebuilt})


def save_frame(
    editor: WorkflowEditor,
    project_id: str,
    owner_id: str | None,
    workflow: Workflow,
    frame: pd.DataFrame,
) -> Project:
    """Validate and persist an inline-editor table."""
    return editor.replace_workflow(
        project_id, frame_to_workflow(workflow, frame), owner_id
    )


def save_order(
    editor: WorkflowEditor,
    project_id: str,
    owner_id: str | None,
    workflow: Workflow,
    order: list[str],
) -> Project:
    """Validate and persist a drag-and-drop ordering."""
    return editor.replace_workflow(
        project_id, reorder_workflow(workflow, order), owner_id
    )


__all__ = [
    "COLUMNS",
    "frame_to_workflow",
    "reorder_workflow",
    "save_frame",
    "save_order",
    "steps_to_frame",
]
