"""Dependency-free workflow diagrams for Streamlit and exports.

The default renderer is a hand-built SVG: it works offline, needs no Graphviz
or Mermaid installation, and uses a theme-aware palette (dark by default for
backwards compatibility). A Mermaid backend is available as a pluggable
alternative and is what the Streamlit component prefers when the CDN is
reachable; the SVG is always embedded as a fallback so the diagram never
disappears offline.

Layout uses topological layers (see :func:`workflow_ai.validation.topological_order`)
rather than the order in which the provider happened to emit the steps.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from typing import Protocol

from .models import StepStatus, StepType, Workflow
from .validation import topological_order


@dataclass(frozen=True)
class DiagramPalette:
    """Colour tokens used by the self-contained SVG and Mermaid diagram."""

    background: str
    card: str
    border: str
    text: str
    muted: str
    true: str
    false: str
    done: str
    active: str
    blocked: str
    mermaid_theme: str


DARK_DIAGRAM = DiagramPalette(
    background="#0f172a",
    card="#111c34",
    border="#6366f1",
    text="#e2e8f0",
    muted="#94a3b8",
    true="#34d399",
    false="#f87171",
    done="#22c55e",
    active="#fbbf24",
    blocked="#f87171",
    mermaid_theme="dark",
)

LIGHT_DIAGRAM = DiagramPalette(
    background="#ffffff",
    card="#f6f7fb",
    border="#4f46e5",
    text="#171a2b",
    muted="#5c6478",
    true="#0e9f6e",
    false="#c4323f",
    done="#0e9f6e",
    active="#b45309",
    blocked="#c4323f",
    mermaid_theme="base",
)

DIAGRAM_PALETTES: dict[str, DiagramPalette] = {
    "dark": DARK_DIAGRAM,
    "Light": LIGHT_DIAGRAM,
    "light": LIGHT_DIAGRAM,
    "Dark": DARK_DIAGRAM,
}


def get_diagram_palette(theme: str) -> DiagramPalette:
    """Resolve a palette name, defaulting to the original dark diagram."""
    return DIAGRAM_PALETTES.get(theme, DARK_DIAGRAM)


_NODE_W = 180
_NODE_H = 58
_H_GAP = 80
_V_GAP = 46
_MARGIN = 42


class DiagramBackend(Protocol):
    """Pluggable diagram renderer (SVG, Mermaid, or a future Graphviz backend)."""

    def render(self, workflow: Workflow, *, theme: str = "dark") -> str:
        """Return markup representing ``workflow``."""
        ...


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def topological_layers(workflow: Workflow) -> list[list[str]]:
    """Group step ids into topological layers (longest-path depth)."""
    ordered = topological_order(workflow)  # raises on cycles
    depth: dict[str, int] = {step.id: 0 for step in ordered}

    for step in ordered:
        predecessors = set(step.depends_on)
        predecessors.update(
            source.id
            for source in workflow.steps
            if source.on_true == step.id or source.on_false == step.id
        )
        for dependency in predecessors:
            depth[step.id] = max(depth[step.id], depth[dependency] + 1)

    max_depth = max(depth.values(), default=0)
    layers: list[list[str]] = [[] for _ in range(max_depth + 1)]
    for step_id in (item.id for item in ordered):
        layers[depth[step_id]].append(step_id)
    return layers


def _positions(workflow: Workflow) -> dict[str, tuple[float, float]]:
    """Return centre coordinates for each step, laid out by layer."""
    layers = topological_layers(workflow)
    rows = max((len(layer) for layer in layers), default=1)
    total_h = rows * _NODE_H + max(rows - 1, 0) * _V_GAP + 2 * _MARGIN

    positions: dict[str, tuple[float, float]] = {}
    for column, layer in enumerate(layers):
        x = _MARGIN + _NODE_W / 2 + column * (_NODE_W + _H_GAP)
        column_height = len(layer) * _NODE_H + max(len(layer) - 1, 0) * _V_GAP
        offset = (total_h - column_height) / 2
        for row, step_id in enumerate(layer):
            y = offset + _NODE_H / 2 + row * (_NODE_H + _V_GAP)
            positions[step_id] = (x, y)
    return positions


def _canvas_size(workflow: Workflow) -> tuple[float, float]:
    layers = topological_layers(workflow)
    rows = max((len(layer) for layer in layers), default=1)
    width = len(layers) * _NODE_W + max(len(layers) - 1, 0) * _H_GAP + 2 * _MARGIN
    height = rows * _NODE_H + max(rows - 1, 0) * _V_GAP + 2 * _MARGIN
    return max(width, 320), max(height, 180)


def component_height(workflow: Workflow) -> int:
    """Suggest a Streamlit iframe height that fits the diagram without scrolling."""
    layers = topological_layers(workflow)
    rows = max((len(layer) for layer in layers), default=1)
    return int(min(560, max(200, rows * 96 + 70)))


# ---------------------------------------------------------------------------
# SVG backend
# ---------------------------------------------------------------------------


def _accent(step_status: StepStatus, palette: DiagramPalette) -> str:
    return {
        StepStatus.done: palette.done,
        StepStatus.in_progress: palette.active,
        StepStatus.blocked: palette.blocked,
        StepStatus.skipped: palette.muted,
    }.get(step_status, palette.border)


def _wrap_label(text: str, width: int = 22) -> list[str]:
    """Wrap a label into short lines so nodes stay a fixed size."""
    clean = " ".join(text.split())
    if not clean:
        return [""]
    words = clean.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:3]


def _render_node(
    step_id: str,
    label_lines: list[str],
    x: float,
    y: float,
    *,
    is_decision: bool,
    accent: str,
    palette: DiagramPalette,
) -> str:
    left = x - _NODE_W / 2
    top = y - _NODE_H / 2
    parts: list[str] = []
    if is_decision:
        points = (
            f"{x:.1f},{top:.1f} "
            f"{left + _NODE_W:.1f},{y:.1f} "
            f"{x:.1f},{top + _NODE_H:.1f} "
            f"{left:.1f},{y:.1f}"
        )
        parts.append(
            f'<polygon points="{points}" fill="{palette.card}" stroke="{accent}" '
            'stroke-width="2" />'
        )
    else:
        parts.append(
            f'<rect x="{left:.1f}" y="{top:.1f}" width="{_NODE_W}" '
            f'height="{_NODE_H}" rx="10" fill="{palette.card}" stroke="{accent}" '
            'stroke-width="2" />'
        )
    start_y = y - (len(label_lines) - 1) * 7 + 4
    for index, line in enumerate(label_lines):
        parts.append(
            f'<text x="{x:.1f}" y="{start_y + index * 14:.1f}" text-anchor="middle" '
            f'fill="{palette.text}" font-size="12" font-family="Inter, sans-serif">'
            f"{html.escape(line)}</text>"
        )
    return "".join(parts)


def _render_edge(
    source: tuple[float, float],
    target: tuple[float, float],
    *,
    color: str,
    label: str = "",
    dashed: bool = False,
) -> str:
    x1, y1 = source[0] + _NODE_W / 2, source[1]
    x2, y2 = target[0] - _NODE_W / 2, target[1]
    mid = (x1 + x2) / 2
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    parts = [
        f'<path d="M {x1:.1f} {y1:.1f} C {mid:.1f} {y1:.1f}, {mid:.1f} {y2:.1f}, '
        f'{x2:.1f} {y2:.1f}" fill="none" stroke="{color}" stroke-width="2"'
        f'{dash} marker-end="url(#arrow)" />'
    ]
    if label:
        parts.append(
            f'<text x="{mid:.1f}" y="{(y1 + y2) / 2 - 6:.1f}" text-anchor="middle" '
            f'fill="{color}" font-size="11" font-family="Inter, sans-serif">'
            f"{html.escape(label)}</text>"
        )
    return "".join(parts)


class SvgDiagramBackend:
    """Render a themed SVG flowchart with decision diamonds and branch labels."""

    def render(self, workflow: Workflow, *, theme: str = "dark") -> str:
        palette = get_diagram_palette(theme)
        width, height = _canvas_size(workflow)
        positions = _positions(workflow)
        by_id = {step.id: step for step in workflow.steps}

        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
            'width="100%" height="100%" preserveAspectRatio="xMidYMid meet" '
            'role="img" aria-labelledby="awg-diagram-title awg-diagram-desc" '
            'style="max-width:100%;background:transparent">',
            '<title id="awg-diagram-title">Workflow diagram</title>',
            '<desc id="awg-diagram-desc">'
            f"{html.escape(workflow.title)}: {len(workflow.steps)} steps, "
            "arrows show dependencies and labelled arrows show decision branches."
            "</desc>",
            "<defs>"
            f'<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{palette.muted}" />'
            "</marker></defs>",
        ]

        # Edges first so nodes sit on top of the arrow tips.
        for step in workflow.steps:
            if step.id not in positions:
                continue
            branch_targets = (
                {step.on_true, step.on_false} if step.step_type == StepType.decision else set()
            )
            for dependency in step.depends_on:
                if dependency in branch_targets:
                    continue
                if dependency in positions:
                    parts.append(
                        _render_edge(positions[dependency], positions[step.id], color=palette.muted)
                    )
            if step.step_type == StepType.decision:
                for target_id, label, color in (
                    (step.on_true, "true", palette.true),
                    (step.on_false, "false", palette.false),
                ):
                    if target_id and target_id in positions:
                        parts.append(
                            _render_edge(
                                positions[step.id],
                                positions[target_id],
                                color=color,
                                label=label,
                                dashed=True,
                            )
                        )

        for step_id, (x, y) in positions.items():
            step = by_id[step_id]
            parts.append(
                _render_node(
                    step_id,
                    _wrap_label(step.title),
                    x,
                    y,
                    is_decision=step.step_type == StepType.decision,
                    accent=_accent(step.status, palette),
                    palette=palette,
                )
            )

        parts.append("</svg>")
        return "".join(parts)


# ---------------------------------------------------------------------------
# Mermaid backend + Streamlit component
# ---------------------------------------------------------------------------


class MermaidDiagramBackend:
    """Emit Mermaid ``flowchart TD`` source with decision diamonds and branches."""

    @staticmethod
    def source(workflow: Workflow) -> str:
        from .exporters import to_mermaid

        return to_mermaid(workflow)

    def render(self, workflow: Workflow, *, theme: str = "dark") -> str:
        palette = get_diagram_palette(theme)
        source = self.source(workflow)
        return (
            '<pre class="mermaid" style="background:transparent;color:'
            f'{palette.text};font-family:Inter,sans-serif">'
            f"{html.escape(source)}</pre>"
        )


def build_component_html(workflow: Workflow, *, theme: str = "dark") -> str:
    """Return themed HTML for ``st.iframe``.

    Mermaid is enhanced when the CDN is available; a fully self-contained SVG
    is always present and is shown if Mermaid fails to load (offline use).
    """
    palette = get_diagram_palette(theme)
    svg = SvgDiagramBackend().render(workflow, theme=theme)
    source = MermaidDiagramBackend.source(workflow)
    payload = json.dumps(source)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  html, body {{ margin: 0; padding: 0; height: 100%;
    background: {palette.background}; color: {palette.text};
    font-family: Inter, sans-serif; overflow-x: hidden; }}
  #fallback {{ width: 100%; height: calc(100% - 26px); }}
  #mermaid-target {{ display: none; width: 100%; height: calc(100% - 26px); overflow-x: auto; }}
  .caption {{ color: {palette.muted}; font-size: 12px; margin: 4px 0 8px; }}
</style>
</head>
<body>
  <div class="caption">Flow order follows the validated dependency graph.</div>
  <div id="fallback">{svg}</div>
  <div id="mermaid-target"></div>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script>
    (function () {{
      var source = {payload};
      var target = document.getElementById('mermaid-target');
      if (!window.mermaid) return; // offline: keep the inline SVG
      try {{
        mermaid.initialize({{
          startOnLoad: false,
          theme: '{palette.mermaid_theme}',
          themeVariables: {{
            background: '{palette.background}', primaryColor: '{palette.card}',
            primaryBorderColor: '{palette.border}', primaryTextColor: '{palette.text}',
            lineColor: '{palette.muted}', fontFamily: 'Inter, sans-serif'
          }}
        }});
        mermaid.render('awg-mermaid', source).then(function (result) {{
          target.innerHTML = result.svg;
          target.style.display = 'block';
          document.getElementById('fallback').style.display = 'none';
        }}).catch(function () {{ /* keep SVG fallback */ }});
      }} catch (e) {{ /* keep SVG fallback */ }}
    }})();
  </script>
</body>
</html>"""


__all__ = [
    "DARK_DIAGRAM",
    "DIAGRAM_PALETTES",
    "LIGHT_DIAGRAM",
    "DiagramBackend",
    "DiagramPalette",
    "MermaidDiagramBackend",
    "SvgDiagramBackend",
    "build_component_html",
    "component_height",
    "get_diagram_palette",
    "topological_layers",
]
