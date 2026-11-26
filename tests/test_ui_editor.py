"""Pure tests for the inline editor's DataFrame/domain-model bridge."""

from __future__ import annotations

import pandas as pd
import pytest

from workflow_ai.config import get_settings
from workflow_ai.errors import InputValidationError, WorkflowValidationError
from workflow_ai.factory import build_project_stack
from workflow_ai.models import (
    GenerationResult,
    StepStatus,
    StepType,
    Workflow,
    WorkflowStep,
)
from workflow_ai.ui.editor import (
    COLUMNS,
    frame_to_workflow,
    reorder_workflow,
    save_frame,
    save_order,
    steps_to_frame,
)


def _workflow() -> Workflow:
    return Workflow(
        title="Approval",
        domain="business",
        steps=[
            WorkflowStep(
                id="s1",
                title="Submit",
                step_type=StepType.start,
                rationale="Kick things off",
            ),
            WorkflowStep(
                id="s2",
                title="Approve",
                step_type=StepType.approval,
                depends_on=["s1"],
                condition="amount > 100",
                on_true="s3",
                notes="check budget",
                status=StepStatus.in_progress,
            ),
            WorkflowStep(id="s3", title="Archive", depends_on=["s2"]),
        ],
    )


def test_steps_to_frame_projects_all_editor_columns() -> None:
    frame = steps_to_frame(_workflow())

    assert list(frame.columns) == list(COLUMNS)
    assert frame["id"].tolist() == ["s1", "s2", "s3"]
    assert frame.iloc[1]["condition"] == "amount > 100"
    assert frame.iloc[1]["notes"] == "check budget"
    assert steps_to_frame(Workflow(title="Empty", domain="x")).empty


def test_text_normalisation_handles_missing_cells() -> None:
    workflow = _workflow()
    frame = steps_to_frame(workflow)
    frame.loc[0, "condition"] = float("nan")
    frame.loc[0, "notes"] = pd.NA
    frame.loc[0, "on_true"] = None

    rebuilt = frame_to_workflow(workflow, frame)

    assert rebuilt.steps[0].condition is None
    assert rebuilt.steps[0].notes == ""
    assert rebuilt.steps[0].on_true is None


def test_frame_to_workflow_updates_fields_and_preserves_hidden_data() -> None:
    workflow = _workflow()
    frame = steps_to_frame(workflow)
    frame.loc[1, "title"] = "Review request"
    frame.loc[1, "step_type"] = "decision"
    frame.loc[1, "status"] = "done"
    frame.loc[1, "depends_on"] = "s1, s3"

    rebuilt = frame_to_workflow(workflow, frame)

    assert rebuilt.steps[1].title == "Review request"
    assert rebuilt.steps[1].step_type is StepType.decision
    assert rebuilt.steps[1].status is StepStatus.done
    assert rebuilt.steps[1].depends_on == ["s1", "s3"]
    # Fields not exposed in the table survive the round-trip.
    assert rebuilt.steps[0].rationale == "Kick things off"


def test_frame_to_workflow_rejects_invalid_edits() -> None:
    workflow = _workflow()
    frame = steps_to_frame(workflow)

    bad_id = frame.copy()
    bad_id.loc[0, "id"] = "missing"
    with pytest.raises(InputValidationError, match="no longer exists"):
        frame_to_workflow(workflow, bad_id)

    bad_type = frame.copy()
    bad_type.loc[0, "step_type"] = "unknown"
    with pytest.raises(InputValidationError, match="valid step type"):
        frame_to_workflow(workflow, bad_type)

    empty_title = frame.copy()
    empty_title.loc[0, "title"] = "   "
    with pytest.raises(InputValidationError, match="cannot be empty"):
        frame_to_workflow(workflow, empty_title)

    with pytest.raises(InputValidationError, match="keep every step"):
        frame_to_workflow(workflow, frame.iloc[:2])


def test_reorder_workflow_rebuilds_a_linear_chain() -> None:
    workflow = _workflow()

    rebuilt = reorder_workflow(workflow, ["s3", "s1", "s2"])

    assert [step.id for step in rebuilt.steps] == ["s3", "s1", "s2"]
    assert rebuilt.steps[0].depends_on == []
    assert rebuilt.steps[1].depends_on == ["s3"]
    assert rebuilt.steps[2].depends_on == ["s1"]


def test_reorder_workflow_rejects_mismatched_ids() -> None:
    with pytest.raises(InputValidationError, match="no longer match"):
        reorder_workflow(_workflow(), ["s1", "s2", "s99"])


def _saved_project() -> tuple[object, object, str]:
    projects, editor, _runs = build_project_stack(get_settings())
    saved = projects.create_from_result(
        GenerationResult(workflow=_workflow(), provider="rule"),
        owner_id="tester",
        prompt="describe",
        category="business",
    )
    return projects, editor, saved.id


def test_save_frame_persists_validated_edits() -> None:
    projects, editor, project_id = _saved_project()
    workflow = projects.load(project_id, "tester").workflow
    frame = steps_to_frame(workflow)
    frame.loc[1, "title"] = "Review request"

    saved = save_frame(editor, project_id, "tester", workflow, frame)

    assert saved.workflow.steps[1].title == "Review request"
    assert projects.load(project_id, "tester").workflow.steps[1].title == "Review request"


def test_save_order_persists_new_chain() -> None:
    projects, editor, project_id = _saved_project()
    workflow = projects.load(project_id, "tester").workflow

    saved = save_order(editor, project_id, "tester", workflow, ["s2", "s1", "s3"])

    assert [step.id for step in saved.workflow.steps] == ["s2", "s1", "s3"]
    assert saved.workflow.steps[0].depends_on == []


def test_save_frame_rejects_dangling_dependencies() -> None:
    projects, editor, project_id = _saved_project()
    workflow = projects.load(project_id, "tester").workflow
    frame = steps_to_frame(workflow)
    frame.loc[0, "depends_on"] = "s99"

    with pytest.raises(WorkflowValidationError):
        save_frame(editor, project_id, "tester", workflow, frame)
