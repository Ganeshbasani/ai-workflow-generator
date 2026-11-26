"""Pure tests for the analytics dashboard aggregations."""

from __future__ import annotations

from workflow_ai.models import (
    GenerationMetadata,
    Project,
    RunRecord,
    StepStatus,
    StepTransition,
    StepType,
    Workflow,
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


def _project(
    title: str,
    *,
    domain: str = "business",
    provider: str = "rule",
    latency_ms: float = 100.0,
    degraded: bool = False,
    runs: list[RunRecord] | None = None,
) -> Project:
    workflow = Workflow(
        title=title,
        domain=domain,
        steps=[
            WorkflowStep(id="s1", title="Start", step_type=StepType.start),
            WorkflowStep(
                id="s2",
                title="Review",
                step_type=StepType.approval,
                status=StepStatus.done,
            ),
        ],
    )
    return Project(
        workflow=workflow,
        metadata=GenerationMetadata(
            category=domain,
            prompt="describe",
            provider=provider,
            latency_ms=latency_ms,
            degraded=degraded,
            estimated_cost_usd=0.01,
            tokens_in=10,
            tokens_out=20,
        ),
        runs=runs or [],
    )


def test_summarize_empty() -> None:
    summary = summarize([])

    assert summary.workflows == 0
    assert summary.steps == 0
    assert summary.runs == 0
    assert summary.completed_runs == 0
    assert summary.avg_latency_ms == 0.0
    assert summary.fallback_rate == 0.0
    assert summary.estimated_cost_usd == 0.0


def test_summarize_aggregates_provenance_and_runs() -> None:
    runs = [
        RunRecord(
            project_id="p1",
            outcome="completed",
            transitions=[StepTransition(step_id="s1", status=StepStatus.done)],
        )
    ]
    projects = [
        _project("A", latency_ms=100, degraded=True, runs=runs),
        _project("B", domain="hospitals", provider="openai", latency_ms=300),
    ]

    summary = summarize(projects)

    assert summary.workflows == 2
    assert summary.steps == 4
    assert summary.runs == 1
    assert summary.completed_runs == 1
    assert summary.avg_latency_ms == 200.0
    assert summary.fallback_rate == 0.5
    assert summary.estimated_cost_usd == 0.02
    assert summary.tokens_in == 20
    assert summary.tokens_out == 40


def test_empty_frames_have_stable_columns() -> None:
    assert list(latency_frame([]).columns) == ["Workflow", "Latency (ms)"]
    assert list(provider_frame([]).columns) == ["Provider", "Workflows"]
    assert list(domain_frame([]).columns) == ["Domain", "Workflows"]
    assert list(step_type_frame([]).columns) == ["Step type", "Steps"]
    assert list(status_frame([]).columns) == ["Status", "Steps"]
    assert list(run_timeline_frame([]).columns) == ["Started", "Transitions", "Outcome"]


def test_count_frames_sort_by_frequency() -> None:
    projects = [
        _project("A", domain="business", provider="rule"),
        _project("B", domain="business", provider="rule"),
        _project("C", domain="hospitals", provider="openai"),
    ]

    domains = domain_frame(projects)
    providers = provider_frame(projects)

    assert domains.iloc[0].tolist() == ["business", 2]
    assert providers.iloc[0].tolist() == ["rule", 2]
    assert step_type_frame(projects)["Steps"].sum() == 6
    assert status_frame(projects)["Steps"].sum() == 6


def test_latency_and_timeline_frames() -> None:
    run = RunRecord(project_id="p", outcome="completed")
    projects = [_project("Slow", latency_ms=900), _project("Fast", latency_ms=10, runs=[run])]

    latency = latency_frame(projects)
    timeline = run_timeline_frame(projects)

    assert latency.iloc[0].tolist() == ["Slow", 900.0]
    assert latency.iloc[1].tolist() == ["Fast", 10.0]
    assert list(timeline.columns) == ["Started", "Transitions", "Outcome"]
    assert timeline.iloc[0]["Outcome"] == "completed"
