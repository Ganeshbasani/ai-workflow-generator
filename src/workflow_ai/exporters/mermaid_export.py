"""Mermaid flowchart export derived from the workflow graph."""

from __future__ import annotations

from ..models import StepType, Workflow
from ..validation import topological_order


def _id(step_id: str) -> str:
    """Mermaid node ids must be alphanumeric; keep generated ids stable."""
    return "".join(char if char.isalnum() else "_" for char in step_id)


def _label(text: str) -> str:
    """Escape characters that would break a Mermaid node label."""
    return (
        text.replace("\\", " ")
        .replace('"', "'")
        .replace("[", "(")
        .replace("]", ")")
        .replace("\n", " ")
        .strip()
    )


def to_mermaid(workflow: Workflow) -> str:
    """Render the workflow as ``flowchart TD`` source.

    Decision steps use diamond nodes and emit ``-- true -->`` / ``-- false -->``
    edges so branches are legible in the diagram, not just in the data model.
    Nodes are emitted in topological order for a predictable left-to-right flow.
    """
    ordered = topological_order(workflow)
    lines = ["flowchart TD"]
    for step in ordered:
        node_id = _id(step.id)
        label = _label(step.title)
        if step.step_type == StepType.decision:
            lines.append(f'    {node_id}{{"{label}"}}')
        else:
            lines.append(f'    {node_id}["{label}"]')
    for step in ordered:
        node_id = _id(step.id)
        branch_targets = (
            {step.on_true, step.on_false} if step.step_type == StepType.decision else set()
        )
        for dependency in step.depends_on:
            if dependency in branch_targets:
                continue
            lines.append(f"    {_id(dependency)} --> {node_id}")
        if step.step_type == StepType.decision:
            if step.on_true:
                lines.append(f"    {node_id} -- true --> {_id(step.on_true)}")
            if step.on_false:
                lines.append(f"    {node_id} -- false --> {_id(step.on_false)}")
    return "\n".join(lines)
