"""Regenerate the published evaluation scorecard.

Usage (from the repository root)::

    python -m tests.eval.run_eval

This runs the deterministic, offline harness and writes ``EVAL_SCORECARD.md``
at the repository root. No API key, network access or cost is involved.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tests.eval.eval_harness import render_scorecard, run_eval

SCORECARD_PATH = _ROOT / "EVAL_SCORECARD.md"


def main() -> None:
    report = run_eval()
    scorecard = render_scorecard(report)
    SCORECARD_PATH.write_text(scorecard, encoding="utf-8")

    print(f"Wrote {SCORECARD_PATH}")
    print(f"  cases={report.total}")
    print(f"  first-attempt validity={report.first_attempt_validity:.0%}")
    print(f"  final validity={report.final_validity:.0%}")
    print(f"  domain accuracy={report.domain_accuracy:.0%}")
    print(f"  structural integrity={report.structural_integrity:.0%}")
    print(f"  fallback rate={report.fallback_rate:.0%}")
    print(f"  latency p50={report.latency_p50_ms:.1f} ms  p95={report.latency_p95_ms:.1f} ms")
    print(f"  estimated cost=${report.total_cost_usd:.6f}")


if __name__ == "__main__":
    main()
