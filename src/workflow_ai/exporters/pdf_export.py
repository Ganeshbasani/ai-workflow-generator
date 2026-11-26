"""PDF export derived from the structured workflow model.

Uses bundled DejaVu fonts so accented characters and typographic punctuation
render correctly. Emoji glyphs are not available in DejaVu; they are dropped
from the PDF text rather than crashing the export. The diagram is drawn with
PDF primitives, so no image library or network access is required.
"""

from __future__ import annotations

import unicodedata
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from pypdf import PdfReader, PdfWriter

from ..models import StepStatus, Workflow
from ..validation import topological_order

# exporters/ -> workflow_ai/ -> src/ -> project root
FONT_DIR = Path(__file__).resolve().parents[3] / "fonts"

_ACCENT = (49, 92, 104)
_DARK = (15, 23, 42)
_MUTED = (100, 116, 139)
_TRUE = (52, 211, 153)
_FALSE = (248, 113, 113)


def _pdf_safe(text: str) -> str:
    """Replace characters the bundled font cannot render (notably emoji)."""
    cleaned: list[str] = []
    for char in text:
        category = unicodedata.category(char)
        if category in ("So", "Sk") and ord(char) > 0x2000:
            continue
        cleaned.append(char)
    return "".join(cleaned)


def _write(pdf: FPDF, text: str, *, size: int, bold: bool = False, height: int = 7) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("DejaVu", style="B" if bold else "", size=size)
    pdf.multi_cell(
        0,
        height,
        text=_pdf_safe(text),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )


def _bullet_list(pdf: FPDF, title: str, items: list[str]) -> None:
    if not items:
        return
    pdf.ln(3)
    _write(pdf, title, size=11, bold=True)
    for item in items:
        _write(pdf, f"- {item}", size=10)


