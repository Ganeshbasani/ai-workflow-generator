# ADR-003 — Pydantic models as the single source of truth

- Status: Accepted
- Date: 2026-01-20 (Phase 1)

## Context
The legacy engine passed `list[str]` between layers. Each consumer stripped a
`"Step N: "` prefix differently, exports disagreed, and there was no structure
for branches, provenance or execution state.

## Decision
Use Pydantic v2 models (`Workflow`, `WorkflowStep`, `Project`, `RunRecord`,
`GenerationResult`) everywhere. DAG validation is centralised in
`validate_workflow()`. Every exporter consumes a `Workflow` and emits bytes;
no consumer re-parses display text. API schemas are a transport-only boundary.

## Consequences
- One topological order drives cards, diagram, CSV, PDF, JSON, Markdown and Mermaid.
- Structural edits are re-validated before saving.
- JSON snapshots remain forward-compatible as optional fields are added.
