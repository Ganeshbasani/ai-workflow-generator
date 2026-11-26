"""Execution tracking — per-step status, notes and per-workflow run history."""

from __future__ import annotations

from datetime import UTC, datetime

from ..errors import InputValidationError
from ..models import Project, RunRecord, StepStatus, StepTransition
from .project import ProjectService

_OPEN = "in_progress"


class RunService:
    """Record execution progress on saved workflows."""

    def __init__(self, projects: ProjectService) -> None:
        self._projects = projects

    @staticmethod
    def _active_run(project: Project) -> RunRecord:
        run = next(
            (item for item in project.runs if item.outcome == _OPEN), None
        )
        if run is None:
            run = RunRecord(project_id=project.id)
            project.runs.append(run)
        return run

    def start_run(self, project_id: str, owner_id: str | None) -> Project:
        """Ensure an open run exists on the project."""
        project = self._projects.load(project_id, owner_id)
        self._active_run(project)
        return self._projects.save(project)

    def set_step_status(
        self,
        project_id: str,
        step_id: str,
        status: StepStatus,
        owner_id: str | None,
        *,
        notes: str = "",
    ) -> Project:
        """Update one step and append an immutable transition to the open run."""
        project = self._projects.load(project_id, owner_id)
        step = next(
            (item for item in project.workflow.steps if item.id == step_id), None
        )
        if step is None:
            raise InputValidationError("That step no longer exists.")

        step.status = status
        step.notes = notes[:1_000]
        run = self._active_run(project)
        run.transitions.append(
            StepTransition(step_id=step_id, status=status, notes=notes[:1_000])
        )
        return self._projects.save(project)

    def finish_run(
        self,
        project_id: str,
        owner_id: str | None,
        *,
        outcome: str = "completed",
        notes: str = "",
    ) -> Project:
        """Close the open run with a final outcome."""
        project = self._projects.load(project_id, owner_id)
        run = self._active_run(project)
        run.outcome = outcome[:50] or "completed"
        run.finished_at = datetime.now(UTC)
        run.notes = notes[:1_000]
        return self._projects.save(project)

    def list_runs(self, project_id: str, owner_id: str | None) -> list[RunRecord]:
        """Return a project's runs, most recently started first."""
        project = self._projects.load(project_id, owner_id)
        return sorted(project.runs, key=lambda run: run.started_at, reverse=True)
