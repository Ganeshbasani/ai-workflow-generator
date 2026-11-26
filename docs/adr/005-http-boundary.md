# ADR-005 — HTTP boundary over the same services

- Status: Accepted
- Date: 2026-11-20 (Phase 5)

## Context
The app needed a backend signal for interviews and programmatic access without
forking business logic or creating a second source of truth.

## Decision
Add a FastAPI application under `src/workflow_ai/api/` with `/api/v1` routes,
typed request/response schemas, injectable services and OpenAPI docs. Middleware
adds `X-Request-ID`, validates the optional `X-Owner-Id` scope, enforces a
request-size limit and records latency/status metrics. A single error envelope
maps the typed exception hierarchy to user-safe messages (422/402/413/429/502/500).

## Consequences
- `uvicorn api:app` and `streamlit run app.py` call identical services.
- Contract tests exercise the boundary with no network or API key.
- Metrics are in-process; a multi-instance deployment should export the same
  snapshot to OpenTelemetry/Prometheus.
