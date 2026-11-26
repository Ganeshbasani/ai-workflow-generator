"""In-process abuse controls: per-session rate limiting and a daily cost cap.

These are deliberately simple and dependency-free. A multi-instance deployment
would swap them for Redis / a metering service behind the same interface.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime
from threading import Lock
from time import monotonic

from .errors import CostCeilingError, RateLimitError

# USD per 1M tokens (input, output). Override by adding a model key.
_MODEL_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-3.5-turbo": (0.50, 1.50),
}

_FREE_MODEL_HINTS = ("ollama", "llama", "mistral", "qwen", "phi", "gemma")


def estimate_tokens(text: str) -> int:
    """Cheap token approximation used for budgeting and cost estimates."""
    return max(1, (len(text) + 3) // 4)


def estimate_cost_usd(model: str | None, tokens_in: int, tokens_out: int) -> float:
    """Estimate spend for one completion using a small, explicit price table."""
    name = (model or "").lower()
    if any(hint in name for hint in _FREE_MODEL_HINTS):
        return 0.0
    price_in, price_out = _MODEL_PRICES.get(name, (1.0, 3.0))
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


class RateLimiter:
    """Sliding-window request counter keyed by session id."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, session_id: str, max_requests: int, window_seconds: int) -> None:
        """Raise :class:`RateLimitError` when the window is exhausted."""
        now = monotonic()
        with self._lock:
            events = self._events[session_id]
            deadline = now - window_seconds
            while events and events[0] <= deadline:
                events.popleft()
            if len(events) >= max_requests:
                raise RateLimitError()
            events.append(now)

    def reset(self) -> None:
        """Clear all counters (used by tests and long-lived servers)."""
        with self._lock:
            self._events.clear()


class CostTracker:
    """Per-day spend counter with a hard ceiling."""

    def __init__(self) -> None:
        self._spend: dict[str, float] = defaultdict(float)
        self._lock = Lock()

    @staticmethod
    def _today() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def check(self, ceiling_usd: float) -> None:
        """Raise :class:`CostCeilingError` if today's ceiling is already met."""
        with self._lock:
            if self._spend[self._today()] >= ceiling_usd:
                raise CostCeilingError()

    def record(self, amount_usd: float) -> None:
        """Account for a completed request."""
        if amount_usd <= 0:
            return
        with self._lock:
            self._spend[self._today()] += amount_usd

    def spent_today(self) -> float:
        """Return today's recorded spend."""
        with self._lock:
            return self._spend[self._today()]

    def reset(self) -> None:
        """Clear all counters (used by tests)."""
        with self._lock:
            self._spend.clear()
