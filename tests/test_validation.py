"""Unit tests for workflow graph validation."""

from __future__ import annotations

import pytest

from workflow_ai.errors import WorkflowValidationError
from workflow_ai.models import Workflow, WorkflowStep
from workflow_ai.validation import (
    topological_order,
    validate_generated_workflow,
    validate_workflow,
)


def _workflow(*steps: WorkflowStep) -> Workflow:
    return Workflow(title="Test", domain="general", steps=list(steps))


def test_empty_workflow_is_structurally_valid() -> None:
    validate_workflow(_workflow())
    assert topological_order(_workflow()) == []


def test_duplicate_ids_are_rejected() -> None:
    workflow = _workflow(
        WorkflowStep(id="s1", title="A"),
        WorkflowStep(id="s1", title="B"),
    )
    with pytest.raises(WorkflowValidationError, match="unique"):
        validate_workflow(workflow)


def test_dangling_dependency_is_rejected() -> None:
    workflow = _workflow(WorkflowStep(id="s1", title="A", depends_on=["missing"]))
    with pytest.raises(WorkflowValidationError, match="unknown step"):
        validate_workflow(workflow)


def test_self_dependency_is_rejected() -> None:
    workflow = _workflow(WorkflowStep(id="s1", title="A", depends_on=["s1"]))
    with pytest.raises(WorkflowValidationError, match="cannot depend on itself"):
        validate_workflow(workflow)


def test_cycle_is_rejected() -> None:
    workflow = _workflow(
        WorkflowStep(id="s1", title="A", depends_on=["s2"]),
        WorkflowStep(id="s2", title="B", depends_on=["s1"]),
    )
    with pytest.raises(WorkflowValidationError, match="cycle"):
        validate_workflow(workflow)


def test_topological_order_respects_dependencies() -> None:
    workflow = _workflow(
        WorkflowStep(id="s3", title="C", depends_on=["s1", "s2"]),
        WorkflowStep(id="s1", title="A"),
        WorkflowStep(id="s2", title="B", depends_on=["s1"]),
    )

    assert [step.id for step in topological_order(workflow)] == ["s1", "s2", "s3"]


def test_unknown_branch_target_is_rejected() -> None:
    workflow = _workflow(
        WorkflowStep(id="s1", title="A", on_true="s2", on_false="missing"),
        WorkflowStep(id="s2", title="B"),
    )
    with pytest.raises(WorkflowValidationError, match="on_false"):
        validate_workflow(workflow)


def test_valid_branch_targets_are_accepted() -> None:
    workflow = _workflow(
        WorkflowStep(id="s1", title="A", condition="ok?", on_true="s2", on_false="s3"),
        WorkflowStep(id="s2", title="B"),
        WorkflowStep(id="s3", title="C"),
    )
    validate_workflow(workflow)
    assert [step.id for step in topological_order(workflow)] == ["s1", "s2", "s3"]


def test_generated_workflow_requires_decisions_separate_from_actions() -> None:
    workflow = _workflow(
        WorkflowStep(id="s1", title="Check ticket", on_true="s2", on_false="s3"),
        WorkflowStep(id="s2", title="Link ticket"),
        WorkflowStep(id="s3", title="Assign ticket"),
    )
    with pytest.raises(WorkflowValidationError, match="separate decision step"):
        validate_generated_workflow(workflow)


def test_generated_decision_requires_condition_and_both_outcomes() -> None:
    workflow = _workflow(
        WorkflowStep(
            id="s1",
            title="Is ticket a duplicate?",
            step_type="decision",
            condition="Ticket matches an existing request",
            on_true="s2",
        ),
        WorkflowStep(id="s2", title="Link ticket"),
    )
    with pytest.raises(WorkflowValidationError, match="both yes and no"):
        validate_generated_workflow(workflow)
