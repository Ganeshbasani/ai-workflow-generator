"""Fresh light/dark theme tokens and runtime styling for the Streamlit UI.

Appearance is persisted through ``st.segmented_control(bind="query-params")``
in ``app.py``. The configured dual theme in ``.streamlit/config.toml`` supplies
the native tokens; this module applies the same palette to the app chrome so
the in-app toggle changes every visible surface immediately.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

APPEARANCES = ("Light", "Dark")
DENSITIES = ("Comfortable", "Compact")


@dataclass(frozen=True)
class Palette:
    """A complete, accessible colour and shape token set."""

    background: str
    surface: str
    surface_alt: str
    text: str
    muted: str
    border: str
    accent: str
    accent_soft: str
    success: str
    warning: str
    danger: str
    radius: str


LIGHT = Palette(
    background="#F6F7FB",
    surface="#FFFFFF",
    surface_alt="#EDEFF7",
    text="#171A2B",
    muted="#5C6478",
    border="#D9DDEA",
    accent="#4F46E5",
    accent_soft="#E7E5FF",
    success="#0E9F6E",
    warning="#B45309",
    danger="#C4323F",
    radius="12px",
)

DARK = Palette(
    background="#0B1020",
    surface="#151C31",
    surface_alt="#1E2740",
    text="#EAEEFA",
    muted="#A3ADC5",
    border="#2C3752",
    accent="#8B7DFF",
    accent_soft="#26224A",
    success="#3DD68C",
    warning="#F5B544",
    danger="#FF7183",
    radius="12px",
)

PALETTES: dict[str, Palette] = {"Light": LIGHT, "Dark": DARK}


def get_palette(appearance: str) -> Palette:
    """Return a known palette, falling back to light for unexpected values."""
    return PALETTES.get(appearance, LIGHT)


def theme_css(appearance: str, density: str) -> str:
    """Build scoped CSS for the selected appearance and density.

    Only static module constants are interpolated, so no user or model text can
    reach the stylesheet. The rules deliberately override native surfaces with
    ``!important`` because the in-app toggle must work without a server
    restart, while ``config.toml`` keeps charts and dataframes on-theme.
    """
    tokens = get_palette(appearance)
    compact = density == "Compact"
    spacing = """
      .stApp [data-testid="stVerticalBlock"] { gap: 0.35rem !important; }
      .stApp .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
      .stApp [data-testid="stMarkdownContainer"] p { margin-bottom: 0.25rem !important; }
    """ if compact else ""
    focus_ring = (
        f"box-shadow: 0 0 0 3px {tokens.accent_soft} !important;"
    )
    return f"""<style data-awg-theme="{appearance}" data-awg-density="{density}">
