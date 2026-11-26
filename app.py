"""Architect AI — redesigned, production-quality Streamlit entrypoint.

A thin orchestration layer over the ``workflow_ai`` services. The UI is a set of
focused tabs with a fresh light/dark theme, an inline workflow editor,
drag-and-drop step ordering, a command palette with keyboard shortcuts, and an
analytics dashboard. All domain logic still lives in the package.
"""

from __future__ import annotations

import html
import sys
from collections.abc import Callable
from functools import partial
from pathlib import Path
from uuid import uuid4

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import streamlit as st

from workflow_ai.config import get_settings
from workflow_ai.diagram import build_component_html, component_height
from workflow_ai.errors import (
    CostCeilingError,
    DocumentError,
    InputValidationError,
    RateLimitError,
    WorkflowError,
    WorkflowValidationError,
)
from workflow_ai.exporters import to_csv, to_json, to_markdown, to_mermaid, to_pdf
from workflow_ai.factory import build_generation_stack, build_project_stack
from workflow_ai.ingest import extract_text as extract_document_text
from workflow_ai.logging_config import get_logger
from workflow_ai.models import (
    GenerationMetadata,
    GenerationRequest,
    GenerationResult,
    Project,
    StepStatus,
    StepType,
    WorkflowStep,
)
from workflow_ai.ui.analytics import (
    domain_frame,
    latency_frame,
    provider_frame,
    run_timeline_frame,
    status_frame,
    step_type_frame,
    summarize,
)
from workflow_ai.ui.components import command_palette, step_list
from workflow_ai.ui.editor import save_frame, save_order, steps_to_frame
from workflow_ai.ui.theme import APPEARANCES, DARK, DENSITIES, Palette, get_palette, inject_theme
from workflow_ai.validation import topological_order

settings = get_settings()
service, mode_badge = build_generation_stack(settings)
projects, editor, runs = build_project_stack(settings)
logger = get_logger(__name__)

CATEGORIES = [
    "Educational Institutes",
    "Business Organizations",
    "Real Estate",
    "Software Industries",
    "Software Projects",
    "Hospitals",
]

STARTER_BRIEFS = [
    (
        "Customer onboarding",
        "Software Industries",
        "A new customer signs up, verifies their email, completes their profile, selects a plan, and receives a welcome message. Route accounts that fail verification to a support review.",
    ),
    (
        "Incident response",
        "Software Projects",
        "When a production incident is detected, acknowledge it, assess severity, assign an incident lead, notify affected teams, mitigate the issue, verify recovery, and publish a post-incident review. Escalate unresolved critical incidents to the on-call lead.",
    ),
    (
        "Patient intake",
        "Hospitals",
        "A patient requests an appointment, shares their symptoms and medical history, completes insurance verification, and is triaged by a clinician. Urgent cases should be escalated immediately; routine cases are scheduled and receive preparation instructions.",
    ),
]

_STATUSES = [status.value for status in StepStatus]
_TYPES = [item.value for item in StepType]
_TABS = ("Generate", "Workflow", "Editor", "Library", "Run", "Analytics")

_COMMANDS = [
    {"id": "workflow", "label": "Go to Workflow", "hint": "View result"},
    {"id": "generate", "label": "Go to Generate", "hint": "New workflow · Ctrl+Enter"},
    {"id": "library", "label": "Go to Library", "hint": "Saved workflows"},
    {"id": "analytics", "label": "Go to Analytics", "hint": "Dashboard"},
    {"id": "toggle_theme", "label": "Toggle light / dark theme", "hint": "Appearance"},
    {"id": "toggle_density", "label": "Toggle comfortable / compact", "hint": "Density"},
]
_TAB_COMMANDS = {
    "workflow": "Workflow",
    "generate": "Generate",
    "library": "Library",
    "analytics": "Analytics",
}

st.set_page_config(page_title="Architect AI", page_icon="🧩", layout="wide")


# ---------------------------------------------------------------------------
# Pure presentation helpers (escaped HTML keeps model output inert)
# ---------------------------------------------------------------------------


