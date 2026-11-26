"""Phase 4 UI integration tests: diagram, five exports and explanations.

Uses Streamlit's native AppTest harness against the real ``app.py``. The
``_isolate_database`` fixture keeps all persistence in a temporary SQLite file.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from streamlit.testing.v1 import AppTest

warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message=".*bare mode.*")

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"
DESCRIPTION = (
    "Customer registers. Places order. Makes payment. "
    "Approve request and archive the record."
)


def _generated_app() -> AppTest:
    """Load the app, generate a workflow and return the resulting AppTest."""
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    at.text_area[0].set_value(DESCRIPTION)
    at.run()
    at.get_by_key("generate_workflow").click().run()
    assert not at.error
    assert not at.exception
    assert at.subheader
    return at


def test_empty_state_shown_before_generation() -> None:
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()

    assert any("Generate a workflow above" in item.value for item in at.caption)
    assert not at.get("iframe")
    assert not at.get("download_button")


def test_diagram_component_renders() -> None:
    at = _generated_app()

    assert len(at.get("iframe")) == 1


def test_all_five_exports_are_present() -> None:
    at = _generated_app()
    labels = [button.label for button in at.get("download_button")]

    assert len(labels) == 5
    assert any("CSV" in label for label in labels)
    assert any("PDF" in label for label in labels)
    assert any("JSON" in label for label in labels)
    assert any("Markdown" in label for label in labels)
    assert any("Mermaid" in label for label in labels)


def test_explanations_are_surfaced() -> None:
    at = _generated_app()
    assert any("Why this workflow" in item.label for item in at.expander)

    markdown = "\n".join(item.value for item in at.markdown)
    assert "Assumptions" in markdown
    assert "Risks" in markdown
    assert "Suggested improvements" in markdown
    assert "Step rationale" in markdown


def test_explanations_escape_model_text() -> None:
    at = _generated_app()
    markdown = "\n".join(item.value for item in at.markdown)

    # No raw script tag from user input may reach the injected explanation HTML.
    assert "<script>" not in markdown
