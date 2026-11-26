"""Unit tests for abuse controls and cost estimation."""

from __future__ import annotations

import pytest

from workflow_ai.errors import CostCeilingError, RateLimitError
from workflow_ai.limits import (
    CostTracker,
    RateLimiter,
    estimate_cost_usd,
    estimate_tokens,
)


def test_estimate_tokens() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_cost_table_and_free_local_models() -> None:
    paid = estimate_cost_usd("gpt-4o-mini", 1_000_000, 1_000_000)
    assert paid == pytest.approx(0.75)
    assert estimate_cost_usd("llama3.1", 1_000_000, 1_000_000) == 0.0
    assert estimate_cost_usd(None, 0, 0) == 0.0


def test_rate_limiter_enforces_window() -> None:
    limiter = RateLimiter()
    for _ in range(3):
        limiter.check("session-a", max_requests=3, window_seconds=60)
    with pytest.raises(RateLimitError):
        limiter.check("session-a", max_requests=3, window_seconds=60)

    limiter.check("session-b", max_requests=1, window_seconds=60)
    limiter.reset()
    limiter.check("session-a", max_requests=1, window_seconds=60)


def test_rate_limiter_sliding_window_expires_events() -> None:
    limiter = RateLimiter()
    limiter.check("s", max_requests=1, window_seconds=0)
    limiter.check("s", max_requests=1, window_seconds=0)


def test_cost_tracker_ceiling() -> None:
    tracker = CostTracker()
    tracker.check(1.0)
    tracker.record(0.6)
    assert tracker.spent_today() == pytest.approx(0.6)
    tracker.check(1.0)
    tracker.record(0.4)
    with pytest.raises(CostCeilingError):
        tracker.check(1.0)

    tracker.reset()
    tracker.check(1.0)