def step_html(
    step: WorkflowStep,
    number: int,
    palette: Palette = DARK,
    step_labels: dict[str, str] | None = None,
) -> str:
    """Render a compact workflow node, escaping all model-derived text."""
    _ = palette  # Theme tokens are consumed by the shared stylesheet.
    detail = f'<p class="awg-step-description">{html.escape(step.description)}</p>' if step.description else ""
    metadata = [step.owner_role, step.estimated_duration]
    if step.depends_on:
        dependencies = [
            (step_labels or {}).get(dependency, dependency)
            for dependency in step.depends_on
        ]
        metadata.append(f"After {', '.join(dependencies)}")
    meta_html = "".join(f"<span>{html.escape(value)}</span>" for value in metadata if value)
    branch = ""
    if step.condition:
        branch = (
            '<div class="awg-step-branch"><strong>Decision</strong> · '
            f"{html.escape(step.condition)}</div>"
        )
    meta = f'<div class="awg-step-meta">{meta_html}</div>' if meta_html else ""
    kind = html.escape(step.step_type.value.replace("_", " ").title())
    status_value = html.escape(step.status.value)
    status_label = html.escape(step.status.value.replace("_", " ").title())
    return (
        '<div class="awg-card"><div class="awg-step-heading">'
        f'<span class="awg-step-number">{number:02d}</span>'
        f'<strong>{html.escape(step.display_text)}</strong>'
        f'<span class="awg-step-kind">{kind}</span>'
        f'<span class="awg-step-status awg-status-{status_value}">{status_label}</span>'
        f"</div>{detail}{branch}{meta}</div>"
    )


def explanation_html(title: str, items: list[str], color: str) -> str:
    """Render a themed, HTML-escaped list of AI explanations."""
    heading = (
        f'<div style="color: {color}; font-weight: 600; margin-top: 8px;">'
        f"{html.escape(title)}</div>"
    )
    bullets = "".join(
        f'<div style="color: #94a3b8; font-size: 13px; margin: 3px 0 3px 14px;">'
        f"• {html.escape(item)}</div>"
        for item in items
    )
    return heading + bullets


def uploaded_context(upload: object) -> str:
    """Extract text from an upload, mapping typed errors to safe UI messages."""
    if upload is None:
        return ""
    try:
        return extract_document_text(upload, settings)
    except DocumentError as exc:
        st.error(exc.user_message)
        return ""


def result_from_project(project: Project) -> GenerationResult:
    """Rebuild a display result from the stored aggregate (no regeneration)."""
    meta: GenerationMetadata | None = project.metadata
    return GenerationResult(
        workflow=project.workflow,
        provider=meta.provider if meta else "rule",
        requested_provider=meta.requested_provider if meta else None,
        model=meta.model if meta else None,
        degraded=meta.degraded if meta else False,
        fallback_reason=meta.fallback_reason if meta else None,
        latency_ms=meta.latency_ms if meta else 0.0,
        attempts=meta.attempts if meta else 1,
        tokens_in=meta.tokens_in if meta else 0,
        tokens_out=meta.tokens_out if meta else 0,
        estimated_cost_usd=meta.estimated_cost_usd if meta else 0.0,
    )


def sync_active(project_id: str, owner_id: str) -> None:
    """Reload the active project so every tab reflects an edit on the next rerun."""
    st.session_state["result"] = result_from_project(projects.load(project_id, owner_id))
    # Bumping the revision forces the inline DataFrame editor to re-hydrate from
    # the freshly validated graph instead of replaying stale cell edits.
    st.session_state["editor_revision"] = st.session_state.get("editor_revision", 0) + 1


def apply_edit(action: Callable[[], object]) -> bool:
    """Run a validated mutation, surfacing typed failures as friendly errors.

    Editor and run actions reject invalid graphs (unknown dependencies, cycles,
    bad branch targets). Those messages are written for end users, so they can
    be shown directly instead of leaking a Streamlit stack trace.
    """
    try:
        action()
    except (InputValidationError, WorkflowValidationError) as exc:
        st.error(str(exc))
        return False
    return True


def _focus(tab_label: str) -> None:
    """Switch tabs from a button callback (runs before widgets are created)."""
    st.session_state["main_tabs"] = tab_label


def _focus_workflow() -> None:
    _focus("Workflow")


def _focus_generate() -> None:
    _focus("Generate")


# ---------------------------------------------------------------------------
# Session scope and deferred tab navigation
# ---------------------------------------------------------------------------

if "session_id" not in st.session_state:
    # A browser refresh starts a new Streamlit session. Keep the anonymous
    # scope in the URL so saved workflows remain visible after a refresh.
    scope = st.query_params.get("sid")
    if not isinstance(scope, str) or not scope:
        scope = uuid4().hex[:12]
        st.query_params["sid"] = scope
    st.session_state["session_id"] = scope
if "active_project_id" not in st.session_state:
    st.session_state["active_project_id"] = None

