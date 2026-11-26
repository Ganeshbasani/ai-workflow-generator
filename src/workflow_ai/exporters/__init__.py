"""Pure exporters. Every function takes a :class:`Workflow` and returns bytes."""

from ..models import Workflow
from .csv_export import to_csv
from .json_export import to_json
from .markdown_export import to_markdown
from .mermaid_export import to_mermaid


def to_pdf(workflow: Workflow) -> bytes:
    """Build a complete PDF; load the optional PDF stack only when requested."""
    from .pdf_export import to_pdf as render_pdf

    return render_pdf(workflow)


def to_steps_pdf(workflow: Workflow) -> bytes:
    """Build a numbered steps PDF; load the PDF stack only when requested."""
    from .pdf_export import to_steps_pdf as render_steps_pdf

    return render_steps_pdf(workflow)


def to_flowchart_pdf(workflow: Workflow) -> bytes:
    """Build a paginated flowchart PDF; load the PDF stack only when requested."""
    from .pdf_export import to_flowchart_pdf as render_flowchart_pdf

    return render_flowchart_pdf(workflow)

__all__ = [
    "to_csv",
    "to_flowchart_pdf",
    "to_json",
    "to_markdown",
    "to_mermaid",
    "to_pdf",
    "to_steps_pdf",
]
