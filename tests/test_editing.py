"""Workflow editor tests: every mutation re-validates before persisting."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fakes import sample_project
from workflow_ai.errors import InputValidationError, WorkflowValidationError
from workflow_ai.models import StepType
from workflow_ai.persistence import SqliteProjectRepository
from workflow_ai.services import ProjectService, WorkflowEditor


@pytest.fixture()
def editor(tmp_path: Path) -> tuple[WorkflowEditor, ProjectService, str]:
    projects = ProjectService(SqliteProjectRepository(tmp_path / "workflows.db"))
    project = sample_project("session-1")
    projects.save(project)
    return WorkflowEditor(projects), projects, project.id


def test_add_step_chains_after_last(editor: tuple[WorkflowEditor, ProjectService, str]) -> None:
    tool, projects, project_id = editor

    updated = tool.add_step(project_id, "  Notify the customer  ", "session-1")

    assert updated.workflow.step_titles()[-1] == "Notify the customer"
    assert updated.workflow.steps[-1].id == "s3"
    assert updated.workflow.steps[-1].depends_on == ["s2"]
    assert projects.load(project_id, "session-1").workflow.steps[-1].id == "s3"


def test_add_step_rejects_blank_title(editor: tuple[WorkflowEditor, ProjectService, str]) -> None:
    tool, projects, project_id = editor
    with pytest.raises(InputValidationError, match="step title"):
        tool.add_step(project_id, "   ", "session-1")
    assert len(projects.load(project_id, "session-1").workflow.steps) == 2


def test_update_step_patches_fields(editor: tuple[WorkflowEditor, ProjectService, str]) -> None:
    tool, projects, project_id = editor

    updated = tool.update_step(
        project_id,
        "s1",
        "session-1",
        title="Register the order",
        step_type=StepType.approval,
        owner_role="manager",
        estimated_duration="2 days",
    )

    step = updated.workflow.steps[0]
    assert step.title == "Register the order"
    assert step.step_type == StepType.approval
    assert step.owner_role == "manager"
    assert step.estimated_duration == "2 days"
    assert projects.load(project_id, "session-1").workflow.steps[0].title == "Register the order"


def test_update_step_rejects_empty_title(
    editor: tuple[WorkflowEditor, ProjectService, str],
) -> None:
    tool, _, project_id = editor
    with pytest.raises(InputValidationError, match="cannot be empty"):
        tool.update_step(project_id, "s1", "session-1", title="  ")


def test_delete_step_cleans_references(editor: tuple[WorkflowEditor, ProjectService, str]) -> None:
    tool, projects, project_id = editor

    updated = tool.delete_step(project_id, "s1", "session-1")

    assert [step.id for step in updated.workflow.steps] == ["s2"]
    assert updated.workflow.steps[0].depends_on == []
    assert projects.load(project_id, "session-1").workflow.steps[0].depends_on == []


def test_delete_missing_step_is_typed_error(
    editor: tuple[WorkflowEditor, ProjectService, str],
) -> None:
    tool, _, project_id = editor
    with pytest.raises(InputValidationError, match="no longer exists"):
        tool.delete_step(project_id, "s99", "session-1")


def test_move_step_reorders_and_rechains(
    editor: tuple[WorkflowEditor, ProjectService, str],
) -> None:
    tool, projects, project_id = editor
    tool.add_step(project_id, "Notify the customer", "session-1")

    moved = tool.move_step(project_id, "s3", -1, "session-1")
    assert [step.id for step in moved.workflow.steps] == ["s1", "s3", "s2"]
    assert [step.depends_on for step in moved.workflow.steps] == [[], ["s1"], ["s3"]]

    back = tool.move_step(project_id, "s3", 1, "session-1")
    assert [step.id for step in back.workflow.steps] == ["s1", "s2", "s3"]
    assert projects.load(project_id, "session-1").workflow.step_titles()[-1] == (
        "Notify the customer"
    )


def test_move_step_rejects_out_of_range(
    editor: tuple[WorkflowEditor, ProjectService, str],
) -> None:
    tool, _, project_id = editor
    with pytest.raises(InputValidationError, match="cannot be moved"):
        tool.move_step(project_id, "s1", -1, "session-1")
    with pytest.raises(InputValidationError, match="Invalid move"):
        tool.move_step(project_id, "s1", 0, "session-1")


def test_set_branch_sets_and_clears_targets(
    editor: tuple[WorkflowEditor, ProjectService, str],
) -> None:
    tool, projects, project_id = editor

    branched = tool.set_branch(
        project_id, "s1", "session-1", condition="approved?", on_true="s2", on_false=None
    )
    step = branched.workflow.steps[0]
    assert step.condition == "approved?"
    assert step.on_true == "s2"
    assert step.on_false is None

    cleared = tool.set_branch(
        project_id, "s1", "session-1", condition=None, on_true=None, on_false=None
    )
    step = cleared.workflow.steps[0]
    assert step.condition is None and step.on_true is None and step.on_false is None
    assert projects.load(project_id, "session-1").workflow.steps[0].on_true is None


def test_edit_rejects_unknown_dependency_without_persisting(
    editor: tuple[WorkflowEditor, ProjectService, str],
) -> None:
    tool, projects, project_id = editor
    with pytest.raises(WorkflowValidationError, match="unknown step"):
        tool.update_step(project_id, "s1", "session-1", depends_on=["s99"])

    assert projects.load(project_id, "session-1").workflow.steps[0].depends_on == []


def test_edit_rejects_self_dependency(
    editor: tuple[WorkflowEditor, ProjectService, str],
) -> None:
    tool, _, project_id = editor
    with pytest.raises(WorkflowValidationError, match="cannot depend on itself"):
        tool.update_step(project_id, "s1", "session-1", depends_on=["s1"])


def test_edit_rejects_unknown_branch_target(
    editor: tuple[WorkflowEditor, ProjectService, str],
) -> None:
    tool, _, project_id = editor
    with pytest.raises(WorkflowValidationError, match="on_true"):
        tool.set_branch(
            project_id, "s1", "session-1", condition="x", on_true="s99", on_false=None
        )


def test_edit_can_create_a_cycle_and_is_rejected(
    editor: tuple[WorkflowEditor, ProjectService, str],
) -> None:
    tool, _, project_id = editor
    with pytest.raises(WorkflowValidationError, match="cycle"):
        tool.update_step(project_id, "s1", "session-1", depends_on=["s2"])
