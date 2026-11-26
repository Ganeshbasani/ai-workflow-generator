"""Execution tracking tests: statuses, notes and durable run history."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fakes import sample_project
from workflow_ai.errors import InputValidationError
from workflow_ai.models import StepStatus
from workflow_ai.persistence import SqliteProjectRepository
from workflow_ai.services import ProjectService, RunService


@pytest.fixture()
def services(tmp_path: Path) -> tuple[RunService, ProjectService, str]:
    projects = ProjectService(SqliteProjectRepository(tmp_path / "workflows.db"))
    project = sample_project("session-1")
    projects.save(project)
    return RunService(projects), projects, project.id


def test_status_change_updates_step_and_records_transition(
    services: tuple[RunService, ProjectService, str],
) -> None:
    runs, projects, project_id = services

    updated = runs.set_step_status(
        project_id, "s1", StepStatus.done, "session-1", notes="approved by finance"
    )

    step = updated.workflow.steps[0]
    assert step.status == StepStatus.done
    assert step.notes == "approved by finance"
    assert len(updated.runs) == 1
    assert updated.runs[0].outcome == "in_progress"
    assert updated.runs[0].transitions[0].step_id == "s1"
    assert updated.runs[0].transitions[0].status == StepStatus.done
    assert projects.load(project_id, "session-1").workflow.steps[0].status == StepStatus.done


def test_multiple_changes_use_one_open_run(
    services: tuple[RunService, ProjectService, str],
) -> None:
    runs, _, project_id = services
    runs.set_step_status(project_id, "s1", StepStatus.in_progress, "session-1")
    runs.set_step_status(project_id, "s1", StepStatus.done, "session-1")
    runs.set_step_status(project_id, "s2", StepStatus.blocked, "session-1", notes="waiting")

    final = runs.finish_run(project_id, "session-1", notes="partial")
    assert len(final.runs) == 1
    assert len(final.runs[0].transitions) == 3
    assert final.runs[0].outcome == "completed"
    assert final.runs[0].finished_at is not None
    assert final.runs[0].notes == "partial"


def test_finished_run_is_reopened_on_next_change(
    services: tuple[RunService, ProjectService, str],
) -> None:
    runs, _, project_id = services
    runs.set_step_status(project_id, "s1", StepStatus.done, "session-1")
    runs.finish_run(project_id, "session-1", outcome="aborted")

    updated = runs.set_step_status(project_id, "s2", StepStatus.done, "session-1")
    assert len(updated.runs) == 2
    assert updated.runs[0].outcome == "aborted"
    assert updated.runs[1].outcome == "in_progress"


def test_start_run_creates_an_open_run(
    services: tuple[RunService, ProjectService, str],
) -> None:
    runs, _, project_id = services
    updated = runs.start_run(project_id, "session-1")
    assert len(updated.runs) == 1
    assert runs.start_run(project_id, "session-1").runs == updated.runs


def test_list_runs_is_newest_first(
    services: tuple[RunService, ProjectService, str],
) -> None:
    runs, _, project_id = services
    runs.set_step_status(project_id, "s1", StepStatus.done, "session-1")
    runs.finish_run(project_id, "session-1")
    runs.set_step_status(project_id, "s2", StepStatus.done, "session-1")
    runs.finish_run(project_id, "session-1", outcome="aborted")

    history = runs.list_runs(project_id, "session-1")
    assert len(history) == 2
    assert history[0].started_at >= history[1].started_at


def test_unknown_step_is_typed_error(
    services: tuple[RunService, ProjectService, str],
) -> None:
    runs, projects, project_id = services
    with pytest.raises(InputValidationError, match="no longer exists"):
        runs.set_step_status(project_id, "s99", StepStatus.done, "session-1")
    assert projects.load(project_id, "session-1").runs == []


def test_notes_are_bounded(services: tuple[RunService, ProjectService, str]) -> None:
    runs, projects, project_id = services
    runs.set_step_status(
        project_id, "s1", StepStatus.done, "session-1", notes="x" * 5_000
    )
    loaded = projects.load(project_id, "session-1")
    assert len(loaded.workflow.steps[0].notes) == 1_000
    assert len(loaded.runs[0].transitions[0].notes) == 1_000


def test_owner_cannot_see_another_sessions_runs(
    services: tuple[RunService, ProjectService, str],
) -> None:
    runs, _, project_id = services
    runs.set_step_status(project_id, "s1", StepStatus.done, "session-1")
    with pytest.raises(InputValidationError):
        runs.list_runs(project_id, "session-2")
