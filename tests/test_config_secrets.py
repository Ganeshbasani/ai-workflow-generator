"""Secret-resolution and configuration tests."""

from __future__ import annotations

from workflow_ai import config
from workflow_ai.config import Settings, resolve_api_key


def test_key_from_settings() -> None:
    settings = Settings(llm_api_key="env-key")
    assert resolve_api_key(settings) == "env-key"


def test_no_key_is_valid_offline_signal() -> None:
    assert resolve_api_key(Settings()) is None


def test_streamlit_secret_takes_precedence(monkeypatch: object) -> None:
    monkeypatch.setattr(config, "_streamlit_secret", lambda name: "secret-key")  # type: ignore[attr-defined]
    settings = Settings(llm_api_key="env-key")

    assert resolve_api_key(settings) == "secret-key"


def test_broken_secret_store_falls_back_to_env(monkeypatch: object) -> None:
    def boom(name: str) -> str | None:
        raise RuntimeError("no runtime")

    monkeypatch.setattr(config, "_streamlit_secret", boom)  # type: ignore[attr-defined]
    assert resolve_api_key(Settings(llm_api_key="env-key")) == "env-key"
