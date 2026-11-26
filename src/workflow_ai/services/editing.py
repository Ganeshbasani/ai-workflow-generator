"""Workflow editor — every mutation re-validates the graph before saving."""

from __future__ import annotations

from collections.abc import Callable

from ..errors import InputValidationError
from ..models import Project, StepType, Workflow, WorkflowStep
from ..validation import validate_workflow
from .project import ProjectService


class WorkflowEditor:
    """Apply bounded, validated structural edits to a saved workflow."""

    def __init__(self, projects: ProjectService) -> None:
        self._projects = projects

    def _mutate(
        self,
        project_id: str,
        owner_id: str | None,
        change: Callable[[Workflow], Workflow],
    ) -> Project:
        project = self._projects.load(project_id, owner_id)
        updated = change(project.workflow)
        validate_workflow(updated)  # rejects dangling edges, bad branches, cycles
        return self._projects.replace_workflow(project_id, updated, owner_id)

    def replace_workflow(
        self, project_id: str, workflow: Workflow, owner_id: str | None
    ) -> Project:
        """Store a caller-supplied graph after the shared DAG validation."""
        return self._mutate(project_id, owner_id, lambda _current: workflow)

    @staticmethod
    def _find_step(workflow: Workflow, step_id: str) -> WorkflowStep:
        step = next((item for item in workflow.steps if item.id == step_id), None)
        if step is None:
            raise InputValidationError("That step no longer exists.")
        return step

    def add_step(
        self,
        project_id: str,
        title: str,
        owner_id: str | None,
        *,
        step_type: StepType = StepType.task,
        owner_role: str | None = None,
    ) -> Project:
        """Append a step to the graph, chaining it after the last step."""
        clean = title.strip()
        if not clean:
            raise InputValidationError("Please enter a step title.")

        def change(workflow: Workflow) -> Workflow:
            numbers = [
                int(step.id[1:])
                for step in workflow.steps
                if step.id.startswith("s") and step.id[1:].isdigit()
            ]
            new_id = f"s{max(numbers, default=0) + 1}"
            new_step = WorkflowStep(
                id=new_id,
                title=clean[:200],
                step_type=step_type,
                owner_role=owner_role,
                depends_on=[workflow.steps[-1].id] if workflow.steps else [],
            )
            return workflow.model_copy(update={"steps": [*workflow.steps, new_step]})

        return self._mutate(project_id, owner_id, change)

    def update_step(
        self,
        project_id: str,
        step_id: str,
        owner_id: str | None,
        *,
        title: str | None = None,
        description: str | None = None,
        step_type: StepType | None = None,
        owner_role: str | None = None,
        depends_on: list[str] | None = None,
        condition: str | None = None,
        on_true: str | None = None,
        on_false: str | None = None,
        estimated_duration: str | None = None,
    ) -> Project:
        """Patch selected fields of one step; ``None`` means 'leave unchanged'."""
        supplied = {
            key: value
            for key, value in {
                "title": title.strip() if title is not None else None,
                "description": description,
                "step_type": step_type,
                "owner_role": owner_role,
                "depends_on": depends_on,
                "condition": condition,
                "on_true": on_true,
                "on_false": on_false,
                "estimated_duration": estimated_duration,
            }.items()
            if value is not None
        }
        if "title" in supplied and not supplied["title"]:
            raise InputValidationError("A step title cannot be empty.")

        def change(workflow: Workflow) -> Workflow:
            self._find_step(workflow, step_id)
            steps = [
                step.model_copy(update=supplied) if step.id == step_id else step
                for step in workflow.steps
            ]
            return workflow.model_copy(update={"steps": steps})

        return self._mutate(project_id, owner_id, change)

    def delete_step(self, project_id: str, step_id: str, owner_id: str | None) -> Project:
        """Remove a step and clean every reference to it."""

        def change(workflow: Workflow) -> Workflow:
            self._find_step(workflow, step_id)
            kept = [
                step.model_copy(
                    update={
                        "depends_on": [
                            dep for dep in step.depends_on if dep != step_id
                        ],
                        "on_true": None if step.on_true == step_id else step.on_true,
                        "on_false": None if step.on_false == step_id else step.on_false,
                    }
                )
                for step in workflow.steps
                if step.id != step_id
            ]
            return workflow.model_copy(update={"steps": kept})

        return self._mutate(project_id, owner_id, change)

    def move_step(
        self, project_id: str, step_id: str, direction: int, owner_id: str | None
    ) -> Project:
        """Reorder a step by one position and rebuild the linear dependency chain."""
        if direction not in (-1, 1):
            raise InputValidationError("Invalid move direction.")

        def change(workflow: Workflow) -> Workflow:
            ordered = list(workflow.steps)
            index = next(
                (i for i, step in enumerate(ordered) if step.id == step_id), None
            )
            if index is None:
                raise InputValidationError("That step no longer exists.")
            target = index + direction
            if target < 0 or target >= len(ordered):
                raise InputValidationError("The step cannot be moved further.")
            ordered[index], ordered[target] = ordered[target], ordered[index]
            rebuilt = [
                step.model_copy(
                    update={"depends_on": [ordered[i - 1].id] if i else []}
                )
                for i, step in enumerate(ordered)
            ]
            return workflow.model_copy(update={"steps": rebuilt})

        return self._mutate(project_id, owner_id, change)

    def set_branch(
        self,
        project_id: str,
        step_id: str,
        owner_id: str | None,
        *,
        condition: str | None,
        on_true: str | None,
        on_false: str | None,
    ) -> Project:
        """Set or clear a decision step's branch targets (``None`` clears)."""
        updates = {"condition": condition, "on_true": on_true, "on_false": on_false}

        def change(workflow: Workflow) -> Workflow:
            self._find_step(workflow, step_id)
            steps = [
                step.model_copy(update=updates) if step.id == step_id else step
                for step in workflow.steps
            ]
            return workflow.model_copy(update={"steps": steps})

        return self._mutate(project_id, owner_id, change)
