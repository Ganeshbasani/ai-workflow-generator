"""Tests for the dependency-free workflow diagram renderers."""

from __future__ import annotations

import re

from workflow_ai.diagram import (
    MermaidDiagramBackend,
    SvgDiagramBackend,
    build_component_html,
    topological_layers,
)
from workflow_ai.models import StepStatus, Workflow, WorkflowStep


def _workflow() -> Workflow:
    """A graph where provider order deliberately differs from dependency order."""
    return Workflow(
        title="Approval Flow",
        domain="business",
        steps=[
            WorkflowStep(
                id="s3",
                title="Archive",
                depends_on=["s2"],
                status=StepStatus.done,
            ),
            WorkflowStep(
                id="s2",
                title="Approve?",
                step_type="decision",
                depends_on=["s1"],
                condition="amount > 1000",
                on_true="s4",
                on_false="s3",
            ),
            WorkflowStep(id="s1", title="Submit request"),
            WorkflowStep(id="s4", title="Escalate", depends_on=["s2"]),
        ],
    )


def test_topological_layers_follow_dependencies() -> None:
    layers = topological_layers(_workflow())

    assert layers[0] == ["s1"]
    assert layers[1] == ["s2"]
    assert set(layers[2]) == {"s3", "s4"}


def test_svg_is_accessible() -> None:
    svg = SvgDiagramBackend().render(_workflow())

    assert '<svg' in svg
    assert 'role="img"' in svg
    assert 'aria-labelledby="awg-diagram-title awg-diagram-desc"' in svg
    assert '<title id="awg-diagram-title">Workflow diagram</title>' in svg
    assert "<desc id=\"awg-diagram-desc\">Approval Flow:" in svg
    assert "4 steps" in svg


def test_svg_renders_decision_diamond_and_branch_labels() -> None:
    svg = SvgDiagramBackend().render(_workflow())

    # Diamond polygon for the decision node.
    assert "<polygon" in svg
    # Labelled, dashed branch edges.
    assert ">true</text>" in svg
    assert ">false</text>" in svg
    assert svg.count("stroke-dasharray") >= 2


def test_svg_escapes_step_titles() -> None:
    workflow = Workflow(
        title="Escaping",
        domain="general",
        steps=[WorkflowStep(id="s1", title='A <script> & "quote"')],
    )
    svg = SvgDiagramBackend().render(workflow)

    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg
    assert "&amp;" in svg
    assert "&quot;" in svg


def test_svg_uses_topological_order_for_node_placement() -> None:
    svg = SvgDiagramBackend().render(_workflow())

    # Extract the x centre of each labelled node and verify dependencies are
    # placed to their left, regardless of provider emission order.
    nodes = re.findall(
        r'<text x="([\d.]+)"[^>]*>(Submit request|Approve\?|Archive|Escalate)</text>',
        svg,
    )
    centers = {label: float(x) for x, label in nodes}

    assert centers["Submit request"] < centers["Approve?"]
    assert centers["Approve?"] < centers["Archive"]
    assert centers["Approve?"] < centers["Escalate"]


def test_mermaid_backend_source_uses_branches() -> None:
    source = MermaidDiagramBackend.source(_workflow())

    assert source.startswith("flowchart TD")
    assert 's2{"Approve?"}' in source
    assert "s2 -- true --> s4" in source
    assert "s2 -- false --> s3" in source
    assert source.index("s1[") < source.index("s2{")


def test_mermaid_backend_render_is_safe_pre() -> None:
    markup = MermaidDiagramBackend().render(_workflow())

    assert '<pre class="mermaid"' in markup
    assert "&quot;" in markup  # labels are HTML-escaped inside <pre>
    assert "</pre>" in markup


def test_component_html_has_offline_svg_fallback() -> None:
    html = build_component_html(_workflow())

    # Self-contained SVG is always present.
    assert 'id="fallback"' in html
    assert 'role="img"' in html
    assert "<title id=\"awg-diagram-title\">Workflow diagram</title>" in html
    # Mermaid enhancement is optional and keeps the SVG when unavailable.
    assert "cdn.jsdelivr.net/npm/mermaid" in html
    assert "if (!window.mermaid) return" in html
    assert "catch(function () { /* keep SVG fallback */ })" in html
    # Responsive: the viewBox scales to the iframe and never overflows.
    assert "overflow-x: hidden" in html
    assert 'preserveAspectRatio="xMidYMid meet"' in html


def test_component_html_escapes_mermaid_payload() -> None:
    workflow = Workflow(
        title="Escaping",
        domain="general",
        steps=[WorkflowStep(id="s1", title='Say "hi"')],
    )
    html = build_component_html(workflow)

    # The JSON payload embeds the Mermaid source; a raw double quote in a JS
    # string would break out of the literal, so json.dumps must escape the
    # Mermaid node-label delimiters. Mermaid's _label converts inner " to '.
    assert 's1[\\"Say \'hi\'\\"]' in html
