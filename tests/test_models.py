"""Unit tests for the typed domain models."""

from __future__ import annotations

import json

from workflow_ai.models import GenerationRequest, GenerationResult, StepType, Workflow, WorkflowStep


def test_workflow_defaults_and_step_titles() -> None:
    workflow = Workflow(
        title="Admissions",
        domain="education",
        steps=[
            WorkflowStep(id="s1", title="Apply"),
            WorkflowStep(id="s2", title="Verify documents", step_type=StepType.approval),
        ],
    )

    assert workflow.id.startswith("wf_")
    assert workflow.step_titles() == ["Apply", "Verify documents"]
    assert workflow.steps[0].step_type is StepType.task
    assert workflow.steps[1].step_type is StepType.approval
    assert workflow.steps[0].display_text == "Apply"
    assert workflow.assumptions == []


def test_models_round_trip_through_json() -> None:
    workflow = Workflow(
        title="Order handling",
        domain="business",
        steps=[WorkflowStep(id="s1", title="Process order", depends_on=[])],
    )
    result = GenerationResult(workflow=workflow, provider="rule", degraded=True)

    decoded = GenerationResult.model_validate_json(result.model_dump_json())
    assert decoded.workflow.step_titles() == ["Process order"]
    assert decoded.provider == "rule"
    assert decoded.degraded is True


def test_request_defaults() -> None:
    request = GenerationRequest(description="do something", category="Business Organizations")

    assert request.additional_context == ""
    assert isinstance(json.loads(request.model_dump_json()), dict)