:root {{
  --awg-bg: {tokens.background};
  --awg-surface: {tokens.surface};
  --awg-surface-alt: {tokens.surface_alt};
  --awg-text: {tokens.text};
  --awg-muted: {tokens.muted};
  --awg-border: {tokens.border};
  --awg-accent: {tokens.accent};
  --awg-accent-soft: {tokens.accent_soft};
  --awg-success: {tokens.success};
  --awg-warning: {tokens.warning};
  --awg-danger: {tokens.danger};
  --awg-radius: {tokens.radius};
}}
.stApp, .stApp .block-container {{
  background-color: var(--awg-bg) !important;
  color: var(--awg-text) !important;
  font-family: "Inter", sans-serif !important;
}}
.stApp .block-container {{
  max-width: 1480px !important;
  padding-top: 2rem !important;
  padding-bottom: 3rem !important;
}}
.awg-brand {{ display: flex; align-items: center; gap: 11px; padding: 8px 2px 14px; }}
.awg-brand-mark {{
  display: grid; place-items: center; width: 38px; height: 38px;
  border-radius: 12px; background: var(--awg-accent); color: #fff;
  font-size: 19px; font-weight: 800;
  box-shadow: 0 5px 14px color-mix(in srgb, var(--awg-accent) 24%, transparent);
}}
.awg-brand strong {{
  display: block; color: var(--awg-text); font-size: 17px; letter-spacing: -.3px;
}}
.awg-brand small {{
  display: block; margin-top: 2px; color: var(--awg-muted);
  font-size: 9px; letter-spacing: 1.25px; font-weight: 700;
}}
.awg-context {{
  display: flex; align-items: center; gap: 9px; padding: 11px 12px;
  color: var(--awg-text); background: var(--awg-surface-alt);
  border: 1px solid var(--awg-border); border-radius: 10px;
  font-size: 13px; overflow-wrap: anywhere;
}}
.awg-context-dot, .awg-status-dot {{
  width: 8px; height: 8px; flex: 0 0 8px; border-radius: 50%;
  background: var(--awg-success);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--awg-success) 16%, transparent);
}}
.awg-page-heading {{
  display: flex; justify-content: space-between; align-items: center; gap: 24px;
  padding: 18px 0 25px; border-bottom: 1px solid var(--awg-border); margin-bottom: 22px;
}}
.awg-page-heading h1 {{
  margin: 5px 0 3px; font-size: clamp(28px, 3vw, 39px);
  letter-spacing: -1.6px; line-height: 1.14;
}}
.awg-page-heading p, .awg-section-intro p {{
  margin: 6px 0 0; color: var(--awg-muted); font-size: 14px;
}}
.awg-eyebrow {{
  color: var(--awg-accent); font-size: 10px;
  font-weight: 800; letter-spacing: 1.35px;
}}
.awg-status {{
  display: flex; align-items: center; gap: 10px; white-space: nowrap;
  padding: 10px 13px; border: 1px solid var(--awg-border); border-radius: 999px;
  background: var(--awg-surface); color: var(--awg-muted); font-size: 12px; font-weight: 600;
}}
.awg-section-intro {{
  display: flex; justify-content: space-between; align-items: end;
  gap: 18px; margin: 5px 0 21px;
}}
.awg-section-intro h2 {{ margin: 5px 0 0; font-size: 25px; letter-spacing: -.7px; }}
.awg-step-count {{
  flex-shrink: 0; color: var(--awg-muted); background: var(--awg-surface);
  border: 1px solid var(--awg-border); border-radius: 999px;
  padding: 7px 11px; font-size: 11px;
}}
.stApp label, .stApp label p, .stApp [data-testid="stMarkdownContainer"],
.stApp .stCaption, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {{
  color: var(--awg-text) !important;
}}
.stApp [data-testid="stCaptionContainer"] {{
  color: var(--awg-muted) !important;
}}
.stApp section[data-testid="stSidebar"] {{
  background-color: var(--awg-surface) !important;
  border-right: 1px solid var(--awg-border) !important;
}}
.stApp [data-baseweb="select"] > div,
.stApp .stTextInput input, .stApp .stTextArea textarea,
.stApp [data-testid="stFileUploader"] {{
  background-color: var(--awg-surface) !important;
  color: var(--awg-text) !important;
  border-color: var(--awg-border) !important;
  border-radius: var(--awg-radius) !important;
}}
.stApp .stButton button[kind="primary"] {{
  background-color: var(--awg-accent) !important;
  color: #FFFFFF !important;
  border: none !important;
  border-radius: var(--awg-radius) !important;
  font-weight: 600 !important;
  transition: transform 120ms ease, filter 120ms ease;
}}
.stApp .stButton button:not([kind="primary"]), .stApp .stDownloadButton button {{
  background: var(--awg-surface) !important;
  color: var(--awg-text) !important;
  border: 1px solid var(--awg-border) !important;
  border-radius: var(--awg-radius) !important;
  font-weight: 600 !important;
  transition: transform 120ms ease, filter 120ms ease;
}}
.stApp .stButton button:hover, .stApp .stDownloadButton button:hover {{
  filter: brightness(1.08) !important;
  transform: translateY(-1px) !important;
}}
.stApp .stButton button:focus-visible,
.stApp .stDownloadButton button:focus-visible,
.stApp .stTextArea textarea:focus-visible,
.stApp .stTextInput input:focus-visible,
.stApp [data-baseweb="select"]:focus-within {{
  outline: 2px solid var(--awg-accent) !important;
  outline-offset: 2px !important;
  {focus_ring}
}}
.stApp [data-testid="stTabs"] button[role="tab"] {{
  color: var(--awg-muted) !important;
  font-weight: 600 !important;
}}
.stApp [data-testid="stTabs"] button[aria-selected="true"] {{
  color: var(--awg-accent) !important;
  border-color: var(--awg-accent) !important;
}}
.stApp [data-testid="stTabs"] button[role="tab"] {{ padding: 11px 14px !important; }}
.stApp [data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap: 8px; }}
.stApp [data-testid="stVerticalBlockBorderWrapper"] {{
  border-color: var(--awg-border) !important; border-radius: 14px !important;
  background: var(--awg-surface) !important;
}}
.stApp [data-testid="stMetric"] {{
  padding: 12px 14px; border-radius: 12px; background: var(--awg-surface);
}}
.stApp [data-testid="stExpander"] summary {{
  color: var(--awg-text) !important;
  border-radius: var(--awg-radius) !important;
}}
.stApp hr {{ border-color: var(--awg-border) !important; }}
.awg-card {{
  background: var(--awg-surface) !important;
  border: 1px solid var(--awg-border) !important;
  border-left: 3px solid var(--awg-accent) !important;
  border-radius: var(--awg-radius) !important;
  padding: 14px 16px !important;
  margin-bottom: 10px !important;
  animation: awg-fade 260ms ease both;
}}
.awg-step-number {{ color: var(--awg-accent) !important; font-weight: 700 !important; }}
.awg-chip {{ color: var(--awg-success) !important; font-size: 12px !important; }}
.awg-step-heading {{
  display: flex; align-items: center; gap: 12px;
  flex-wrap: wrap; color: var(--awg-text);
}}
.awg-step-heading strong {{ flex: 1 1 220px; font-size: 14px; }}
.awg-step-number {{ font-variant-numeric: tabular-nums; }}
.awg-step-kind, .awg-step-status {{
  padding: 4px 8px; border: 1px solid var(--awg-border); border-radius: 999px;
  font-size: 10px; line-height: 1.2; color: var(--awg-muted);
}}
.awg-step-status {{
  border-color: color-mix(in srgb, var(--awg-success) 30%, var(--awg-border));
  color: var(--awg-success);
}}
.awg-status-pending, .awg-status-skipped {{
  color: var(--awg-muted); border-color: var(--awg-border);
}}
.awg-status-blocked {{
  color: var(--awg-danger);
  border-color: color-mix(in srgb, var(--awg-danger) 30%, var(--awg-border));
}}
.awg-status-in_progress {{
  color: var(--awg-accent);
  border-color: color-mix(in srgb, var(--awg-accent) 30%, var(--awg-border));
}}
.awg-step-description {{
  margin: 8px 0 0 38px; color: var(--awg-muted);
  font-size: 13px; line-height: 1.55;
}}
.awg-step-branch {{
  margin: 9px 0 0 38px; padding: 8px 10px;
  border-left: 2px solid var(--awg-warning); color: var(--awg-muted);
  background: var(--awg-surface-alt); border-radius: 0 8px 8px 0; font-size: 12px;
}}
.awg-step-branch strong {{ color: var(--awg-warning); }}
.awg-step-meta {{ display: flex; flex-wrap: wrap; gap: 7px; margin: 10px 0 0 38px; }}
.awg-step-meta span {{
  color: var(--awg-muted); background: var(--awg-surface-alt);
  border-radius: 999px; padding: 4px 8px; font-size: 10px;
}}
.awg-explanation-title {{ color: var(--awg-accent) !important; font-weight: 600 !important; }}
.awg-explanation-item {{ color: var(--awg-muted) !important; font-size: 13px !important; }}
@keyframes awg-fade {{
  from {{ opacity: 0; transform: translateY(6px); }}
  to {{ opacity: 1; transform: none; }}
}}
@media (prefers-reduced-motion: reduce) {{
  .awg-card {{ animation: none !important; }}
  .stApp .stButton button, .stApp .stDownloadButton button {{ transition: none !important; }}
}}
@media (max-width: 640px) {{
  .stApp .block-container {{ padding: 1rem 1rem 2rem !important; }}
  .awg-page-heading, .awg-section-intro {{ align-items: flex-start; flex-direction: column; }}
  .awg-status {{ white-space: normal; }}
  .stApp .stButton button, .stApp .stDownloadButton button {{
    padding: 8px !important; font-size: 13px !important;
  }}
}}
{spacing}
</style>"""


def inject_theme(appearance: str, density: str) -> None:
    """Render the runtime stylesheet before any widgets are created."""
    st.html(theme_css(appearance, density))