# A deferred tab request is applied before the tabs widget exists.
_pending_tab = st.session_state.pop("pending_tab", None)
if _pending_tab in _TABS:
    st.session_state["main_tabs"] = _pending_tab

owner_id: str = st.session_state["session_id"]


# ---------------------------------------------------------------------------
# Sidebar: preferences, command palette and quick context
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        '<div class="awg-brand"><span class="awg-brand-mark">A</span>'
        '<span><strong>Architect</strong><small>WORKFLOW STUDIO</small></span></div>',
        unsafe_allow_html=True,
    )
    st.caption("Turn the way work happens into a plan people can follow.")
    st.divider()
    st.markdown("#### Your workspace")
    active_title = "No workflow selected"
    active_project_id = st.session_state.get("active_project_id")
    if active_project_id:
        try:
            active_title = projects.load(active_project_id, owner_id).display_title
        except WorkflowError:
            active_title = "No workflow selected"
    st.markdown(
        f'<div class="awg-context"><span class="awg-context-dot"></span>'
        f'<span>{html.escape(active_title)}</span></div>',
        unsafe_allow_html=True,
    )
    if st.button("+  Create a workflow", key="sidebar_create", width="stretch"):
        st.session_state["main_tabs"] = "Generate"
        st.rerun()

    st.divider()
    st.markdown("#### Preferences")

    # Appearance is shareable via the URL; density is per-session.
    appearance_choice = st.segmented_control(
        "Appearance",
        APPEARANCES,
        default="Light",
        key="theme",
        bind="query-params",
        on_change="rerun",
    )
    density_choice = st.segmented_control(
        "Density",
        DENSITIES,
        default="Comfortable",
        key="density",
        persist_state="session",
        on_change="rerun",
    )
    appearance = appearance_choice or "Light"
    density = density_choice or "Comfortable"
    palette = get_palette(appearance)

    st.divider()
    st.markdown("#### Quick actions")
    st.caption("Press **Ctrl/Cmd + K** for commands, **Ctrl/Cmd + Enter** to generate.")
    command_result = command_palette(
        _COMMANDS,
        tokens={
            "surface": palette.surface,
            "surface-alt": palette.surface_alt,
            "text": palette.text,
            "muted": palette.muted,
            "border": palette.border,
            "accent": palette.accent,
            "radius": palette.radius,
        },
        key="awg_command_palette",
        on_command_change=lambda: None,
    )

    # Commands arrive as one-shot triggers. Tabs can be set here because the
    # tabs widget has not been instantiated yet in this run.
    command = getattr(command_result, "command", None)
    if command in _TAB_COMMANDS:
        st.session_state["main_tabs"] = _TAB_COMMANDS[str(command)]
    elif command == "toggle_theme":
        st.query_params["theme"] = "Dark" if appearance == "Light" else "Light"
        st.rerun()
    elif command == "toggle_density":
        st.session_state["pending_density"] = (
            "Compact" if density == "Comfortable" else "Comfortable"
        )
        st.rerun()

    # Apply a density change requested from the palette before its widget exists.
    pending_density = st.session_state.pop("pending_density", None)
    if pending_density in DENSITIES:
        st.session_state["density"] = pending_density
        st.rerun()

    st.divider()
    st.caption(f"Generation mode: **{mode_badge}**")
    st.caption(f"Session: `{owner_id}`")

# Runtime styling mirrors config.toml but follows the in-app toggle instantly.
inject_theme(appearance, density)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="awg-page-heading"><div><div class="awg-eyebrow">'
    'WORKFLOW DESIGN, MADE CLEAR</div><h1>Build a better way to work.</h1>'
    '<p>Describe a process. Get a thoughtful, editable blueprint your team can use.</p>'
    '</div><div class="awg-status"><span class="awg-status-dot"></span>'
    f'{html.escape(mode_badge)}</div></div>',
    unsafe_allow_html=True,
)

tabs = st.tabs(list(_TABS), key="main_tabs", on_change="rerun")
generate_tab, workflow_tab, editor_tab, library_tab, run_tab, analytics_tab = tabs


# ---------------------------------------------------------------------------
# 1. Generate
# ---------------------------------------------------------------------------

