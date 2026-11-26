"""JSON export — a lossless representation of the workflow model."""

from __future__ import annotations

from ..models import Workflow


def to_json(workflow: Workflow) -> bytes:
    """Serialise the workflow to pretty-printed UTF-8 JSON bytes."""
    return workflow.model_dump_json(indent=2, exclude_none=True).encode("utf-8")
