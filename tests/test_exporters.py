"""Unit tests for the pure exporters."""

from __future__ import annotations

import csv
import io
import json
from io import BytesIO

from pypdf import PdfReader

from workflow_ai.exporters import to_csv, to_flowchart_pdf, to_json, to_markdown, to_mermaid, to_pdf
from workflow_ai.models import Workflow, WorkflowStep


def _workflow() -> Workflow:
    return Workflow(
        title="Order Workflow",
        domain="business",
        summary="Handle a customer order.",
        steps=[
            WorkflowStep(id="s1", title="Process order", owner_role="clerk"),
            WorkflowStep(
                id="s2",
                title="=malicious formula",
                step_type="decision",
                depends_on=["s1"],
                condition="payment failed",
                on_true="s3",
                on_false="s4",
            ),
            WorkflowStep(id="s3", title="Retry payment", depends_on=["s2"]),
            WorkflowStep(id="s4", title="Cancel order", depends_on=["s2"]),
        ],
        assumptions=["Assumes stock is available"],
        risks=["Gateway timeout"],
        missing_information=["No delivery SLA"],
        suggested_improvements=["Add a delivery SLA"],
    )


def test_csv_neutralises_formula_injection() -> None:
    rows = to_csv(_workflow()).decode("utf-8-sig").splitlines()

    assert rows[0] == "step_id,title,type,owner,depends_on,condition,status"
    assert "'=malicious formula" in rows[2]
    assert "Step 1:" not in rows[1]


def test_csv_uses_topological_order() -> None:
    reader = csv.DictReader(io.StringIO(to_csv(_workflow()).decode("utf-8-sig")))
    rows = list(reader)

    assert [row["step_id"] for row in rows] == ["s1", "s2", "s3", "s4"]
    assert rows[1]["condition"] == "payment failed"
    assert rows[1]["status"] == "pending"


def test_json_is_lossless() -> None:
    payload = json.loads(to_json(_workflow()))

    assert payload["title"] == "Order Workflow"
    assert payload["steps"][1]["depends_on"] == ["s1"]
    assert payload["steps"][1]["condition"] == "payment failed"
    assert payload["suggested_improvements"] == ["Add a delivery SLA"]


def test_json_round_trips_through_model() -> None:
    original = _workflow()
    restored = Workflow.model_validate(json.loads(to_json(original)))

    assert restored.title == original.title
    assert [step.id for step in restored.steps] == [step.id for step in original.steps]
    assert restored.steps[1].on_true == "s3"
    assert restored.suggested_improvements == original.suggested_improvements


def test_markdown_contains_metadata() -> None:
    text = to_markdown(_workflow()).decode("utf-8")

    assert "# Order Workflow" in text
    assert "**Domain:** business" in text
    assert "1. **Process order**" in text
    assert "Depends on: s1" in text
    assert "On true: s3" in text
    assert "On false: s4" in text
    assert "## Risks" in text
    assert "## Suggested Improvements" in text


def test_markdown_uses_topological_order() -> None:
    text = to_markdown(_workflow()).decode("utf-8")

    assert text.index("**Process order**") < text.index("**=malicious formula**")
    assert text.index("**Retry payment**") < text.index("**Cancel order**")


def test_mermaid_emits_nodes_and_edges() -> None:
    text = to_mermaid(_workflow())

    assert text.startswith("flowchart TD")
    assert 's1["Process order"]' in text
    assert "s1 --> s2" in text


def test_mermaid_decision_diamond_and_branches() -> None:
    text = to_mermaid(_workflow())

    assert 's2{"=malicious formula"}' in text
    assert "s2 -- true --> s3" in text
    assert "s2 -- false --> s4" in text


def test_mermaid_escapes_problematic_labels() -> None:
    workflow = Workflow(
        title="Test",
        domain="general",
        steps=[WorkflowStep(id="s1", title='Say "yes" [now]')],
    )
    text = to_mermaid(workflow)

    label_line = text.split("\n")[1]
    assert "'yes'" in label_line
    assert "(now)" in label_line
    assert label_line.count('"') == 2  # only the two label delimiters remain


