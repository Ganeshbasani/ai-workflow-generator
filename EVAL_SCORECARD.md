# AI Engine Evaluation Scorecard

**Run mode:** mocked OpenAI-compatible client
**Cases:** 25 (25 golden cases across 6 domains)

| Metric | Result | Target |
|---|---:|---|
| Schema validity (first attempt) | 92% | ≥ 90% |
| Schema validity (after repair/fallback) | 100% | 100% |
| Domain accuracy | 100% | ≥ 90% |
| Structural integrity | 100% | 100% |
| Fallback rate | 0% | report only |
| Latency p50 | 4.0 ms | report only |
| Latency p95 | 6.1 ms | < 20 s |
| Estimated cost | $0.001350 | report only |

## Method

Each case carries its expected domain and minimum step count. A golden
payload is built from that specification and replayed by a scripted
OpenAI-compatible client through the real prompt builder, JSON parser,
Pydantic schema validation, bounded repair loop and rule fallback. Two
cases deliberately return an invalid `step_type` on the first attempt to
exercise repair; the corrected response is returned on the next attempt.

Domain accuracy and structural integrity therefore measure whether the
engine preserves a well-formed golden answer end to end; first-attempt
schema validity measures the validation and repair mechanics directly.
The scripted client makes the run deterministic, free and offline. For a
live model-quality run, inject a real OpenAI-compatible client into
`run_case` and set `LLM_API_KEY` / `LLM_BASE_URL`; the same metrics apply.

## Per-case results

| Case | Domain | First OK | Final OK | Domain OK | Fallback | Latency (ms) |
|---|---|---:|---:|---:|---:|---:|
| g01 | business | ✓ | ✓ | ✓ | — | 6.1 |
| g02 | business | ✓ | ✓ | ✓ | — | 4.3 |
| g03 | business | ✓ | ✓ | ✓ | — | 4.2 |
| g04 | business | ✗ | ✓ | ✓ | — | 4.2 |
| g05 | business | ✓ | ✓ | ✓ | — | 4.8 |
| g06 | business | ✓ | ✓ | ✓ | — | 3.7 |
| g07 | education | ✓ | ✓ | ✓ | — | 4.0 |
| g08 | education | ✓ | ✓ | ✓ | — | 4.5 |
| g09 | education | ✓ | ✓ | ✓ | — | 8.3 |
| g10 | education | ✓ | ✓ | ✓ | — | 4.5 |
| g11 | education | ✓ | ✓ | ✓ | — | 4.1 |
| g12 | hospital | ✓ | ✓ | ✓ | — | 3.9 |
| g13 | hospital | ✓ | ✓ | ✓ | — | 4.4 |
| g14 | hospital | ✓ | ✓ | ✓ | — | 4.1 |
| g15 | hospital | ✓ | ✓ | ✓ | — | 3.4 |
| g16 | hospital | ✓ | ✓ | ✓ | — | 3.4 |
| g17 | real_estate | ✗ | ✓ | ✓ | — | 3.8 |
| g18 | real_estate | ✓ | ✓ | ✓ | — | 3.7 |
| g19 | real_estate | ✓ | ✓ | ✓ | — | 3.6 |
| g20 | real_estate | ✓ | ✓ | ✓ | — | 3.4 |
| g21 | software | ✓ | ✓ | ✓ | — | 3.4 |
| g22 | software | ✓ | ✓ | ✓ | — | 3.9 |
| g23 | software | ✓ | ✓ | ✓ | — | 4.1 |
| g24 | infrastructure | ✓ | ✓ | ✓ | — | 3.8 |
| g25 | infrastructure | ✓ | ✓ | ✓ | — | 4.0 |
