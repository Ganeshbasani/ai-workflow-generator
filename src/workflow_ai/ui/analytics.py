"""Pure aggregations that power the analytics dashboard.

These functions only read domain models and return pandas DataFrames, which
keeps them cheap to unit-test and independent of Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..models import Project


@dataclass(frozen=True)
class AnalyticsSummary:
    """Headline numbers shown as KPI cards."""

    workflows: int
    steps: int
    runs: int
    completed_runs: int
    avg_latency_ms: float
    fallback_rate: float
    estimated_cost_usd: float
    tokens_in: int
    tokens_out: int


def summarize(projects: list[Project]) -> AnalyticsSummary:
    """Aggregate generation provenance and run history across projects."""
    metas = [project.metadata for project in projects if project.metadata is not None]
    runs = [run for project in projects for run in project.runs]
    degraded = sum(1 for meta in metas if meta.degraded)
    return AnalyticsSummary(
        workflows=len(projects),
        steps=sum(len(project.workflow.steps) for project in projects),
        runs=len(runs),
        completed_runs=sum(1 for run in runs if run.outcome == "completed"),
        avg_latency_ms=(
            sum(meta.latency_ms for meta in metas) / len(metas) if metas else 0.0
        ),
        fallback_rate=(degraded / len(metas)) if metas else 0.0,
        estimated_cost_usd=sum(meta.estimated_cost_usd for meta in metas),
        tokens_in=sum(meta.tokens_in for meta in metas),
        tokens_out=sum(meta.tokens_out for meta in metas),
    )


def _counts(values: list[str], label: str, value: str) -> pd.DataFrame:
    frame = pd.DataFrame({label: values})
    if frame.empty:
        return pd.DataFrame(columns=[label, value])
    return (
        frame.groupby(label, dropna=False)
        .size()
        .reset_index(name=value)
        .sort_values(value, ascending=False)
    )


def latency_frame(projects: list[Project]) -> pd.DataFrame:
    """Generation latency per workflow, slowest first."""
    rows = [
        {
            "Workflow": project.display_title,
            "Latency (ms)": round(project.metadata.latency_ms, 1)
            if project.metadata
            else 0.0,
        }
        for project in projects
    ]
    if not rows:
        return pd.DataFrame(columns=["Workflow", "Latency (ms)"])
    return pd.DataFrame(rows).sort_values("Latency (ms)", ascending=False).head(12)


def provider_frame(projects: list[Project]) -> pd.DataFrame:
    """How many workflows each provider produced."""
    values = [
        project.metadata.provider if project.metadata else "rule"
        for project in projects
    ]
    return _counts(values, "Provider", "Workflows")


def domain_frame(projects: list[Project]) -> pd.DataFrame:
    """Workflow volume by industry/domain."""
    values = [project.workflow.domain or "unspecified" for project in projects]
    return _counts(values, "Domain", "Workflows")


def step_type_frame(projects: list[Project]) -> pd.DataFrame:
    """Distribution of semantic step kinds across all saved workflows."""
    values = [
        step.step_type.value
        for project in projects
        for step in project.workflow.steps
    ]
    return _counts(values, "Step type", "Steps")


def status_frame(projects: list[Project]) -> pd.DataFrame:
    """Current execution status across all saved steps."""
    values = [
        step.status.value
        for project in projects
        for step in project.workflow.steps
    ]
    return _counts(values, "Status", "Steps")


def run_timeline_frame(projects: list[Project]) -> pd.DataFrame:
    """Recorded runs with their transition counts, newest first."""
    rows = [
        {
            "Started": run.started_at.strftime("%Y-%m-%d %H:%M"),
            "Transitions": len(run.transitions),
            "Outcome": run.outcome,
        }
        for project in projects
        for run in project.runs
    ]
    if not rows:
        return pd.DataFrame(columns=["Started", "Transitions", "Outcome"])
    return pd.DataFrame(rows).sort_values("Started", ascending=False).head(12)


__all__ = [
    "AnalyticsSummary",
    "domain_frame",
    "latency_frame",
    "provider_frame",
    "run_timeline_frame",
    "status_frame",
    "step_type_frame",
    "summarize",
]
