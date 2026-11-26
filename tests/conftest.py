"""Shared test setup: make ``src/`` importable without an editable install."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

for path in (str(SRC), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from workflow_ai.config import Settings, get_settings

# A developer's real .env must never change unit-test behavior or expose a
# local API key to tests. Environment variables remain available to tests that
# explicitly set them; the implicit dotenv file is disabled for this process.
Settings.model_config["env_file"] = None


@pytest.fixture(autouse=True)
def _isolate_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Keep AppTest runs from writing a real ``workflows.db`` into the repo.

    Service tests pass explicit paths, so this only affects code paths that
    call :func:`get_settings` (notably ``app.py`` under AppTest).
    """
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app_workflows.db"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