def _new_pdf() -> FPDF:
    pdf = FPDF(format="A4")
    pdf.set_margins(16, 16, 16)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("DejaVu", style="", fname=str(FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", style="B", fname=str(FONT_DIR / "DejaVuSans-Bold.ttf"))
    pdf.set_text_color(*_DARK)
    return pdf


def _report_header(pdf: FPDF, workflow: Workflow, label: str, detail: str) -> None:
    _write(pdf, workflow.title, size=20, bold=True, height=10)
    _write(pdf, f"{label}  ·  {workflow.domain.replace('_', ' ').title()}", size=10, bold=True)
    _write(pdf, detail, size=9)
    pdf.ln(4)


def _step_names(workflow: Workflow) -> dict[str, str]:
    return {step.id: step.title for step in workflow.steps}


def to_steps_pdf(workflow: Workflow) -> bytes:
    """Render an ordered, readable process document with full step details."""
    pdf = _new_pdf()
    pdf.add_page()
    _report_header(
        pdf,
        workflow,
        "Step-by-step process",
        "Read from top to bottom. Decision steps list their outcomes explicitly.",
    )
    if workflow.summary:
        _write(pdf, workflow.summary, size=11, height=7)
        pdf.ln(3)
    ordered = topological_order(workflow)
    names = _step_names(workflow)
    if not ordered:
        _write(pdf, "No process steps were identified.", size=12)
    for number, step in enumerate(ordered, start=1):
        pdf.ln(3)
        _write(pdf, f"{number:02d}  {step.title}", size=14, bold=True, height=8)
        meta = [
            step.step_type.value.replace("_", " ").title(),
            f"Status: {step.status.value.replace('_', ' ')}",
        ]
        if step.owner_role:
            meta.append(f"Owner: {step.owner_role}")
        if step.estimated_duration:
            meta.append(f"Duration: {step.estimated_duration}")
        if step.depends_on:
            meta.append("After: " + ", ".join(names.get(item, item) for item in step.depends_on))
        _write(pdf, "  ·  ".join(meta), size=9, height=5)
        if step.description:
            _write(pdf, step.description, size=10, height=6)
        if step.rationale:
            _write(pdf, f"Evidence: {step.rationale}", size=9, height=5)
        if step.condition:
            _write(pdf, f"Condition: {step.condition}", size=9, bold=True, height=5)
        if step.on_true:
            _write(pdf, f"If yes → {names.get(step.on_true, step.on_true)}", size=9, height=5)
        if step.on_false:
            _write(pdf, f"If no → {names.get(step.on_false, step.on_false)}", size=9, height=5)
        pdf.set_draw_color(220, 228, 222)
        pdf.line(pdf.l_margin, pdf.get_y() + 2, pdf.w - pdf.r_margin, pdf.get_y() + 2)

    for title, items in (
        ("Assumptions", workflow.assumptions),
        ("Risks to review", workflow.risks),
        ("Open questions", workflow.missing_information),
        ("Suggested improvements", workflow.suggested_improvements),
    ):
        _bullet_list(pdf, title, items)

    return bytes(pdf.output())


def _arrow(pdf: FPDF, x: float, y: float, direction: str, color: tuple[int, int, int]) -> None:
    pdf.set_draw_color(*color)
    if direction == "down":
        pdf.line(x, y - 2.2, x, y)
        pdf.line(x, y, x - 1.4, y - 1.6)
        pdf.line(x, y, x + 1.4, y - 1.6)
    elif direction == "right":
        pdf.line(x - 2.2, y, x, y)
        pdf.line(x, y, x - 1.6, y - 1.4)
        pdf.line(x, y, x - 1.6, y + 1.4)
    else:
        pdf.line(x + 2.2, y, x, y)
        pdf.line(x, y, x + 1.6, y - 1.4)
        pdf.line(x, y, x + 1.6, y + 1.4)


def to_flowchart_pdf(workflow: Workflow) -> bytes:
    """Render a print-size flowchart with readable nodes and explicit branches."""
    ordered = topological_order(workflow)
    page_size = 4
    groups = [
        ordered[index : index + page_size] for index in range(0, len(ordered), page_size)
    ] or [[]]
    page_by_step_id = {
        step.id: index // page_size + 1
        for index, step in enumerate(ordered)
    }
    names = _step_names(workflow)
    by_id = {step.id: step for step in workflow.steps}
    pdf = _new_pdf()
    card_h, card_gap, card_x = 52.0, 7.0, 24.0
    card_w, card_y = pdf.w - 2 * card_x, 48.0

    for page_number, steps in enumerate(groups, start=1):
        pdf.add_page()
        _report_header(
            pdf,
            workflow,
            "Flowchart",
            f"Page {page_number} of {len(groups)} · Read top to bottom. "
            "Decision routes are labeled Yes and No.",
        )
        if not steps:
            _write(pdf, "No steps are available to diagram.", size=12)
            continue
        page_ids = {step.id for step in steps}
        page_positions = {
            step.id: (
                card_y + index * (card_h + card_gap),
                card_y + index * (card_h + card_gap) + card_h / 2,
            )
            for index, step in enumerate(steps)
        }

        # Draw connectors first so node cards remain legible above them.
        for step in steps:
            top, mid = page_positions[step.id]
            for source_id in step.depends_on:
                if source_id not in page_ids:
                    continue
                source_step = by_id.get(source_id)
                if (
                    source_step
                    and source_step.step_type.value == "decision"
                    and step.id in (source_step.on_true, source_step.on_false)
                ):
                    continue
                source_top, source_mid = page_positions[source_id]
                if abs(source_mid - mid) <= card_h + card_gap + 1:
                    pdf.set_draw_color(*_MUTED)
                    pdf.line(pdf.w / 2, source_top + card_h, pdf.w / 2, top)
                    _arrow(pdf, pdf.w / 2, top, "down", _MUTED)
                else:
                    rail = 17.0
                    pdf.set_draw_color(*_MUTED)
                    pdf.line(card_x, source_mid, rail, source_mid)
                    pdf.line(rail, source_mid, rail, mid)
                    pdf.line(rail, mid, card_x, mid)
                    _arrow(pdf, card_x, mid, "right", _MUTED)
            if step.on_true in page_ids:
                _, target_mid = page_positions[step.on_true]
                rail = pdf.w - 17.0
                pdf.set_draw_color(*_TRUE)
                pdf.line(card_x + card_w, mid - 5, rail, mid - 5)
                pdf.line(rail, mid - 5, rail, target_mid)
                pdf.line(rail, target_mid, card_x + card_w, target_mid)
                _arrow(pdf, card_x + card_w, target_mid, "left", _TRUE)
            if step.on_false in page_ids:
                _, target_mid = page_positions[step.on_false]
                rail = 17.0
                pdf.set_draw_color(*_FALSE)
                pdf.line(card_x, mid + 5, rail, mid + 5)
                pdf.line(rail, mid + 5, rail, target_mid)
                pdf.line(rail, target_mid, card_x, target_mid)
                _arrow(pdf, card_x, target_mid, "right", _FALSE)

        for local_number, step in enumerate(steps):
            top, _ = page_positions[step.id]
            number = local_number + (page_number - 1) * page_size + 1
            pdf.set_draw_color(203, 216, 207)
            pdf.set_fill_color(250, 252, 250)
            pdf.rect(card_x, top, card_w, card_h, style="DF")
            accent = _TRUE if step.status == StepStatus.done else _ACCENT
            pdf.set_fill_color(*accent)
            pdf.rect(card_x, top, 2.2, card_h, style="F")
            pdf.set_xy(card_x + 6, top + 5)
            pdf.set_font("DejaVu", style="B", size=11)
            pdf.set_text_color(*_DARK)
            pdf.multi_cell(card_w - 12, 5.5, _pdf_safe(f"{number:02d}  {step.title}"))
            pdf.set_x(card_x + 6)
            pdf.set_font("DejaVu", size=8)
            pdf.set_text_color(*_MUTED)
            step_type = step.step_type.value.replace("_", " ").title()
            status = step.status.value.replace("_", " ").title()
            detail = f"{step_type}  ·  {status}"
            if step.owner_role:
                detail += f"  ·  {step.owner_role}"
            if step.depends_on:
                dependencies = []
                for item in step.depends_on:
                    reference = names.get(item, item)
                    source_page = page_by_step_id.get(item)
                    if source_page is not None and source_page != page_number:
                        reference += f" (page {source_page})"
                    dependencies.append(reference)
                detail += "  ·  After: " + ", ".join(dependencies)
            pdf.multi_cell(card_w - 12, 4.5, _pdf_safe(detail))
            if step.condition:
                pdf.set_x(card_x + 6)
                pdf.set_text_color(*_DARK)
                pdf.set_font("DejaVu", style="B", size=8)
                pdf.multi_cell(card_w - 12, 4.5, _pdf_safe(f"Condition: {step.condition}"))
            for label, target_id, color in (
                ("YES", step.on_true, _TRUE),
                ("NO", step.on_false, _FALSE),
            ):
                if target_id:
                    destination = names.get(target_id, target_id)
                    target_page = page_by_step_id.get(target_id)
                    if target_page is not None and target_page != page_number:
                        destination += f" (page {target_page})"
                    pdf.set_x(card_x + 6)
                    pdf.set_text_color(*color)
                    pdf.set_font("DejaVu", style="B", size=8)
                    pdf.multi_cell(
                        card_w - 12, 4.5, _pdf_safe(f"{label} → {destination}")
                    )
            pdf.set_text_color(*_DARK)

    return bytes(pdf.output())


def to_pdf(workflow: Workflow) -> bytes:
    """Render a complete PDF with a readable flowchart followed by full steps."""
    writer = PdfWriter()
    for document in (to_flowchart_pdf(workflow), to_steps_pdf(workflow)):
        for page in PdfReader(BytesIO(document)).pages:
            writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
