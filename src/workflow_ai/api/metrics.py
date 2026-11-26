"""Small in-process metrics registry for the HTTP boundary.

This is deliberately dependency-free and process-local. A multi-instance
deployment can export the same snapshot to Prometheus/OTel without changing the
service layer.
"""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from typing import Any

from ..models import GenerationResult


class Metrics:
    """Thread-safe counters and bounded latency samples."""

    def __init__(self, *, sample_size: int = 500) -> None:
        self._lock = Lock()
        self._samples: deque[float] = deque(maxlen=sample_size)
        self._requests_total = 0
        self._by_status: dict[str, int] = defaultdict(int)
        self._by_endpoint: dict[str, int] = defaultdict(int)
        self._generation_total = 0
        self._generation_errors = 0
        self._fallback_total = 0
        self._tokens_in = 0
        self._tokens_out = 0
        self._cost_usd = 0.0

    def record_request(
        self, *, method: str, path: str, status: int, latency_ms: float
    ) -> None:
        """Record one completed HTTP request."""
        with self._lock:
            self._requests_total += 1
            self._by_status[str(status)] += 1
            self._by_endpoint[f"{method} {path}"] += 1
            self._samples.append(latency_ms)

    def record_generation(self, result: GenerationResult) -> None:
        """Record generation tokens, cost and fallback provenance."""
        with self._lock:
            self._generation_total += 1
            self._fallback_total += int(result.degraded)
            self._tokens_in += result.tokens_in
            self._tokens_out += result.tokens_out
            self._cost_usd += result.estimated_cost_usd

    def record_generation_error(self) -> None:
        """Record a generation that ended in a typed error."""
        with self._lock:
            self._generation_errors += 1

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot of all counters."""
        with self._lock:
            ordered = sorted(self._samples)
            count = len(ordered)
            avg = sum(ordered) / count if count else 0.0
            p95 = ordered[min(count - 1, int(count * 0.95))] if count else 0.0
            fallback_rate = (
                self._fallback_total / self._generation_total
                if self._generation_total
                else 0.0
            )
            return {
                "requests": {
                    "total": self._requests_total,
                    "by_status": dict(sorted(self._by_status.items())),
                    "by_endpoint": dict(sorted(self._by_endpoint.items())),
                    "avg_latency_ms": round(avg, 2),
                    "p95_latency_ms": round(p95, 2),
                },
                "generation": {
                    "total": self._generation_total,
                    "errors": self._generation_errors,
                    "fallbacks": self._fallback_total,
                    "fallback_rate": round(fallback_rate, 4),
                    "tokens_in": self._tokens_in,
                    "tokens_out": self._tokens_out,
                    "estimated_cost_usd": round(self._cost_usd, 6),
                },
            }
