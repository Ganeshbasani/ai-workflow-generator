"""Deterministic offline evaluation of the full LLM pipeline.

The harness drives a scripted OpenAI-compatible client through prompt building,
JSON parsing, schema validation, repair and fallback — no network or API key.
Each golden case carries its *expected* domain and structural properties; the
scripted client returns a well-formed payload matching that specification so
the metrics measure the engine's mechanics (schema enforcement, repair,
degradation and provenance) rather than any single provider's phrasing.
Replace the scripted client with a real one for a live quality run.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from time import perf_counter

from pydantic import ValidationError

from tests.eval.golden_cases import GOLDEN_CASES, REPAIR_CASE_IDS, GoldenCase
from tests.fakes import FakeClient, completion
from workflow_ai.config import Settings
from workflow_ai.errors import WorkflowError
from workflow_ai.limits import CostTracker, RateLimiter
from workflow_ai.models import GenerationRequest, Workflow
from workflow_ai.providers import LLMProvider, RuleProvider
from workflow_ai.services import GenerationService


@dataclass(frozen=True)
class CaseOutcome:
    case_id: str
    domain: str
    first_attempt_valid: bool
    final_valid: bool
    domain_correct: bool
    structurally_valid: bool
    fallback: bool
    latency_ms: float
    cost_usd: float


@dataclass(frozen=True)
class EvalReport:
    outcomes: tuple[CaseOutcome, ...]
    mode: str

    @property
    def total(self) -> int:
        return len(self.outcomes)

    @property
    def first_attempt_validity(self) -> float:
        return sum(o.first_attempt_valid for o in self.outcomes) / self.total

    @property
    def final_validity(self) -> float:
        return sum(o.final_valid for o in self.outcomes) / self.total

    @property
    def domain_accuracy(self) -> float:
        return sum(o.domain_correct for o in self.outcomes) / self.total

    @property
    def structural_integrity(self) -> float:
        return sum(o.structurally_valid for o in self.outcomes) / self.total

    @property
    def fallback_rate(self) -> float:
        return sum(o.fallback for o in self.outcomes) / self.total

    @property
    def latency_p50_ms(self) -> float:
        values = [o.latency_ms for o in self.outcomes]
        return statistics.median(values) if values else 0.0

    @property
    def latency_p95_ms(self) -> float:
        values = sorted(o.latency_ms for o in self.outcomes)
        if not values:
            return 0.0
        index = min(len(values) - 1, round((len(values) - 1) * 0.95))
        return values[index]

    @property
    def total_cost_usd(self) -> float:
        return sum(o.cost_usd for o in self.outcomes)


def _percent(value: float) -> str:
    return f"{value:.0%}"


# Plausible step titles per domain. The harness inserts as many as a case needs
# so structural integrity is judged against the specification, not the quirks
# of the offline rule engine's keyword matching.
_DOMAIN_STEP_TITLES: dict[str, tuple[str, ...]] = {
    "business": (
        "Review the customer request",
        "Process the transaction",
        "Generate the confirmation",
        "Notify the customer",
    ),
    "education": (
        "Review the application",
        "Verify the documents",
        "Enroll the student",
        "Publish the outcome",
    ),
    "hospital": (
        "Register the patient",
        "Record the clinical details",
        "Deliver the requested care",
        "Confirm the next steps",
    ),
    "real_estate": (
        "Capture the property details",
        "Coordinate the viewing",
        "Prepare the agreement",
        "Close the request",
    ),
    "software": (
        "Analyse the requirements",
        "Design the solution",
        "Implement the change",
        "Verify and release",
    ),
    "infrastructure": (
        "Validate the request",
        "Apply the infrastructure change",
        "Monitor the result",
        "Close the incident",
    ),
}


def _payload(case: GoldenCase) -> dict[str, object]:
    """Build the well-formed golden answer a correct provider should return."""
    titles = _DOMAIN_STEP_TITLES.get(case.expected_domain, ("Review", "Process", "Complete"))
    count = max(case.min_steps, 2)
    steps: list[dict[str, object]] = []
    for index in range(1, count + 1):
        title = titles[index - 1] if index <= len(titles) else f"Follow up on step {index}"
        step_type = "start" if index == 1 else ("end" if index == count else "task")
        steps.append(
            {
                "id": f"s{index}",
                "title": title,
                "step_type": step_type,
                "depends_on": [f"s{index - 1}"] if index > 1 else [],
                "owner_role": "coordinator",
            }
        )
    return {
        "title": f"{case.expected_domain.replace('_', ' ').title()} workflow",
        "domain": case.expected_domain,
        "summary": f"Workflow for: {case.description}",
        "steps": steps,
        "assumptions": [],
        "risks": [],
        "missing_information": [],
    }


def _first_attempt_probe(payload: dict[str, object], case: GoldenCase) -> dict[str, object]:
    """Return the raw first response; two cases are deliberately malformed."""
    probe = json.loads(json.dumps(payload))
    if case.id in REPAIR_CASE_IDS:
        steps = probe.get("steps")
        if isinstance(steps, list) and steps:
            steps[0]["step_type"] = "not_a_real_step_type"
    return probe


def run_case(case: GoldenCase, settings: Settings) -> CaseOutcome:
    """Run one golden case through prompt -> parse -> validate -> repair."""
    payload = _payload(case)
    first = _first_attempt_probe(payload, case)
    try:
        Workflow.model_validate(first)
        first_valid = True
    except ValidationError:
        first_valid = False

    responses = []
    if not first_valid:
        responses.append(completion(json.dumps(first)))
    responses.append(completion(json.dumps(payload)))

    client = FakeClient(responses)
    provider = LLMProvider(settings, api_key="eval-only", client=client)  # type: ignore[arg-type]
    service = GenerationService(
        provider,  # type: ignore[arg-type]
        settings,
        fallback=RuleProvider(settings),
        rate_limiter=RateLimiter(),
        cost_tracker=CostTracker(),
    )
    request = GenerationRequest(
        description=case.description,
        category=case.category,
        session_id=case.id,
    )

    started = perf_counter()
    try:
        result = service.generate(request)
        final_valid = True
        domain_correct = result.workflow.domain == case.expected_domain
        structurally_valid = len(result.workflow.steps) >= case.min_steps
        fallback = result.degraded
        cost = result.estimated_cost_usd
    except WorkflowError:
        final_valid = False
        domain_correct = False
        structurally_valid = False
        fallback = True
        cost = 0.0
    latency = (perf_counter() - started) * 1000

    return CaseOutcome(
        case_id=case.id,
        domain=case.expected_domain,
        first_attempt_valid=first_valid,
        final_valid=final_valid,
        domain_correct=domain_correct,
        structurally_valid=structurally_valid,
        fallback=fallback,
        latency_ms=latency,
        cost_usd=cost,
    )


def run_eval(
    cases: tuple[GoldenCase, ...] = GOLDEN_CASES,
    *,
    mode: str = "mocked OpenAI-compatible client",
) -> EvalReport:
    """Evaluate all cases with a deterministic, offline provider."""
    settings = Settings(retry_backoff_seconds=0.0, max_requests_per_session=10_000)
    return EvalReport(
        outcomes=tuple(run_case(case, settings) for case in cases),
        mode=mode,
    )


def render_scorecard(report: EvalReport) -> str:
    """Render a publishable Markdown scorecard."""
    rows = [
        ("Schema validity (first attempt)", _percent(report.first_attempt_validity), "≥ 90%"),
        ("Schema validity (after repair/fallback)", _percent(report.final_validity), "100%"),
        ("Domain accuracy", _percent(report.domain_accuracy), "≥ 90%"),
        ("Structural integrity", _percent(report.structural_integrity), "100%"),
        ("Fallback rate", _percent(report.fallback_rate), "report only"),
        ("Latency p50", f"{report.latency_p50_ms:.1f} ms", "report only"),
        ("Latency p95", f"{report.latency_p95_ms:.1f} ms", "< 20 s"),
        ("Estimated cost", f"${report.total_cost_usd:.6f}", "report only"),
    ]

    lines = [
        "# AI Engine Evaluation Scorecard",
        "",
        f"**Run mode:** {report.mode}  ",
        f"**Cases:** {report.total} (25 golden cases across 6 domains)",
        "",
        "| Metric | Result | Target |",
        "|---|---:|---|",
        *(f"| {name} | {value} | {target} |" for name, value, target in rows),
        "",
        "## Method",
        "",
        "Each case carries its expected domain and minimum step count. A golden",
        "payload is built from that specification and replayed by a scripted",
        "OpenAI-compatible client through the real prompt builder, JSON parser,",
        "Pydantic schema validation, bounded repair loop and rule fallback. Two",
        "cases deliberately return an invalid `step_type` on the first attempt to",
        "exercise repair; the corrected response is returned on the next attempt.",
        "",
        "Domain accuracy and structural integrity therefore measure whether the",
        "engine preserves a well-formed golden answer end to end; first-attempt",
        "schema validity measures the validation and repair mechanics directly.",
        "The scripted client makes the run deterministic, free and offline. For a",
        "live model-quality run, inject a real OpenAI-compatible client into",
        "`run_case` and set `LLM_API_KEY` / `LLM_BASE_URL`; the same metrics apply.",
        "",
        "## Per-case results",
        "",
        "| Case | Domain | First OK | Final OK | Domain OK | Fallback | Latency (ms) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for outcome in report.outcomes:
        lines.append(
            f"| {outcome.case_id} | {outcome.domain} | "
            f"{'✓' if outcome.first_attempt_valid else '✗'} | "
            f"{'✓' if outcome.final_valid else '✗'} | "
            f"{'✓' if outcome.domain_correct else '✗'} | "
            f"{'✓' if outcome.fallback else '—'} | {outcome.latency_ms:.1f} |"
        )
    lines.append("")
    return "\n".join(lines)
