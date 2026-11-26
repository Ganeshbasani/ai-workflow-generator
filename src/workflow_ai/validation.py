"""Structural integrity checks for workflow graphs."""

from __future__ import annotations

from .errors import WorkflowValidationError
from .models import Workflow, WorkflowStep


def validate_workflow(workflow: Workflow) -> None:
    """Reject graphs with duplicate ids, dangling edges, or cycles.

    Raises:
        WorkflowValidationError: if the graph is structurally invalid.
    """
    # An empty workflow is a legitimate "nothing detected" outcome. There is
    # simply nothing to check; callers decide whether to present it.
    ids = [step.id for step in workflow.steps]
    if len(ids) != len(set(ids)):
        raise WorkflowValidationError("Step IDs must be unique.")

    id_set = set(ids)
    for step in workflow.steps:
        for dependency in step.depends_on:
            if dependency == step.id:
                raise WorkflowValidationError(f"Step '{step.id}' cannot depend on itself.")
            if dependency not in id_set:
                raise WorkflowValidationError(
                    f"Step '{step.id}' depends on unknown step '{dependency}'."
                )
        for field_name in ("on_true", "on_false"):
            target = getattr(step, field_name)
            if target is not None and target not in id_set:
                raise WorkflowValidationError(
                    f"Step '{step.id}' has {field_name} pointing to unknown step '{target}'."
                )
            if target == step.id:
                raise WorkflowValidationError(f"Step '{step.id}' cannot branch to itself.")

    topological_order(workflow)  # raises on cycles


def validate_generated_workflow(workflow: Workflow) -> None:
    """Validate a new AI/rule draft's branch semantics, not just its references.

    Legacy saved workflows remain loadable through ``validate_workflow`` so
    teams can repair older drafts. New generated graphs must keep decisions
    separate from the actions taken on either path.
    """
    validate_workflow(workflow)
    for step in workflow.steps:
        has_branch = step.on_true is not None or step.on_false is not None
        has_condition = bool(step.condition and step.condition.strip())
        if step.step_type != "decision" and (has_branch or has_condition):
            raise WorkflowValidationError(
                f"Step '{step.id}' is an action but contains decision logic. "
                "Create a separate decision step for its condition and branch targets."
            )
        if step.step_type == "decision":
            if not has_condition:
                raise WorkflowValidationError(
                    f"Decision step '{step.id}' needs a clear condition."
                )
            if step.on_true is None or step.on_false is None:
                raise WorkflowValidationError(
                    f"Decision step '{step.id}' needs both yes and no branch targets."
                )


def topological_order(workflow: Workflow) -> list[WorkflowStep]:
    """Return steps in graph order, including decision branch edges."""
    by_id = {step.id: step for step in workflow.steps}
    parents = {step.id: set(step.depends_on) for step in workflow.steps}
    dependents: dict[str, list[str]] = {step_id: [] for step_id in by_id}

    for step in workflow.steps:
        for target in (step.on_true, step.on_false):
            if target is not None:
                parents[target].add(step.id)

    for step_id, dependencies in parents.items():
        for dependency in dependencies:
            dependents[dependency].append(step_id)

    indegree = {step_id: len(dependencies) for step_id, dependencies in parents.items()}
    ready = [step.id for step in workflow.steps if indegree[step.id] == 0]
    ordered: list[WorkflowStep] = []

    while ready:
        step_id = ready.pop(0)
        ordered.append(by_id[step_id])
        for dependent in dependents[step_id]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)

    if len(ordered) != len(workflow.steps):
        raise WorkflowValidationError("Workflow contains a dependency cycle.")

    return ordered
