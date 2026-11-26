"""CSV export derived from the structured workflow model."""

from __future__ import annotations

import csv
import io

from ..models import Workflow
from ..validation import topological_order

# Normalised column names (Phase 4, fixes the old "Step 1:" prefix inconsistency).
COLUMNS = (
    "step_id",
    "title",
    "type",
    "owner",
    "depends_on",
    "condition",
    "status",
)


def _safe_cell(value: object) -> str:
    text = "" if value is None else str(value)
    # Neutralise spreadsheet formula injection (S-09).
    return "'" + text if text and text[0] in ("=", "+", "-", "@") else text


def to_csv(workflow: Workflow) -> bytes:
    """Serialise all steps and their graph metadata to a UTF-8 BOM CSV.

    Rows follow topological order so the file reads in execution order.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    for step in topological_order(workflow):
        writer.writerow(
            [
                _safe_cell(step.id),
                _safe_cell(step.title),
                _safe_cell(step.step_type.value),
                _safe_cell(step.owner_role),
                _safe_cell("; ".join(step.depends_on)),
                _safe_cell(step.condition),
                _safe_cell(step.status.value),
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")
