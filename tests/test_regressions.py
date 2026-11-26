"""Phase 0 regression tests, migrated to the Phase 1 structured model.

Each test still encodes a defect found in the original audit
(see AUDIT_REPORT.md); only the API used to assert it has changed.
"""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message=".*bare mode.*")

import pytest

import app
from workflow import WorkflowInputError, generate_structured_workflow, generate_workflow
from workflow_ai.config import Settings
from workflow_ai.errors import DocumentError
from workflow_ai.exporters import to_csv, to_json, to_markdown, to_pdf
from workflow_ai.ingest import extract_text
from workflow_ai.models import Workflow, WorkflowStep


def _workflow(*titles: str) -> Workflow:
    return Workflow(
        title="Test Workflow",
        domain="general",
        steps=[WorkflowStep(id=f"s{i}", title=t) for i, t in enumerate(titles, start=1)],
    )


# --- C-01: category selects a domain without rewriting user actions -------
def test_category_selects_domain_without_rewriting_or_dropping_actions() -> None:
    text = "book an appointment and process the order"
    business = generate_workflow(text, category="Business Organizations")
    hospital = generate_workflow(text, category="Hospitals")

    # The offline draft applies sentence case while preserving the complete
    # action text regardless of the selected domain.
    assert business == [text.capitalize()]
    assert hospital == [text.capitalize()]
    structured_business = generate_structured_workflow(text, "Business Organizations")
    structured_hospital = generate_structured_workflow(text, "Hospitals")
    assert structured_business.domain == "business"
    assert structured_hospital.domain == "hospital"


# --- C-02: injected UI labels must never leak into output -----------------
def test_ui_labels_never_appear_in_output() -> None:
    steps = generate_workflow("Approve the plan", category="Hospitals")

    assert steps == ["Approve the plan"]
    assert not any("category" in step.lower() for step in steps)
    assert not any("hospital" in step.lower() for step in steps)


# --- C-03: PDF export must handle Unicode ---------------------------------
def test_pdf_export_handles_unicode() -> None:
    workflow = _workflow(
        "Approve — the “review” phase ✅",
        "Notify the équipe → 日本語",
    )
    data = to_pdf(workflow)

    assert isinstance(data, bytes)
    assert data.startswith(b"%PDF-")
    assert len(data) > 500


# --- C-04: no substring false positives -----------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "render the page",  # "end" inside "render"
        "extend the subscription",  # "end" inside "extend"
        "send the parcel",  # "end" inside "send"
        "review the listing",  # "view" inside "review"
    ],
)
def test_no_substring_false_positive(text: str) -> None:
    steps = generate_workflow(text)

    assert "Complete workflow process" not in steps
    assert "Schedule property viewing" not in steps


# --- C-05: a single domain must win ---------------------------------------
def test_single_domain_isolation() -> None:
    steps = generate_workflow(
        "Register the customer. Schedule a patient appointment.",
        category="Hospitals",
    )

    assert "Register the customer" in steps
    assert "Schedule a patient appointment" in steps


# --- C-06: output order must follow input order ---------------------------
def test_output_order_matches_input_order() -> None:
    steps = generate_workflow(
        "Start the process. Process payment. Generate invoice.",
        category="Business Organizations",
    )

    assert steps == ["Start the process", "Process payment", "Generate invoice"]


# --- C-07: errors are not steps -------------------------------------------
def test_errors_are_not_rendered_as_steps() -> None:
    with pytest.raises(WorkflowInputError):
        generate_workflow("")
    with pytest.raises(WorkflowInputError):
        generate_workflow("   ")

    # A malformed brief should be corrected, never silently saved as empty.
    with pytest.raises(WorkflowInputError) as error:
        generate_workflow("a")
    assert "clear action" in error.value.user_message


# --- C-08: legitimate repetition must survive -----------------------------
def test_repeated_steps_not_collapsed() -> None:
    steps = generate_workflow("Process payment. " * 20, category="Business Organizations")

    assert len(steps) == 20
    assert set(steps) == {"Process payment"}


# --- S-01: user text must be HTML-escaped ---------------------------------
def test_user_text_is_html_escaped() -> None:
    step = WorkflowStep(id="s1", title='<img src=x onerror="alert(1)"> approval')
    rendered = app.step_html(step, 1)

    # The tag delimiters are escaped, so the payload cannot form an element.
    assert "<img" not in rendered
    assert "&lt;img" in rendered
    assert "&gt;" in rendered
    assert "&quot;" in rendered
    assert "awg-card" in rendered  # design/card markup preserved


# --- C-11: exports must be mutually consistent ----------------------------
def test_exports_are_consistent() -> None:
    workflow = _workflow("Process order request", "Generate tax invoice")

    csv_data = to_csv(workflow).decode("utf-8-sig")
    json_data = to_json(workflow).decode("utf-8")
    md_data = to_markdown(workflow).decode("utf-8")

    assert csv_data.startswith("step_id,title,type,owner,depends_on,condition,status")
    assert "Step 1:" not in csv_data
    assert "Process order request" in csv_data
    assert "Generate tax invoice" in json_data
    assert "Process order request" in md_data
    assert "Step 1:" not in md_data


# --- S-02: fake PDFs must be rejected -------------------------------------
class FakeUpload:
    name = "fake.pdf"
    type = "application/pdf"

    @staticmethod
    def getvalue() -> bytes:
        return b"this is definitely not a pdf"


def test_fake_pdf_is_rejected() -> None:
    with pytest.raises(DocumentError):
        extract_text(FakeUpload(), Settings())


def test_app_maps_document_error_to_safe_message() -> None:
    assert app.uploaded_context(FakeUpload()) == ""


# --- C-14: fallback must preserve original casing -------------------------
def test_fallback_preserves_casing() -> None:
    assert generate_workflow("AI Workflow Approval") == ["AI Workflow Approval"]


# --- Limits ---------------------------------------------------------------
def test_oversized_description_is_rejected() -> None:
    with pytest.raises(WorkflowInputError):
        generate_workflow("x" * 4_001, category="Hospitals")


# --- Phase 1 exit criterion: no legacy step-prefix strings in the model ---
def test_no_legacy_step_prefix_strings() -> None:
    assert all("Step 1:" not in title for title in generate_workflow("Start. Process payment."))
