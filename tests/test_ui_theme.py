"""Pure tests for the light/dark theme tokens and runtime stylesheet."""

from __future__ import annotations

import pytest
import streamlit as st

from workflow_ai.ui.theme import (
    APPEARANCES,
    DARK,
    DENSITIES,
    LIGHT,
    PALETTES,
    get_palette,
    inject_theme,
    theme_css,
)


def test_palettes_cover_every_appearance() -> None:
    assert set(PALETTES) == set(APPEARANCES)
    assert DARK.background != LIGHT.background
    assert DARK.text != LIGHT.text
    for palette in PALETTES.values():
        assert palette.accent.startswith("#")
        assert palette.radius.endswith("px")


def test_unknown_appearance_falls_back_to_light() -> None:
    assert get_palette("not-a-theme") is LIGHT
    assert get_palette("Light") is LIGHT
    assert get_palette("Dark") is DARK


def test_stylesheet_contains_theme_tokens_and_no_user_text() -> None:
    for appearance in APPEARANCES:
        css = theme_css(appearance, "Comfortable")
        assert f'data-awg-theme="{appearance}"' in css
        assert 'data-awg-density="Comfortable"' in css
        assert get_palette(appearance).accent in css
        assert "--awg-accent" in css
        assert "prefers-reduced-motion" in css
        assert "<script" not in css


def test_compact_density_changes_spacing_rules() -> None:
    compact = theme_css("Dark", "Compact")
    comfortable = theme_css("Dark", "Comfortable")

    assert 'data-awg-density="Compact"' in compact
    assert "gap: 0.35rem" in compact
    assert "gap: 0.35rem" not in comfortable
    assert set(DENSITIES) == {"Comfortable", "Compact"}


def test_inject_theme_renders_one_stylesheet(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(st, "html", lambda markup: captured.append(markup))

    inject_theme("Dark", "Compact")

    assert len(captured) == 1
    assert 'data-awg-theme="Dark"' in captured[0]
