# ADR-004 — Owner-scoped SQLite repository

- Status: Accepted
- Date: 2026-01-22 (Phase 3)

## Context
Saved workflows had to survive refresh and restart, and a future authenticated
deployment needed per-user isolation without rewriting callers.

## Decision
Define a `ProjectRepository` protocol whose every operation takes `owner_id`.
`SqliteProjectRepository` stores Pydantic JSON snapshots with idempotent
forward migrations and an in-process lock. `owner_id` is nullable: `None` is a
real scope matching only anonymous rows. The UI uses a URL session token; the
API exposes an `X-Owner-Id` seam for a future auth layer.

## Consequences
- Anonymous and authenticated scopes share one code path.
- SQLite is zero-ops for local/demo use; Postgres can implement the same protocol.
- The connection and lock are process-local, so multi-instance deployments need
  an external repository.