def test_pdf_contains_report_structure() -> None:
    data = to_pdf(_workflow())

    assert data.startswith(b"%PDF-")
    assert len(data) > 1_000


def test_flowchart_pdf_marks_branch_continuations_across_pages() -> None:
    workflow = Workflow(
        title="Refund review",
        domain="business",
        steps=[
            WorkflowStep(id="s1", title="Receive request"),
            WorkflowStep(
                id="s2",
                title="Review refund",
                step_type="decision",
                depends_on=["s1"],
                condition="Eligible?",
                on_true="s5",
                on_false="s3",
            ),
            WorkflowStep(id="s3", title="Explain rejection", depends_on=["s2"]),
            WorkflowStep(id="s4", title="Record review"),
            WorkflowStep(id="s5", title="Issue refund", depends_on=["s2"]),
        ],
    )

    pages = PdfReader(BytesIO(to_flowchart_pdf(workflow))).pages

    assert len(pages) == 2
    assert "YES → Issue refund (page 2)" in pages[0].extract_text()
    assert "After: Review refund (page 1)" in pages[1].extract_text()


def test_exports_are_mutually_consistent() -> None:
    """All five exports describe the same graph and branch semantics."""
    workflow = _workflow()
    titles = [step.title for step in workflow.steps]

    json_text = to_json(workflow).decode("utf-8")
    md_text = to_markdown(workflow).decode("utf-8")
    mermaid_text = to_mermaid(workflow)
    csv_text = to_csv(workflow).decode("utf-8-sig")

    for title in titles:
        assert title in json_text
        assert title in md_text
        assert title in mermaid_text
        assert title in csv_text

    assert '"on_true": "s3"' in json_text
    assert '"on_false": "s4"' in json_text
    assert "On true: s3" in md_text
    assert "On false: s4" in md_text
    assert "s2 -- true --> s3" in mermaid_text
    assert "s2 -- false --> s4" in mermaid_text
    assert "payment failed" in csv_text

    # PDF is binary but must still be produced from the same workflow.
    assert to_pdf(workflow).startswith(b"%PDF-")


def test_exporters_handle_full_unicode() -> None:
    """Emoji, em-dashes, CJK and RTL text survive every export without crashing."""
    workflow = Workflow(
        title="订单处理 ✅ — الموافقة",
        domain="general",
        summary="Handle café orders — 订单 — طلب",
        steps=[
            WorkflowStep(
                id="s1",
                title="Review ✅ — 审核 — مراجعة",
                description="Emoji 🎉, em dash —, CJK 中文, RTL العربية",
                rationale="Raison d'être — 理由 — السبب",
            ),
        ],
        assumptions=["Emoji 🚀 and — dash"],
        risks=["CJK 风险 and RTL خطر"],
        missing_information=["Missing ✅ 情報"],
        suggested_improvements=["Improve — 改善 — تحسين"],
    )

    # JSON / Markdown / Mermaid must be valid UTF-8 and preserve the text.
    json_text = to_json(workflow).decode("utf-8")
    md_text = to_markdown(workflow).decode("utf-8")
    mermaid_text = to_mermaid(workflow)

    assert "订单处理" in json_text
    assert "الموافقة" in json_text
    assert "订单处理" in md_text
    assert "الموافقة" in md_text
    assert "审核" in mermaid_text

    # CSV must round-trip the same Unicode content.
    csv_rows = list(csv.reader(io.StringIO(to_csv(workflow).decode("utf-8-sig"))))
    assert "订单处理" not in csv_rows[0][0]  # header is column names
    assert "审核" in csv_rows[1][1]

    # PDF must not crash on any of these characters.
    pdf_data = to_pdf(workflow)
    assert pdf_data.startswith(b"%PDF-")
