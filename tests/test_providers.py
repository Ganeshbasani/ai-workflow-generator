"""Unit tests for the provider contract and the offline rule provider."""

from __future__ import annotations

import pytest

from workflow_ai.config import Settings
from workflow_ai.errors import InputValidationError
from workflow_ai.models import GenerationRequest, StepType, Workflow
from workflow_ai.providers import RuleProvider, WorkflowProvider


def _provider() -> RuleProvider:
    return RuleProvider(Settings())


def _generate(description: str, category: str = "Business Organizations") -> Workflow:
    return _provider().generate(GenerationRequest(description=description, category=category))


def test_rule_provider_satisfies_protocol() -> None:
    provider: WorkflowProvider = _provider()
    assert provider.name == "rule"


def test_provider_returns_structured_workflow() -> None:
    workflow = _generate("Start. Process payment. Complete the process.")

    assert isinstance(workflow, Workflow)
    assert workflow.domain == "business"
    assert [step.id for step in workflow.steps] == ["s1", "s2", "s3"]
    assert workflow.steps[1].depends_on == ["s1"]
    assert workflow.steps[0].step_type is StepType.start
    assert workflow.steps[-1].step_type is StepType.end
    assert workflow.step_titles() == ["Start", "Process payment", "Complete the process"]


def test_category_is_a_real_tie_breaker() -> None:
    text = "book an appointment and process the order"

    hospital = _generate(text, "Hospitals")
    business = _generate(text, "Business Organizations")
    assert hospital.domain == "hospital"
    assert business.domain == "business"
    assert hospital.step_titles() == business.step_titles() == [text.capitalize()]


def test_keyword_evidence_overrides_dropdown() -> None:
    workflow = _generate("Process the customer order and generate an invoice", "Hospitals")

    assert workflow.domain == "business"
    assert workflow.step_titles() == ["Process the customer order and generate an invoice"]


def test_missing_input_raises_typed_error() -> None:
    with pytest.raises(InputValidationError):
        _provider().generate(GenerationRequest(description="   ", category="Hospitals"))


def test_unrecognisable_input_returns_actionable_error() -> None:
    with pytest.raises(InputValidationError) as error:
        _generate("a")
    assert "clear action" in error.value.user_message


@pytest.mark.parametrize(
    "description",
    ["Create the workflow", "Generate an AI workflow", "Please make me a process flowchart."],
)
def test_meta_request_is_rejected_instead_of_saved_as_a_fake_step(description: str) -> None:
    with pytest.raises(InputValidationError) as error:
        _generate(description)
    assert "Describe the real process" in error.value.user_message


def test_workflow_title_does_not_repeat_workflow_suffix() -> None:
    workflow = _generate("Start the onboarding workflow. Verify the account.")

    assert workflow.title == "Start the onboarding workflow"


def test_long_trigger_sentence_creates_a_concise_action_title() -> None:
    workflow = _generate(
        "When a customer requests a refund, support reviews the order and checks eligibility. "
        "Then notify the customer."
    )

    assert workflow.title == "Support reviews the order"


def test_actions_keep_the_user_wording_instead_of_generic_domain_templates() -> None:
    workflow = _generate(
        "The support agent checks the order and eligibility, then issues the refund."
    )

    assert workflow.step_titles() == [
        "The support agent checks the order and eligibility",
        "Issues the refund",
    ]


def test_explicit_complementary_conditions_create_a_real_decision_branch() -> None:
    workflow = _generate(
        "If eligible, approve the request. If not eligible, explain the reason. "
        "Then notify the customer."
    )

    decision, yes_path, no_path, final = workflow.steps
    assert decision.step_type is StepType.decision
    assert decision.condition == "eligible"
    assert decision.on_true == yes_path.id
    assert decision.on_false == no_path.id
    assert yes_path.title == "Approve the request"
    assert no_path.title == "Explain the reason"
    assert final.title == "Notify the customer"
    assert final.depends_on == [yes_path.id, no_path.id]


def test_inline_else_creates_both_paths() -> None:
    workflow = _generate(
        "If the order is eligible, issue the refund; otherwise explain the policy."
    )

    decision, yes_path, no_path = workflow.steps
    assert decision.step_type is StepType.decision
    assert decision.on_true == yes_path.id
    assert decision.on_false == no_path.id


def test_adjacent_yes_no_actions_share_the_stated_decision_criterion() -> None:
    workflow = _generate(
        "An agent reviews the issue and decides whether it can be resolved on the first response. "
        "If yes, send the solution and close the ticket. "
        "If no, route it to the right specialist."
    )

    review, decision, yes_path, no_path = workflow.steps
    assert review.step_type is StepType.task
    assert decision.step_type is StepType.decision
    assert "resolved on the first response" in (decision.condition or "")
    assert decision.on_true == yes_path.id
    assert decision.on_false == no_path.id
    assert yes_path.title == "Send the solution and close the ticket"
    assert no_path.title == "Route it to the right specialist"


def test_context_is_bounded_by_settings() -> None:
    settings = Settings(max_context_chars=10)
    workflow = RuleProvider(settings).generate(
        GenerationRequest(
            description="Approve the plan",
            category="Hospitals",
            additional_context="extraneous tail that must be truncated",
        )
    )

    assert workflow.steps[0].title == "Approve the plan"
