"""Phase 3 UI integration tests: history, editor and execution tracking.

These use Streamlit's native AppTest harness against the real ``app.py``. The
``_isolate_database`` fixture in ``conftest.py`` points the app at a temporary
SQLite file, so no test writes a real ``workflows.db`` into the repository.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

from streamlit.testing.v1 import AppTest

warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message=".*bare mode.*")

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"
DESCRIPTION = "Customer registers. Places order. Makes payment. Generate invoice."


def _generated_app() -> AppTest:
    """Load the app, generate a workflow and return the resulting AppTest."""
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    at.selectbox[0].set_value("Business Organizations")
    at.text_area[0].set_value(DESCRIPTION)
    at.run()
    at.get_by_key("generate_workflow").click().run()
    assert not at.error
    assert at.subheader
    return at


def _step_cards(at: AppTest) -> list[str]:
    """Return the visible text of rendered step cards, in display order.

    The leading ``1.``/``2.`` counter is removed so reorder assertions compare
    titles rather than positions. Any status chip is intentionally retained.
    """
    cards: list[str] = []
    for item in at.markdown:
        if item.value.startswith('<div class="step-container">'):
            text = re.sub(
                r'^<div class="step-container"><span[^>]*>\d+\.</span>',
                "",
                item.value,
            )
            cards.append(text.replace("</div>", ""))
    return cards


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def test_generation_creates_a_saved_history_entry() -> None:
    at = _generated_app()

    picker = at.get_by_key("saved_project_picker")
    assert len(picker.options) == 1
    assert "Business Organizations Workflow" in picker.options[0]
    for key in ("load_project", "rename_project", "delete_project"):
        assert at.get_by_key(key) is not None
    assert not any("No saved workflows yet" in c.value for c in at.caption)


def test_history_rename_updates_the_picker_label() -> None:
    at = _generated_app()
    at.get_by_key("rename_project_input").set_value("Client onboarding")
    at.get_by_key("rename_project").click().run()

    assert not at.error
    picker_options = at.get_by_key("saved_project_picker").options
    assert any("Client onboarding" in option for option in picker_options)


def test_history_load_restores_results_after_session_reset() -> None:
    at = _generated_app()
    at.session_state["result"] = None
    at.session_state["active_project_id"] = None
    at.run()
    assert not at.subheader

    at.get_by_key("load_project").click().run()

    assert at.subheader[0].value == "📋 Business Organizations Workflow"
    assert len(at.get("download_button")) == 5
    assert len(_step_cards(at)) == 4


def test_history_delete_removes_the_entry_and_results() -> None:
    at = _generated_app()
    at.get_by_key("delete_project").click().run()

    assert not at.error
    assert not at.subheader
    assert not _step_cards(at)
    assert any("No saved workflows yet" in c.value for c in at.caption)


def test_history_survives_an_app_restart() -> None:
    """A fresh session with the same URL scope sees the persisted workflow."""
    first = _generated_app()
    scope = first.session_state["session_id"]
    assert scope

    restarted = AppTest.from_file(APP_PATH, default_timeout=30)
    restarted.query_params["sid"] = scope
    restarted.run()

    assert len(restarted.get_by_key("saved_project_picker").options) == 1
    restarted.get_by_key("load_project").click().run()
    assert restarted.subheader[0].value == "📋 Business Organizations Workflow"


# ---------------------------------------------------------------------------
# Editor
# ---------------------------------------------------------------------------


def test_editor_add_step() -> None:
    at = _generated_app()
    before = len(_step_cards(at))

    at.get_by_key("new_step_title").set_value("Archive the record")
    at.get_by_key("add_step").click().run()

    assert not at.error
    cards = _step_cards(at)
    assert len(cards) == before + 1
    assert "Archive the record" in cards[-1]


def test_editor_update_step_title() -> None:
    at = _generated_app()
    at.get_by_key("edit_title_s1").set_value("Onboard the customer")
    at.get_by_key("edit_save_s1").click().run()

    assert not at.error
    assert "Onboard the customer" in _step_cards(at)[0]


def test_editor_move_step_reorders_the_cards() -> None:
    at = _generated_app()
    before = _step_cards(at)
    assert len(before) >= 2

    at.get_by_key("edit_down_s1").click().run()

    assert not at.error
    after = _step_cards(at)
    assert after[0] == before[1]
    assert after[1] == before[0]


def test_editor_delete_step() -> None:
    at = _generated_app()
    before = len(_step_cards(at))

    at.get_by_key("edit_delete_s1").click().run()

    assert not at.error
    assert len(_step_cards(at)) == before - 1


def test_editor_branch_fields_are_saved() -> None:
    at = _generated_app()
    at.get_by_key("edit_condition_s1").set_value("approved?")
    at.get_by_key("edit_on_true_s1").set_value("s2")
    at.get_by_key("edit_on_false_s1").set_value("s3")
    at.get_by_key("edit_graph_s1").click().run()

    assert not at.error
    assert not at.exception
    # Reopening the app (same scope) proves the branch survived a round-trip.
    scope = at.session_state["session_id"]
    reopened = AppTest.from_file(APP_PATH, default_timeout=30)
    reopened.query_params["sid"] = scope
    reopened.run()
    reopened.get_by_key("load_project").click().run()
    assert reopened.get_by_key("edit_on_true_s1").value == "s2"
    assert reopened.get_by_key("edit_on_false_s1").value == "s3"


def test_editor_rejects_invalid_dependency_without_corrupting_the_graph() -> None:
    at = _generated_app()
    before = len(_step_cards(at))

    at.get_by_key("edit_deps_s1").set_value("s99")
    at.get_by_key("edit_graph_s1").click().run()

    assert any("unknown step" in error.value for error in at.error)
    assert not at.exception
    assert len(_step_cards(at)) == before


# ---------------------------------------------------------------------------
# Execution tracking
# ---------------------------------------------------------------------------


def test_execution_status_transition_and_run_history() -> None:
    at = _generated_app()
    at.get_by_key("status_s1").set_value("done")
    at.get_by_key("notes_s1").set_value("verified by QA")
    at.get_by_key("status_update_s1").click().run()

    assert not at.error
    captions = [item.value for item in at.caption]
    assert any("Run history (1)" in text for text in captions)
    assert any("1 transition(s)" in text for text in captions)
    assert "done" in _step_cards(at)[0]

    at.get_by_key("finish_run").click().run()

    assert not at.error
    assert any("completed" in item.value for item in at.caption)


def test_execution_status_survives_a_restart() -> None:
    at = _generated_app()
    at.get_by_key("status_s1").set_value("blocked")
    at.get_by_key("notes_s1").set_value("waiting on approval")
    at.get_by_key("status_update_s1").click().run()

    scope = at.session_state["session_id"]
    reopened = AppTest.from_file(APP_PATH, default_timeout=30)
    reopened.query_params["sid"] = scope
    reopened.run()
    reopened.get_by_key("load_project").click().run()

    assert reopened.get_by_key("status_s1").value == "blocked"
    assert reopened.get_by_key("notes_s1").value == "waiting on approval"
    assert "blocked" in _step_cards(reopened)[0]
