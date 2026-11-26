"""Streamlit UI integration tests using the native AppTest harness."""

from __future__ import annotations

import warnings
from pathlib import Path

from streamlit.testing.v1 import AppTest

warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message=".*bare mode.*")

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


def _loaded_app() -> AppTest:
    return AppTest.from_file(APP_PATH, default_timeout=30).run()


def test_app_starts_without_errors() -> None:
    at = _loaded_app()
    assert not at.error
    assert not at.exception
    assert len(at.selectbox) == 1
    assert len(at.text_area) == 1
    button_keys = {button.key for button in at.button}
    assert "generate_workflow" in button_keys
    assert {"starter_0", "starter_1", "starter_2"} <= button_keys


def test_generate_happy_path() -> None:
    at = _loaded_app()
    at.selectbox[0].set_value("Business Organizations")
    at.text_area[0].set_value(
        "Customer registers. Places order. Makes payment. Generate invoice."
    )
    at.run()
    at.get_by_key("generate_workflow").click().run()

    assert not at.error
    assert not at.warning
    assert at.subheader[0].value == "Customer registers"
    assert len(at.get("download_button")) == 5


def test_typing_survives_category_change() -> None:
    """Regression: the category-dependent placeholder used to reset the field."""
    at = _loaded_app()
    at.text_area[0].set_value("Customer registers. Places order.")
    at.selectbox[0].set_value("Hospitals")
    at.run()

    assert at.text_area[0].value == "Customer registers. Places order."


def test_empty_input_shows_warning_not_error() -> None:
    at = _loaded_app()
    at.get_by_key("generate_workflow").click().run()

    assert [w.value for w in at.warning] == [
        "Please provide a description or upload a file."
    ]
    assert not at.error


def test_results_header_remembers_generation_category() -> None:
    at = _loaded_app()
    at.selectbox[0].set_value("Hospitals")
    at.text_area[0].set_value("book an appointment and process the order")
    at.run()
    at.get_by_key("generate_workflow").click().run()

    at.selectbox[0].set_value("Real Estate")
    at.run()

    assert at.subheader[0].value == "Book an appointment"


def test_unicode_input_does_not_crash_exports() -> None:
    at = _loaded_app()
    at.text_area[0].set_value("Approve — the review phase")
    at.run()
    at.get_by_key("generate_workflow").click().run()

    assert not at.error
    assert not at.exception
    assert len(at.get("download_button")) == 5
