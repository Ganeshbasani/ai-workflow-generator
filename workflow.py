"""Backwards-compatible facade over the Phase 1 rule provider.

Historically this module contained the entire generator and returned
``list[str]``. Phase 1 moved the engine to
``workflow_ai.providers.RuleProvider`` and made :class:`~workflow_ai.models.Workflow`
the single source of truth. This shim preserves the old call signature for any
external consumers while delegating all logic to the layered package.

Prefer importing from ``workflow_ai`` directly in new code::

    from workflow_ai.models import GenerationRequest
    from workflow_ai.providers import RuleProvider
    from workflow_ai.services import GenerationService
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from workflow_ai.config import get_settings
from workflow_ai.errors import InputValidationError as WorkflowInputError
from workflow_ai.models import GenerationRequest, Workflow
from workflow_ai.providers import RuleProvider

MAX_DESCRIPTION_CHARS = get_settings().max_input_chars
MAX_CONTEXT_CHARS = get_settings().max_context_chars

CATEGORY_TO_DOMAIN = {
    "educational institutes": "education",
    "business organizations": "business",
    "real estate": "real_estate",
    "software industries": "software",
    "software projects": "software",
    "hospitals": "hospital",
}

__all__ = [
    "CATEGORY_TO_DOMAIN",
    "MAX_CONTEXT_CHARS",
    "MAX_DESCRIPTION_CHARS",
    "GenerationRequest",
    "Workflow",
    "WorkflowInputError",
    "generate_structured_workflow",
    "generate_workflow",
]


def generate_structured_workflow(
    description: str,
    category: str | None = None,
    additional_context: str = "",
) -> Workflow:
    """Legacy signature returning the new structured :class:`Workflow`."""
    settings = get_settings()
    request = GenerationRequest(
        description=description,
        category=category or "",
        additional_context=additional_context,
    )
    return RuleProvider(settings).generate(request)


def generate_workflow(
    description: str,
    category: str | None = None,
    additional_context: str = "",
) -> list[str]:
    """Generate ordered step titles (legacy ``list[str]`` API)."""
    return generate_structured_workflow(description, category, additional_context).step_titles()