with generate_tab:
    st.markdown(
        '<div class="awg-section-intro"><div><div class="awg-eyebrow">'
        '01 — START WITH THE OUTCOME</div><h2>What needs to happen?</h2>'
        '<p>Give the process a goal, the people involved, and any decisions or exceptions.</p>'
        '</div><span class="awg-step-count">Takes about a minute</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown("**Start with a proven pattern**")
    starter_cols = st.columns(3)
    for idx, (label, starter_category, starter_prompt) in enumerate(STARTER_BRIEFS):
        with starter_cols[idx], st.container(border=True):
            st.markdown(f"**{label}**")
            st.caption(starter_category)
            if st.button("Use this brief", key=f"starter_{idx}", width="stretch"):
                st.session_state["workflow_category"] = starter_category
                st.session_state["workflow_description"] = starter_prompt
                st.rerun()

    with st.container(border=True):
        st.markdown("#### Your process")
        form_left, form_right = st.columns([1, 1])
        with form_left:
            category = st.selectbox("Industry or team", CATEGORIES, key="workflow_category")
        with form_right:
            uploaded_file = st.file_uploader(
                "Add context (optional)", type=["pdf", "txt"],
                help="Upload a PDF or text file with policies, roles, or process details.",
            )
        user_input = st.text_area(
            "Workflow description",
            placeholder=(
                "For example: When a customer requests a refund, verify the order, "
                "check eligibility, approve or escalate exceptions, issue the refund, "
                "and notify the customer."
            ),
            height=145,
            key="workflow_description",
            help="Include the trigger, the main steps, who owns them, and what happens when something goes wrong.",
        )
        action_left, action_right = st.columns([1, 3])
        with action_left:
            generate_clicked = st.button(
                "✦  Create workflow", type="primary", width="stretch", key="generate_workflow"
            )
        with action_right:
            st.caption("Your draft is validated and saved automatically. You can edit every step.")

    if generate_clicked:
        if len(user_input) > settings.max_input_chars:
            st.error(
                f"Please shorten your description to {settings.max_input_chars:,} "
                "characters or fewer."
            )
        else:
            file_content = uploaded_context(uploaded_file)
            if not user_input.strip() and not file_content.strip():
                st.warning("Please provide a description or upload a file.")
            else:
                with st.status("Architecting your workflow…", expanded=False) as progress:
                    result: GenerationResult | None = None
                    try:
                        result = service.generate(
                            GenerationRequest(
                                description=user_input,
                                category=category,
                                additional_context=file_content,
                                session_id=owner_id,
                            )
                        )
                        progress.update(label="Workflow ready", state="complete")
                    except InputValidationError as exc:
                        st.error(str(exc))
                        progress.update(label="Invalid input", state="error")
                        result = None
                    except (RateLimitError, CostCeilingError) as exc:
                        st.error(exc.user_message)
                        progress.update(label="Provider limit reached", state="error")
                        result = None
                    except WorkflowError:
                        logger.exception("Workflow generation failed")
                        st.error("Workflow generation failed. Please try again.")
                        progress.update(label="Generation failed", state="error")
                        result = None

                if result is not None and result.workflow.steps:
                    # Persist immediately: generation survives refresh and restart.
                    saved = projects.create_from_result(
                        result,
                        owner_id=owner_id,
                        prompt=user_input,
                        category=category,
                    )
                    st.session_state["active_project_id"] = saved.id
                    st.session_state["result"] = result
                    st.session_state["editor_revision"] = (
                        st.session_state.get("editor_revision", 0) + 1
                    )
                    st.toast("Workflow generated and saved", icon="✨")
                    st.session_state["pending_tab"] = "Workflow"
                    st.rerun()
                else:
                    st.warning(
                        "No specific workflow steps were detected. "
                        "Please describe the process more clearly."
                    )


# ---------------------------------------------------------------------------
# 2. Workflow — result, diagram, exports and explanations
# ---------------------------------------------------------------------------

with workflow_tab:
    stored_result: GenerationResult | None = st.session_state.get("result")
    if stored_result is None:
        with st.container(border=True):
            st.markdown("### Your canvas is ready")
            st.markdown(
                "Start with a process brief and Architect will map the steps, "
                "dependencies, decisions, and points that need a human review."
            )
            st.button(
                "Create your first workflow",
                type="primary",
                key="empty_canvas_create",
                on_click=_focus_generate,
            )
    else:
        st.markdown(
            '<div class="awg-eyebrow">02 — REVIEW YOUR BLUEPRINT</div>',
            unsafe_allow_html=True,
        )
        st.subheader(stored_result.workflow.title)
        meta1, meta2, meta3, meta4 = st.columns(4, border=True)
        with meta1:
            st.metric("Process stages", len(stored_result.workflow.steps))
        with meta2:
            st.metric("Decisions", sum(1 for step in stored_result.workflow.steps if step.step_type.value == "decision"))
        with meta3:
            st.metric("Domain", stored_result.workflow.domain or "General")
        with meta4:
            st.metric("Created with", "AI" if stored_result.provider != "rule" else "Offline engine")
        if stored_result.degraded:
            st.warning(
                f"⚠️ {stored_result.fallback_reason or 'AI was unavailable'} "
                "Offline rules were used instead."
            )

        workflow = stored_result.workflow

        # Topological order replaces provider emission order everywhere.
        ordered_steps = topological_order(workflow)
        step_labels = {
            step.id: f"{number:02d} · {step.title}"
            for number, step in enumerate(ordered_steps, start=1)
        }
        for number, step in enumerate(ordered_steps, start=1):
            st.markdown(
                step_html(step, number, palette, step_labels),
                unsafe_allow_html=True,
            )

        st.markdown("🗺️ **Workflow diagram**")
        # st.iframe is the supported successor to deprecated components.v1.html
        # and adds an accessible label plus keyboard focus.
        st.iframe(
            build_component_html(workflow, theme=appearance),
            height=component_height(workflow),
            alt="Workflow diagram showing steps, dependencies and decision branches",
            tab_index=0,
        )

        st.markdown("📦 **Exports** — all five are generated from the same validated graph.")
        exp_c1, exp_c2 = st.columns(2)
        with exp_c1:
            st.download_button(
                "📂 Export as CSV",
                data=to_csv(workflow),
                file_name="workflow.csv",
                mime="text/csv",
                width="stretch",
            )
        with exp_c2:
            st.download_button(
                "📄 Generate PDF Report",
                data=to_pdf(workflow),
                file_name="workflow.pdf",
                mime="application/pdf",
                width="stretch",
            )

        exp_c3, exp_c4, exp_c5 = st.columns(3)
        with exp_c3:
            st.download_button(
                "📦 Export as JSON",
                data=to_json(workflow),
                file_name="workflow.json",
                mime="application/json",
                width="stretch",
            )
        with exp_c4:
            st.download_button(
                "📝 Export as Markdown",
                data=to_markdown(workflow),
                file_name="workflow.md",
                mime="text/markdown",
                width="stretch",
            )
        with exp_c5:
            st.download_button(
                "🔀 Export Mermaid source",
                data=to_mermaid(workflow).encode("utf-8"),
                file_name="workflow.mmd",
                mime="text/plain",
                width="stretch",
            )

        with st.expander("💡 Why this workflow", expanded=False):
            sections = (
                ("Assumptions", workflow.assumptions, palette.accent),
                ("Risks", workflow.risks, palette.danger),
                ("Missing information", workflow.missing_information, palette.warning),
                (
                    "Suggested improvements",
                    workflow.suggested_improvements,
                    palette.success,
                ),
            )
            has_explanations = False
            for title, items, color in sections:
                if items:
                    has_explanations = True
                    st.markdown(explanation_html(title, items, color), unsafe_allow_html=True)

            rationales = [
                (number, step)
                for number, step in enumerate(topological_order(workflow), start=1)
                if step.rationale
            ]
            if rationales:
                has_explanations = True
                st.markdown("**Step rationale**")
                for number, step in rationales:
                    st.markdown(
                        f'<div style="color: {palette.muted}; font-size: 13px; '
                        f'margin: 4px 0;"><b>{number}. {html.escape(step.title)}</b> — '
                        f"{html.escape(step.rationale or '')}</div>",
                        unsafe_allow_html=True,
                    )
            if not has_explanations:
                st.caption("No explanations were provided for this workflow.")


# ---------------------------------------------------------------------------
# 3. Editor — inline table, drag-and-drop and fine-grained controls
# ---------------------------------------------------------------------------

with editor_tab:
    st.markdown(
        '<div class="awg-section-intro"><div><div class="awg-eyebrow">'
        '03 — SHAPE THE DETAILS</div><h2>Refine your blueprint</h2>'
        '<p>Adjust ownership, sequence, and decision paths. Every change is checked against the workflow graph.</p>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    active_id: str | None = st.session_state.get("active_project_id")
    if not active_id:
        st.caption("Generate or load a workflow to enable editing.")
    else:
        pid: str = active_id  # narrow the optional session value once
        current = projects.load(pid, owner_id)
        workflow = current.workflow
        revision = st.session_state.get("editor_revision", 0)

        st.markdown("#### Inline editor")
        st.caption(
            "Edit cells directly and save, or drag the cards below to reorder steps. "
            "Every save re-validates the dependency graph."
        )
        frame = st.data_editor(
            steps_to_frame(workflow),
            key=f"step_table_{pid}_{revision}",
            hide_index=True,
            width="stretch",
            column_config={
                "id": st.column_config.TextColumn("ID", disabled=True),
                "title": st.column_config.TextColumn("Title"),
                "step_type": st.column_config.SelectboxColumn("Type", options=_TYPES),
                "depends_on": st.column_config.TextColumn("Depends on"),
                "condition": st.column_config.TextColumn("Condition"),
                "on_true": st.column_config.TextColumn("On true"),
                "on_false": st.column_config.TextColumn("On false"),
                "status": st.column_config.SelectboxColumn("Status", options=_STATUSES),
                "notes": st.column_config.TextColumn("Notes"),
            },
        )
        if st.button("💾 Save table") and apply_edit(
            partial(save_frame, editor, pid, owner_id, workflow, frame)
        ):
            st.toast("Workflow updated", icon="💾")
            sync_active(pid, owner_id)
            st.rerun()

        st.markdown("#### Reorder steps")
        st.caption("Drag a card, or focus one and press **Alt + ↑ / ↓**.")
        drag_result = step_list(
            [
                {"id": step.id, "title": step.title, "step_type": step.step_type.value}
                for step in workflow.steps
            ],
            tokens={
                "surface": palette.surface,
                "surface-alt": palette.surface_alt,
                "text": palette.text,
                "muted": palette.muted,
                "border": palette.border,
                "accent": palette.accent,
                "radius": palette.radius,
            },
            key="awg_step_list",
            on_order_change=lambda: None,
        )
        emitted_order = getattr(drag_result, "order", None)
        new_order = [str(item) for item in emitted_order] if isinstance(emitted_order, list) else []
        if new_order and new_order != [step.id for step in workflow.steps] and apply_edit(
            partial(save_order, editor, pid, owner_id, workflow, new_order)
        ):
            st.toast("Step order saved", icon="🔀")
            sync_active(pid, owner_id)
            st.rerun()

        # Accessible, keyboard-friendly fallback for the drag interaction.
        st.markdown("#### Fine-grained controls")
        for step in workflow.steps:
            up_col, down_col = st.columns(2)
            with up_col:
                if st.button("↑ Move up", key=f"edit_up_{step.id}") and apply_edit(
                    partial(editor.move_step, pid, step.id, -1, owner_id)
                ):
                    st.toast("Step moved up", icon="⬆️")
                    sync_active(pid, owner_id)
                    st.rerun()
            with down_col:
                if st.button("↓ Move down", key=f"edit_down_{step.id}") and apply_edit(
                    partial(editor.move_step, pid, step.id, 1, owner_id)
                ):
                    st.toast("Step moved down", icon="⬇️")
                    sync_active(pid, owner_id)
                    st.rerun()

        with st.expander("Advanced step fields", expanded=False):
            for step in workflow.steps:
                with st.container(border=True):
                    title_col, type_col = st.columns([3, 1])
                    new_title = title_col.text_input(
                        "Step title",
                        value=step.title,
                        key=f"edit_title_{step.id}",
                        label_visibility="collapsed",
                    )
                    new_type = type_col.selectbox(
                        "Step type",
                        _TYPES,
                        index=_TYPES.index(step.step_type.value),
                        key=f"edit_type_{step.id}",
                        label_visibility="collapsed",
                    )
                    save_col, del_col = st.columns(2)
                    if save_col.button("💾 Save", key=f"edit_save_{step.id}") and apply_edit(
                        partial(
                            editor.update_step,
                            pid,
                            step.id,
                            owner_id,
                            title=new_title,
                            step_type=StepType(new_type),
                        )
                    ):
                        st.toast("Step saved", icon="💾")
                        sync_active(pid, owner_id)
                        st.rerun()
                    if del_col.button("✕ Delete", key=f"edit_delete_{step.id}") and apply_edit(
                        partial(editor.delete_step, pid, step.id, owner_id)
                    ):
                        st.toast("Step deleted", icon="🗑")
                        sync_active(pid, owner_id)
                        st.rerun()

                    with st.expander(f"Dependencies & branch — {step.title}", expanded=False):
                        deps = st.text_input(
                            "Depends on (comma-separated step ids)",
                            value=", ".join(step.depends_on),
                            key=f"edit_deps_{step.id}",
                        )
                        condition = st.text_input(
                            "Condition",
                            value=step.condition or "",
                            key=f"edit_condition_{step.id}",
                        )
                        on_true = st.text_input(
                            "On true (step id)",
                            value=step.on_true or "",
                            key=f"edit_on_true_{step.id}",
                        )
                        on_false = st.text_input(
                            "On false (step id)",
                            value=step.on_false or "",
                            key=f"edit_on_false_{step.id}",
                        )
                        if st.button("Save graph fields", key=f"edit_graph_{step.id}"):
                            dep_ids = [item.strip() for item in deps.split(",") if item.strip()]
                            graph_saved = apply_edit(
                                partial(
                                    editor.update_step,
                                    pid,
                                    step.id,
                                    owner_id,
                                    depends_on=dep_ids,
                                    condition=condition or None,
                                )
                            ) and apply_edit(
                                partial(
                                    editor.set_branch,
                                    pid,
                                    step.id,
                                    owner_id,
                                    condition=condition or None,
                                    on_true=on_true or None,
                                    on_false=on_false or None,
                                )
                            )
                            if graph_saved:
                                st.toast("Graph fields saved", icon="🔗")
                                sync_active(pid, owner_id)
                                st.rerun()

        new_step_title = st.text_input("New step title", key="new_step_title")
        if st.button("+ Add step", key="add_step") and apply_edit(
            partial(editor.add_step, pid, new_step_title, owner_id)
        ):
            st.toast("Step added", icon="✅")
            sync_active(pid, owner_id)
            st.rerun()


# ---------------------------------------------------------------------------
# 4. Library — saved workflows with search, load, rename and delete
# ---------------------------------------------------------------------------

with library_tab:
    st.markdown(
        '<div class="awg-section-intro"><div><div class="awg-eyebrow">'
        'YOUR WORKSPACE</div><h2>Saved blueprints</h2>'
        '<p>Find, revisit, and keep improving the processes you have designed.</p>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    saved_projects = projects.list_projects(owner_id)
    if not saved_projects:
        st.caption("No saved workflows yet. Generate one to start your history.")
    else:
        search = st.text_input("Search by name or domain", key="library_search")
        term = search.strip().lower()
        if term:
            saved_projects = [
                item
                for item in saved_projects
                if term in item.display_title.lower() or term in item.workflow.domain.lower()
            ]
        if not saved_projects:
            st.caption("No saved workflows match your search.")
        else:
            labels = [
                f"{item.display_title} ({item.workflow.domain})" for item in saved_projects
            ]
            selected_label = st.selectbox("Saved workflows", labels, key="saved_project_picker")
            selected = saved_projects[labels.index(selected_label)]

            load_col, rename_col, delete_col = st.columns(3)
            with load_col:
                if st.button("📂 Load", key="load_project", on_click=_focus_workflow):
                    st.session_state["active_project_id"] = selected.id
                    st.session_state["result"] = result_from_project(selected)
                    st.session_state["editor_revision"] = (
                        st.session_state.get("editor_revision", 0) + 1
                    )
                    st.toast("Workflow loaded", icon="📂")
                    # Editor and Run tabs render before the Library tab in this
                    # run, so rerun to make the loaded workflow visible to them.
                    st.rerun()
            with rename_col:
                new_name = st.text_input(
                    "New name",
                    value=selected.display_title,
                    key="rename_project_input",
                    label_visibility="collapsed",
                )
                if st.button("✏️ Rename", key="rename_project") and apply_edit(
                    partial(projects.rename, selected.id, new_name, owner_id)
                ):
                    sync_active(selected.id, owner_id)
                    st.toast("Workflow renamed", icon="✏️")
                    st.rerun()
            with delete_col:
                if st.button("🗑 Delete", key="delete_project"):
                    projects.delete(selected.id, owner_id)
                    if st.session_state.get("active_project_id") == selected.id:
                        st.session_state["active_project_id"] = None
                        st.session_state["result"] = None
                    st.toast("Workflow deleted", icon="🗑")
                    st.rerun()


# ---------------------------------------------------------------------------
# 5. Run — execution tracking and history
# ---------------------------------------------------------------------------

with run_tab:
    st.markdown(
        '<div class="awg-section-intro"><div><div class="awg-eyebrow">'
        '04 — PUT IT INTO PRACTICE</div><h2>Run the process</h2>'
        '<p>Track progress as work moves through each stage and keep a record of the run.</p>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    if not active_id:
        st.caption("Generate or load a workflow to track execution.")
    else:
        pid = active_id  # narrowed by the guard above
        current = projects.load(pid, owner_id)
        for step in current.workflow.steps:
            status_col, notes_col, update_col = st.columns([2, 3, 1])
            with status_col:
                chosen_status = st.selectbox(
                    f"Status — {step.title}",
                    _STATUSES,
                    index=_STATUSES.index(step.status.value),
                    key=f"status_{step.id}",
                    label_visibility="collapsed",
                )
            with notes_col:
                step_notes = st.text_input(
                    f"Notes — {step.title}",
                    value=step.notes,
                    key=f"notes_{step.id}",
                    label_visibility="collapsed",
                )
            with update_col:
                if st.button("Update", key=f"status_update_{step.id}") and apply_edit(
                    partial(
                        runs.set_step_status,
                        pid,
                        step.id,
                        StepStatus(chosen_status),
                        owner_id,
                        notes=step_notes,
                    )
                ):
                    st.toast("Status updated", icon="✅")
                    sync_active(pid, owner_id)
                    st.rerun()

        if st.button("🏁 Finish run", key="finish_run") and apply_edit(
            partial(runs.finish_run, pid, owner_id)
        ):
            st.toast("Run completed", icon="🏁")
            sync_active(pid, owner_id)
            st.rerun()

        history = runs.list_runs(pid, owner_id)
        if history:
            st.caption(f"Run history ({len(history)})")
            for run in history[:5]:
                st.caption(f"{run.id} · {run.outcome} · {len(run.transitions)} transition(s)")
        else:
            st.caption("No runs recorded yet.")


# ---------------------------------------------------------------------------
# 6. Analytics — provenance, quality and usage KPIs
# ---------------------------------------------------------------------------

with analytics_tab:
    st.markdown(
        '<div class="awg-section-intro"><div><div class="awg-eyebrow">'
        'OPERATIONS OVERVIEW</div><h2>Understand your workflows</h2>'
        '<p>See what has been created, how runs are progressing, and where generation effort goes.</p>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    saved_for_stats = projects.list_projects(owner_id)
    summary = summarize(saved_for_stats)

    st.markdown("#### At a glance")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4, border=True)
    with kpi1:
        st.metric("Workflows", summary.workflows)
    with kpi2:
        st.metric("Steps", summary.steps)
    with kpi3:
        st.metric("Runs", summary.runs)
    with kpi4:
        st.metric("Completed", summary.completed_runs)

    kpi5, kpi6, kpi7, kpi8 = st.columns(4, border=True)
    with kpi5:
        st.metric("Avg latency", f"{summary.avg_latency_ms:.0f} ms")
    with kpi6:
        st.metric("Fallback rate", f"{summary.fallback_rate:.0%}")
    with kpi7:
        st.metric("Est. cost", f"${summary.estimated_cost_usd:.4f}")
    with kpi8:
        st.metric("Tokens in / out", f"{summary.tokens_in:,} / {summary.tokens_out:,}")

    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.markdown("**Workflows by domain**")
        domain_data = domain_frame(saved_for_stats)
        if domain_data.empty:
            st.caption("No domain data yet.")
        else:
            st.bar_chart(domain_data.set_index("Domain"), alt="Workflow volume by domain")

        st.markdown("**Step types**")
        type_data = step_type_frame(saved_for_stats)
        if type_data.empty:
            st.caption("No step data yet.")
        else:
            st.bar_chart(type_data.set_index("Step type"), alt="Step type distribution")

    with chart_right:
        st.markdown("**Generation latency**")
        latency_data = latency_frame(saved_for_stats)
        if latency_data.empty:
            st.caption("No latency data yet.")
        else:
            st.bar_chart(latency_data.set_index("Workflow"), alt="Latency per workflow")

        st.markdown("**Providers**")
        provider_data = provider_frame(saved_for_stats)
        if provider_data.empty:
            st.caption("No provider data yet.")
        else:
            st.bar_chart(provider_data.set_index("Provider"), alt="Workflows by provider")

    st.markdown("**Step status distribution**")
    status_data = status_frame(saved_for_stats)
    if status_data.empty:
        st.caption("No status data yet.")
    else:
        st.dataframe(status_data, hide_index=True, width="stretch")

    st.markdown("**Recent runs**")
    st.dataframe(run_timeline_frame(saved_for_stats), hide_index=True, width="stretch")

st.caption("Built by Ganesh Basani — AI Workflow Automation Project")
