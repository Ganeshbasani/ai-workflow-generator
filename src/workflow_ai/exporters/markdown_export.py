"""Markdown export derived from the structured workflow model."""

from __future__ import annotations

from ..models import Workflow
from ..validation import topological_order


def _section(title: str, items: list[str]) -> list[str]:
    if not items:
        return []
    return [f"## {title}", "", *(f"- {item}" for item in items), ""]


def to_markdown(workflow: Workflow) -> bytes:
    """Render the workflow as a portable Markdown document."""
    lines: list[str] = [
        f"# {workflow.title}",
        "",
        f"**Domain:** {workflow.domain}",
        "",
    ]
    if workflow.summary:
        lines.extend([workflow.summary, ""])

    lines.extend(["## Steps", ""])
    for number, step in enumerate(topological_order(workflow), start=1):
        lines.append(f"{number}. **{step.title}**")
        details: list[str] = [f"Type: `{step.step_type.value}`"]
        if step.owner_role:
            details.append(f"Owner: {step.owner_role}")
        if step.depends_on:
            details.append(f"Depends on: {', '.join(step.depends_on)}")
        if step.condition:
            details.append(f"Condition: {step.condition}")
        if step.on_true:
            details.append(f"On true: {step.on_true}")
        if step.on_false:
            details.append(f"On false: {step.on_false}")
        if step.estimated_duration:
            details.append(f"Duration: {step.estimated_duration}")
        if step.status.value != "pending":
            details.append(f"Status: {step.status.value}")
        lines.append(f"   - {'; '.join(details)}")
        if step.description:
            lines.append(f"   - {step.description}")
        if step.rationale:
            lines.append(f"   - Rationale: {step.rationale}")
        if step.notes:
            lines.append(f"   - Notes: {step.notes}")
    lines.append("")

    lines.extend(_section("Assumptions", workflow.assumptions))
    lines.extend(_section("Risks", workflow.risks))
    lines.extend(_section("Missing Information", workflow.missing_information))
    lines.extend(_section("Suggested Improvements", workflow.suggested_improvements))

    return "\n".join(lines).rstrip().encode("utf-8")
