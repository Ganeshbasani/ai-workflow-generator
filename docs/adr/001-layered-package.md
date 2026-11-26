# ADR-001 — Layered `src/` package

- Status: Accepted
- Date: 2026-01-20 (Phase 1)

## Context
The original app was a Streamlit monolith: `app.py` called a single rule
function and re-parsed `"Step N: ..."` strings for every export. There was no
seam for tests, an API, persistence or an LLM.

## Decision
Move domain logic into `src/workflow_ai/` with explicit layers: `models`,
`providers`, `services`, `persistence`, `exporters`, `ingest`, `validation`,
`config` and (from Phase 5) `api`. `app.py` and `workflow.py` remain thin
compatibility entry points.

## Consequences
- UI, HTTP API and future clients reuse one service stack.
- Pure functions are unit-testable without Streamlit.
- A small amount of import-path plumbing is needed before an editable install;
  both entry points add `src/` to `sys.path`.
