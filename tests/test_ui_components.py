"""Tests for the CCv2 interaction wrappers and their inline JavaScript.

AppTest mounts components without executing JavaScript, so the syntax checks
below close a real gap: a malformed ``export default`` module looks fine in the
test suite but renders an error in the browser.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from workflow_ai.ui import components

_MODULES = {
    "step_list": components._STEP_JS,
    "command_palette": components._COMMAND_JS,
}


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for JS syntax checks")
@pytest.mark.parametrize("name", sorted(_MODULES))
def test_inline_javascript_parses(name: str) -> None:
    source = _MODULES[name]

    with TemporaryDirectory() as tmp:
        module = Path(tmp) / f"{name}.mjs"
        module.write_text(source, encoding="utf-8")
        result = subprocess.run(
            ["node", "--check", str(module)],
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("name", sorted(_MODULES))
def test_inline_javascript_uses_v2_api_and_safe_text(name: str) -> None:
    source = _MODULES[name]

    assert "export default function" in source
    assert "setTriggerValue" in source
    assert "Streamlit.setComponentValue" not in source
    assert "innerHTML" not in source
    assert "textContent" in source


def test_wrappers_pass_data_and_callbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, object]] = []

    def fake_mount(**kwargs: object) -> str:
        captured.append(kwargs)
        return "result"

    monkeypatch.setattr(components, "_STEP_LIST", fake_mount)
    monkeypatch.setattr(components, "_COMMAND_PALETTE", fake_mount)

    step_result = components.step_list(
        [{"id": "s1", "title": "Start", "step_type": "start"}],
        tokens={"accent": "#4F46E5"},
        key="steps",
    )
    command_result = components.command_palette(
        [{"id": "workflow", "label": "Go to Workflow", "hint": "View result"}],
        tokens={"accent": "#4F46E5"},
        key="commands",
    )

    assert step_result == "result"
    assert command_result == "result"
    assert captured[0]["key"] == "steps"
    assert captured[0]["data"] == {
        "steps": [{"id": "s1", "title": "Start", "step_type": "start"}],
        "tokens": {"accent": "#4F46E5"},
    }
    assert captured[1]["key"] == "commands"
    assert captured[1]["on_command_change"] is not None
