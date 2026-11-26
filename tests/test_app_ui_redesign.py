"""AppTest coverage for the redesigned tabbed UI."""

from __future__ import annotations

import warnings
from pathlib import Path

from streamlit.testing.v1 import AppTest

warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message=".*bare mode.*")

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"
DESCRIPTION = "Customer registers. Places order. Makes payment. Generate invoice."


def _loaded_app() -> AppTest:
    return AppTest.from_file(APP_PATH, default_timeout=30).run()


def _generated_app() -> AppTest:
    at = _loaded_app()
    at.text_area[0].set_value(DESCRIPTION)
    at.run()
    at.button[0].click().run()
    assert not at.error
    assert not at.exception
    return at


def test_six_focused_tabs_render() -> None:
    at = _loaded_app()

    assert [tab.label for tab in at.get("tabs")] == [
        "Generate",
        "Workflow",
        "Editor",
        "Library",
        "Run",
        "Analytics",
    ]


def test_preferences_persist_via_segmented_controls() -> None:
    at = _loaded_app()
    assert len(at.get("segmented_control")) == 2

    at.get("segmented_control")[0].set_value("Dark")
    at.get("segmented_control")[1].set_value("Compact")
    at.run()

    stylesheet = at.get("html")[0].value
    assert 'data-awg-theme="Dark"' in stylesheet
    assert 'data-awg-density="Compact"' in stylesheet
    assert "gap: 0.35rem" in stylesheet
    assert not at.error


def test_in_app_toggles_do_not_add_widgets_to_the_base_layout() -> None:
    at = _loaded_app()

    # The theme/density toggles are segmented controls, not selectboxes, so the
    # legacy category selectbox stays at index zero.
    assert len(at.selectbox) == 1
    assert len(at.text_area) == 1
    assert len(at.button) == 1


def test_generation_fires_a_toast() -> None:
    at = _generated_app()

    assert any(toast.value == "Workflow generated and saved" for toast in at.toast)


def test_inline_editor_and_drag_drop_component_are_mounted() -> None:
    at = _generated_app()

    editor_tab = at.get("tabs")[2]
    assert len(editor_tab.data_editor) == 1
    assert len(editor_tab.get("bidi_component")) == 1

    components = [str(component.proto) for component in at.get("bidi_component")]
    assert any("ai_workflow_generator.step_list" in markup for markup in components)
    assert any("ai_workflow_generator.command_palette" in markup for markup in components)


def test_save_table_button_persists_without_errors() -> None:
    at = _generated_app()

    save_button = next(
        button for button in at.get("tabs")[2].button if button.label == "💾 Save table"
    )
    save_button.click().run()

    assert not at.error
    assert not at.exception
    assert any(toast.value == "Workflow updated" for toast in at.toast)


def test_analytics_dashboard_renders_metrics_and_charts() -> None:
    at = _loaded_app()
    assert len(at.metric) == 8  # empty state still shows all KPI cards

    at = _generated_app()
    values = [metric.value for metric in at.metric]

    assert values[0] == "1"  # workflows
    assert values[1] == "4"  # steps
    assert len(at.get("vega_lite_chart")) >= 3
    assert len(at.get("dataframe")) >= 2
    assert not at.error


def test_domain_change_produces_a_domain_labelled_title() -> None:
    at = _loaded_app()
    at.selectbox[0].set_value("Hospitals")
    at.text_area[0].set_value("book an appointment and process the order")
    at.run()
    at.button[0].click().run()

    assert at.subheader[0].value == "📋 Hospitals Workflow"


def test_empty_state_captions_are_shown_in_each_workspace() -> None:
    at = _loaded_app()
    captions = " ".join(caption.value for caption in at.caption)

    assert "Generate a workflow above" in captions
    assert "Generate or load a workflow to enable editing" in captions
    assert "No saved workflows yet" in captions
    assert "Generate or load a workflow to track execution" in captions
