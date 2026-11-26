# ADR-002 — Provider protocol with an honest degradation ladder

- Status: Accepted
- Date: 2026-01-21 (Phase 2)

## Context
LLM calls can fail (timeouts, quota, auth, malformed JSON) and the app must
still work offline, with no key and no cost. Claiming "AI" when rules generated
the result would be misleading.

## Decision
Define a `WorkflowProvider` protocol. `LLMProvider` uses JSON Schema, Pydantic
validation and a bounded repair loop; `RuleProvider` is the deterministic
fallback. `GenerationService` owns the ladder:
rate/cost check → LLM → validate → repair → rules → typed error. Every result
records `provider`, `degraded`, `fallback_reason` and token/cost metadata, and
the UI displays `⚡ AI` or `🛠 Offline (rule-based)` truthfully.

## Consequences
- New providers (Ollama, Groq, etc.) only implement the protocol.
- No single provider can take the app offline.
- Users see why a result came from rules; logs never contain user text.
