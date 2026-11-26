"""Gate tests for the published Phase 2 evaluation scorecard.

These assertions make the exit criteria executable: a regression in schema
enforcement, repair, domain preservation or structural integrity fails CI.
"""

from __future__ import annotations

import pytest

from tests.eval.eval_harness import EvalReport, run_eval
from tests.eval.golden_cases import GOLDEN_CASES


@pytest.fixture(scope="module")
def report() -> EvalReport:
    return run_eval()


def test_golden_set_has_25_cases() -> None:
    assert len(GOLDEN_CASES) == 25
    assert len({case.id for case in GOLDEN_CASES}) == 25
    assert len({case.expected_domain for case in GOLDEN_CASES}) == 6


def test_first_attempt_schema_validity_at_least_90_percent(report: EvalReport) -> None:
    assert report.first_attempt_validity >= 0.90


def test_final_schema_validity_is_100_percent(report: EvalReport) -> None:
    assert report.final_validity == 1.0


def test_domain_accuracy_at_least_90_percent(report: EvalReport) -> None:
    assert report.domain_accuracy >= 0.90


def test_structural_integrity_is_100_percent(report: EvalReport) -> None:
    assert report.structural_integrity == 1.0


def test_repair_cases_were_exercised(report: EvalReport) -> None:
    repaired = [o for o in report.outcomes if not o.first_attempt_valid]
    assert len(repaired) == 2
    assert all(o.final_valid for o in repaired)


def test_latency_and_cost_are_bounded(report: EvalReport) -> None:
    assert report.latency_p95_ms < 20_000
    assert report.total_cost_usd >= 0.0
