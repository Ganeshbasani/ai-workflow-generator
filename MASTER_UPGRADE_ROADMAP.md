# 🗺️ MASTER UPGRADE ROADMAP

**Project:** AI Workflow Generator → production-quality, interview-ready AI application
**Status:** All phases 0–6 complete. Production hardening and the fresh UI refresh are finished and verified; changes remain uncommitted and unpushed.
**Date:** 2026-01-19 (plan) · 2026-11-21 (final verification + UI refresh)
**Companion docs:** `AUDIT_REPORT.md` · `CURRENT_ARCHITECTURE.md` · `AI_WORKFLOW_ENGINE_ANALYSIS.md` · `SECURITY_AND_TESTING_REPORT.md` · `PRODUCTION_READINESS_REPORT.md`

---

## 1. Guiding Principles

1. ~~**Preserve the visual identity.** Same colors, Inter typography, card style and hero — no redesign.~~ **Superseded:** the UI refresh in Phase 6 replaced the original dark shell with a fresh light/dark tabbed theme at the user's explicit request. The service layer, entry points and domain logic were deliberately left untouched.
2. **Structure before intelligence.** An LLM needs a schema to land in. Build the data model first.
3. **Repurpose, don't discard.** `workflow.py` becomes the deterministic fallback provider.
4. **Test before you refactor.** Regression tests encode the audit findings and become the safety net.
5. **Every phase is independently demo-able.** No long stretches of invisible work.
6. **No feature theater.** Each feature must solve a real problem or it doesn't ship.
7. **Honesty as a feature.** Surface uncertainty (`assumptions`, `missing_information`, "Offline mode") instead of fabricating confidence.

---

## 2. Phase Overview

| Phase | Name | Complexity | Effort | Risk | Deliverable you can demo |
|---:|---|---|---|---|---|
| 0 | Stabilize | 🟢 Low | 1–2 d | Low | "The bugs from the audit are fixed" |
| 1 | Foundation | 🟡 Medium | 3–5 d | Medium | "Structured workflows + tests, offline" |
| 2 | AI Engine | 🟡 Medium | 4–6 d | Medium-High | "Real LLM generation with guaranteed schema + fallback" |
| 3 | Persistence & Control | 🟡 Medium | 4–6 d | Medium | "History, editing, execution tracking" |
| 4 | Visualization & Output | 🟡 Medium | 3–5 d | Low | "Live DAG diagram, 5 exports, AI explanations" |
| 5 | Production Hardening | 🔴 Med-High | 4–6 d | Medium | "FastAPI, CI/CD, Docker, observability" ✅ complete |
| 6 | UI Refresh | 🟡 Medium | 3–4 d | Medium | "Fresh light/dark tabs, inline editor, command palette, analytics" ✅ complete |
| | **Total** | | **22–34 d** | | |

**Complexity legend:** 🟢 Low (localized, low ambiguity) · 🟡 Medium (cross-cutting, some design decisions) · 🔴 Medium-High (multiple subsystems, integration risk)

---

## PHASE 0 — STABILIZE 🟢
*Goal: eliminate the critical defects so new work builds on solid ground.*
**Effort: 1–2 days · Complexity: Low · Risk: Low**

### Tasks
| # | Task | Addresses | Effort |
|---:|---|---|---|
| 0.1 | Pass `category` / `context` / `file_text` as **separate arguments** instead of one formatted f-string | C-01, C-02 | S |
| 0.2 | Stop the fallback from echoing UI-injected labels; echo only genuine user text | C-02 | S |
| 0.3 | Bundle a Unicode TTF (DejaVuSans) for `fpdf2`; replace deprecated `Arial`/`txt`/`ln` | C-03, C-10 | S |
| 0.4 | Generate exports **on click only**, not on every rerun | C-12 | S |
| 0.5 | `html.escape()` all user-derived text before HTML interpolation | **S-01** | S |
| 0.6 | Pin all dependencies; replace `pandas` with stdlib `csv` | C-10, §5.3 | S |
| 0.7 | Add `.gitignore`, `.env.example`, `LICENSE` (MIT, matching the README badge) | S-04 | S |
| 0.8 | Remove CORS/XSRF-disabling flags from the devcontainer (or gate behind an env var) | S-03 | S |
| 0.9 | Cap input length (4,000 chars) and upload size (5 MB) with friendly messages | S-05, S-02 | S |
| 0.10 | Add file-size/page cap + magic-byte MIME check + `extract_text() or ""` guard | S-02, C-15 | S |
| 0.11 | Write **9 regression tests** encoding the audit findings | all | M |
| 0.12 | Correct README example output + project structure; add a "Known limitations" section | §5.5 | S |
| 0.13 | Remove dead code: `index.html`, `style.css`, `assets` (**approved; completed**) | §2.3 | S |

### Exit criteria
- [ ] All 9 regression tests pass
- [ ] Typing an em-dash no longer crashes PDF export
- [ ] Domain dropdown demonstrably affects output
- [ ] No `Category:` string can appear in rendered output
- [ ] `git status` clean; deps pinned; CI not yet required

---

## PHASE 1 — FOUNDATION 🟡
*Goal: introduce structure — a real data model, package layout, and a rehabilitated offline engine.*
**Effort: 3–5 days · Complexity: Medium · Risk: Medium (touches everything)**

### Target structure
```
ai-workflow-generator/
├── app.py                     # thin Streamlit entrypoint (keeps visual identity)
├── src/workflow_ai/
│   ├── __init__.py
│   ├── models/                # Pydantic: Workflow, WorkflowStep, StepType, GenerationRequest
│   ├── providers/             # WorkflowProvider protocol, RuleProvider, LLMProvider (stub in P1)
│   ├── services/              # GenerationService, ExportService, ProjectService
│   ├── exporters/             # json, csv, pdf, markdown, mermaid (pure functions of the model)
│   ├── ingest/                # document parsing (PDF/TXT), sanitization, limits
│   ├── config.py              # pydantic-settings
│   └── logging.py             # structured logging setup
├── tests/
│   ├── unit/  integration/  ui/  fixtures/
├── requirements.txt  requirements-dev.txt  pyproject.toml
├── .env.example  .gitignore  LICENSE
└── .github/workflows/ci.yml
```

### Tasks
| # | Task | Notes |
|---:|---|---|
| 1.1 | Create `src/` package + `pyproject.toml`; `app.py` becomes a thin shell | Keeps `streamlit run app.py` working |
| 1.2 | Define Pydantic models: `Workflow`, `WorkflowStep` (`id`, `title`, `description`, `step_type`, `owner_role`, `depends_on`, `condition`, `on_true`, `on_false`, `estimated_duration`, `system_hint`), `Workflow` (`title`, `domain`, `summary`, `steps`, `assumptions`, `risks`, `missing_information`) | **Load-bearing change** |
| 1.3 | Introduce `WorkflowProvider` protocol (`generate(request) -> Workflow`) | Enables swapping/fallback |
| 1.4 | Rebuild `workflow.py` as **`RuleProvider`**: word-boundary regex, single-domain isolation via a scoring function, sentence-order output, per-context dedup, real `category` argument, basic stemming, returns `Workflow` (not `list[str]`) | Fixes C-01, C-04, C-05, C-06, C-07, C-08 |
| 1.5 | Extract exporters to pure functions operating on `Workflow` | Fixes C-11 (consistent outputs) |
| 1.6 | Extract document ingest with explicit limits and typed errors | Fixes C-15, S-02 |
| 1.7 | `GenerationService` orchestrating provider → validation → result | Single entry point for UI *and* future API |
| 1.8 | `pydantic-settings` config (model, limits, timeouts, feature flags) | |
| 1.9 | Structured logging (JSON, request IDs, **no PII/secrets**) | |
| 1.10 | Test suite to ≥70% coverage: unit + integration + `AppTest` UI tests | |
| 1.11 | `ruff` + `mypy --strict` clean | |
| 1.12 | **Preserve the UI verbatim** — only swap `list[str]` rendering for `Workflow` rendering | Design unchanged |

### Exit criteria
- [ ] `Workflow` is the single source of truth; no `"Step N: "` strings anywhere
- [ ] `RuleProvider` passes all Phase-0 regression tests **and** the new domain-isolation tests
- [ ] Category selection changes output, verifiably
- [ ] UI looks pixel-identical to today
- [ ] Coverage ≥70%, ruff + mypy green

---

## PHASE 2 — AI ENGINE 🟡
*Goal: genuine LLM-powered generation with guaranteed structure and reliable degradation.*
**Effort: 4–6 days · Complexity: Medium · Risk: Medium-High (external dependency)**

### Tasks
| # | Task | Notes |
|---:|---|---|
| 2.1 | `LLMProvider` implementing `WorkflowProvider` via the **`openai` SDK** against an OpenAI-compatible endpoint | Works with OpenAI, Groq, OpenRouter, **Ollama** |
| 2.2 | System prompt with **embedded JSON Schema**; JSON-mode/structured-output requested | Schema-constrained decoding |
| 2.3 | **Validation → repair → retry** loop (max 2) using Pydantic errors fed back to the model | Core reliability mechanism |
| 2.4 | **Degradation ladder:** `LLM → repair → RuleProvider → typed, user-safe error` | Never a raw traceback |
| 2.5 | Timeout (20 s), retries with backoff, error taxonomy (timeout / quota / auth / invalid) | |
| 2.6 | Input sanitization + **prompt-injection hardening**: delimit untrusted doc content, state it is data not instructions | |
| 2.7 | Length caps + token budget + per-session rate limit + daily cost ceiling | S-05, S-08 |
| 2.8 | `st.secrets` → env var → clear message; **never** hardcoded; `.env.example` committed | S-04 |
| 2.9 | **Evaluation harness** — `tests/eval/` golden set (25 cases), scorecard: schema validity, domain accuracy, structural integrity, latency p50/p95, cost, fallback rate | **Key differentiator** |
| 2.10 | Offline demo mode via Ollama; UI badge: `⚡ AI` vs `🛠 Offline (rule-based)` | Honest degradation |
| 2.11 | Cost/latency metrics emitted to logs | |
| 2.12 | Mocked-provider unit tests (no network, no cost, deterministic) | |

### Exit criteria
- [ ] ≥90% schema validity on first attempt across the golden set; 100% after repair or fallback
- [ ] App fully functional with **no API key** (rule fallback)
- [ ] Prompt-injection test passes
- [ ] All degradation paths covered by tests
- [ ] Published eval scorecard

---

## PHASE 3 — PERSISTENCE & CONTROL 🟡
*Goal: make workflows durable, editable, and trackable.*
**Effort: 4–6 days · Complexity: Medium · Risk: Medium**

### Tasks
| # | Task | Notes |
|---:|---|---|
| 3.1 | SQLite persistence + `ProjectRepository` interface (nullable `owner_id` for future auth) | Swappable later |
| 3.2 | Save / list / load / rename / delete workflows; **session-scoped anonymous history** | Refresh no longer loses work |
| 3.3 | Store generation metadata: category, prompt, provider, model, tokens, latency, timestamp | Provenance |
| 3.4 | Workflow **editor**: add / edit / delete / reorder steps; set `depends_on`; toggle branch conditions | Turns it into a real tool |
| 3.5 | Schema re-validation on every edit (reject dangling `depends_on`, cycles) | |
| 3.6 | **Execution tracking**: per-step status (`pending / in_progress / done / blocked / skipped`) + notes | |
| 3.7 | Run history per workflow (who/when/outcome) | |
| 3.8 | Optimistic UI updates; clear empty/loading/error states | |
| 3.9 | Repository + service tests, incl. round-trip equality and migration | |
| 3.10 | Optional: `st.cache_data` for repeat generations | Cost saving |

### Exit criteria
- [ ] History survives refresh and restart
- [ ] Editing preserves schema validity
- [ ] Status transitions persist and are visible
- [ ] Round-trip tests green; coverage ≥85%

---

## PHASE 4 — VISUALIZATION & OUTPUT 🟡
*Goal: make the workflow tangible, portable, and explainable.*
**Effort: 3–5 days · Complexity: Medium · Risk: Low**

### Tasks
| # | Task | Notes |
|---:|---|---|
| 4.1 | **Mermaid flowchart** rendered via `st.components.v1.html`, styled to match the existing dark/indigo theme | Zero install; preserves design |
| 4.2 | Decision branches rendered as diamond nodes with `on_true`/`on_false` labels | |
| 4.3 | Optional Graphviz backend for large DAGs (better auto-layout) | Pluggable |
| 4.4 | Topological ordering for correct linear display (replaces fragile rule-block order) | |
| 4.5 | **JSON export** — the structured model, round-trippable | Interop |
| 4.6 | **CSV export** — normalized columns (`step_id, title, type, owner, depends_on, condition, status`); fix prefix inconsistency | Fixes C-11 |
| 4.7 | **PDF export** — Unicode-safe, includes title, summary, diagram image, steps table, assumptions/risks | Fixes C-03 |
| 4.8 | **Markdown export** + **Mermaid source export** | |
| 4.9 | CSV formula-injection escaping | S-09 |
| 4.10 | **AI explanations**: per-step rationale, `assumptions`, `risks`, `missing_information`, suggested improvements | Surfaces reasoning |
| 4.11 | Exporter test matrix incl. emoji / `—` / CJK / RTL content | Regression for C-03 |
| 4.12 | **UI polish (no redesign):** responsive media queries for the 56px hero, ARIA labels, visible focus states, semantic markup, reduced `!important`, better empty/loading states | Accessibility |

### Exit criteria
- [x] Diagram renders with branches and matches the app's visual language
- [x] All 5 exports work and are mutually consistent
- [x] Full Unicode passes in every export
- [x] Lighthouse/accessibility basics pass; no horizontal overflow on mobile

---

## PHASE 5 — PRODUCTION HARDENING ✅
*Goal: operate it like a real service.*
**Effort: 4–6 days · Complexity: Medium-High · Risk: Medium · Status: complete (5A + 5B)**

### Tasks
| # | Task | Notes |
|---:|---|---|
| 5.1 | **FastAPI** layer wrapping the *same* services (generate, list, get, update, export) + OpenAPI docs | ✅ Phase 5A complete |
| 5.2 | API contract tests; versioned routes (`/api/v1`) | ✅ 18 contract tests |
| 5.3 | Rate limiting, request-size limits, auth-ready middleware | ✅ `X-Owner-Id` seam + size guard; service rate/cost limits reused |
| 5.4 | Structured logging + request IDs + metrics (latency, tokens, cost, fallback rate) | ✅ `X-Request-ID` + `/api/v1/metrics` |
| 5.5 | Typed exception taxonomy → boundary mapping → user-safe messages | ✅ single error envelope; 422/402/413/429/502/500 mapping |
| 5.6 | **Multi-stage `Dockerfile`** (non-root, healthcheck) + `docker-compose` for local | ✅ image built; `/health`, `/ready`, OpenAPI verified; UID 10001 |
| 5.7 | **GitHub Actions CI:** gitleaks → ruff → mypy → pytest (≥85%) → pip-audit; deploy on tag | ✅ `.github/workflows/ci.yml`; clean-clone image job + GHCR on `v*` |
| 5.8 | `pre-commit` hooks | ✅ whitespace/YAML/TOML/private keys + ruff + mypy + pytest |
| 5.9 | Health/readiness endpoints; graceful shutdown | ✅ `/health`, `/ready`; `docker stop` exit 0 with 10 s drain |
| 5.10 | `Makefile` / one-command dev setup (`make dev`, `make test`, `make eval`) | ✅ `make dev/check/docker/docker-ui/clean` |
| 5.11 | Architecture Decision Records (5 key decisions) | ✅ `docs/adr/` 001–005 + index |
| 5.12 | Final README rewrite with verified example, architecture diagram, honest limitations, demo GIF | ✅ Mermaid architecture, verified API output, domain-effect proof, limitations, `docs/demo.gif` from the real UI + live demo link |
| 5.13 | *(Optional, only if multi-user arrives)* OAuth + roles | Deferred by design |

### Exit criteria
- [x] `docker run` works from a clean clone *(image built and probed locally; CI repeat job added)*
- [x] CI green on every PR; coverage gate enforced *(same commands verified locally; 96% ≥ 85%)*
- [x] No secrets in logs; no deprecated APIs; no unpinned deps *(patched `pypdf` pin; `-W error::DeprecationWarning`)*
- [x] API documented and contract-tested *(OpenAPI + 18 contract tests)*
- [x] Full audit re-run shows **zero 🔴/🟠 findings** *(see `AUDIT_RERUN.md`)*

**Phase 5 status:** all tasks 5.1–5.12 are complete. Phase 5A delivered the
versioned API with typed contracts, DI, request IDs, size guard, metrics and a
single error envelope. Phase 5B delivered the non-root multi-stage image,
Compose profile, CI/CD with tag deploy, pre-commit hooks, Makefile, five ADRs,
the final README and the audit re-run. Task 5.13 (OAuth + roles) is
intentionally deferred until a real multi-user deployment exists.

---

## PHASE 6 — UI REFRESH ✅
*Goal: replace the original dark shell with a fresh, production-quality UI without touching the service stack.*
**Effort: 3–4 days · Complexity: Medium · Risk: Medium · Status: complete**

This phase supersedes the original "no redesign" principle at the user's explicit
request. `app.py`, `api.py` and `workflow.py` remain the three entry points; all
domain logic is still in `src/workflow_ai`. The UI is a thin orchestration layer
over the same services.

### Tasks
| # | Task | Notes |
|---:|---|---|
| 6.1 | `.streamlit/config.toml` with dual `[theme.light]` / `[theme.dark]` palettes, Inter font, radii, chart/dataframe colors | ✅ Native appearance toggle + shareable in-app control |
| 6.2 | Six native `st.tabs`: Generate, Workflow, Editor, Library, Run, Analytics | ✅ Compatibility keys/elements preserved for legacy AppTest |
| 6.3 | `st.status`, `st.toast`, `st.badge`, `st.metric` and charts | ✅ Loading/success/failure states and KPI dashboard |
| 6.4 | Theme + density segmented controls with `bind="query-params"` / `persist_state="session"` and runtime CSS tokens | ✅ `src/workflow_ai/ui/theme.py` |
| 6.5 | Themed diagram palettes; default dark preserved for existing assertions | ✅ `DiagramPalette`, SVG + Mermaid `theme` kwarg |
| 6.6 | Inline `st.data_editor` with validated DataFrame↔workflow bridge | ✅ `src/workflow_ai/ui/editor.py`, re-validates every save |
| 6.7 | CCv2 drag-and-drop step list with Alt+arrow and up/down button fallbacks | ✅ `src/workflow_ai/ui/components.py` (no `components.v1`) |
| 6.8 | CCv2 command palette with Ctrl/Cmd+K and Ctrl/Cmd+Enter | ✅ Shadow-DOM isolated, all dynamic text via `textContent` |
| 6.9 | Analytics aggregations: domain/provider/status counts, latency, runs, tokens/cost | ✅ `src/workflow_ai/ui/analytics.py` |
| 6.10 | Tests: AppTest redesign flows, pure UI tests, and `node --check` JS syntax gates | ✅ Browser-only CCv2 failures are now caught |
| 6.11 | Regenerate `docs/demo.gif` from the real redesigned app | ✅ Seven real headless-Chrome scenes, no fabricated frames |

### Exit criteria
- [x] `streamlit run app.py` still works; API and service stack unchanged
- [x] Domain selection still genuinely affects output (legacy regression tests pass)
- [x] No deprecated APIs, no unpinned deps (`pandas==3.1.1` pinned), no secrets in logs
- [x] Real-browser check: palette, theme/density toggles, keyboard reorder and analytics all work
- [x] 216 tests, 96% coverage (≥ 85% gate), ruff and strict mypy clean
- [x] Demo GIF captured from the redesigned UI

**Phase 6 status:** complete. The full suite is 216 tests at 96% coverage with
ruff, strict mypy and pre-commit clean. The only deliberate deferral remains
task 5.13 (OAuth + roles).

---

## 3. Dependency & Sequencing Graph

```
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 4
                │           │              │
                │           └──► Phase 5 ──┴──► Phase 6
                └──► Phase 3 ──► Phase 5
```

**Why this order:**
- **0 → 1:** never refactor on top of a crashing exporter and an inert control.
- **1 → 2:** the LLM needs a schema to target; without it you'd be validating strings.
- **2 → 4:** diagrams and explanations consume the structured model the LLM emits.
- **3 parallel to 2:** persistence depends only on the Phase-1 model, not on the LLM.
- **5 last (before the UI refresh):** the API should wrap a *stable* service interface, not a moving target.
- **6 after 5:** the new UI is a thin layer over already-tested services, so a visual redesign cannot regress domain logic.

---

## 4. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM output unstable / invalid JSON | High | High | Schema-constrained decoding + repair loop + rule fallback |
| API cost or quota exhaustion | Medium | High | Budget ceiling, caching, rate limits, free Ollama mode |
| Refactor regresses the UI | Medium | Medium | `AppTest` flows; UI changes limited to data-binding; real-browser interaction check |
| Prompt injection via uploads | Medium | High | Delimiting, schema validation, injection test in CI |
| Scope creep (too many features) | High | Medium | Phase exit criteria are hard gates; defer auth/microservices |
| Deprecation breakage (`fpdf2`, Streamlit) | High | Medium | Pinned deps in Phase 0; CI `pip-audit` + deprecation-as-error |
| Diagram complexity explodes on large workflows | Low | Medium | Mermaid first; Graphviz fallback; step-count guidance |
| CCv2 JavaScript error invisible to `AppTest` | Medium | Medium | `node --check` gates on both inline modules + real-browser smoke check |
| Theme token drift between config and runtime CSS | Low | Low | Shared palette constants; browser check of light/dark scenes |
| Single developer bandwidth | High | Medium | Each phase independently shippable; ~22–34 days total |

---

## 5. Suggested Milestones for Showcasing

| Milestone | After | Best for |
|---|---|---|
| **M1 — "Audited & stable"** | Phase 0 | Demonstrating rigor: you found and fixed 5 critical bugs |
| **M2 — "Structured & tested"** | Phase 1 | Software engineering interviews: architecture, models, tests |
| **M3 — "Real AI with guarantees"** | Phase 2 | **AI engineering interviews**: schema output, repair, fallback, evals |
| **M4 — "A real product"** | Phase 3–4 | Full-stack depth: persistence, editing, diagrams, exports |
| **M5 — "Production grade"** | Phase 5 | Senior-signal: API, CI/CD, Docker, observability |
| **M6 — "Interview-ready product"** | Phase 6 | Fresh light/dark UI, inline editing, palette, analytics, real demo |

---

## 6. Approval Gate (resolved)

The initial audit phase was strictly read-only. Implementation was subsequently
approved; task 0.13 (removing the dead `index.html`, `style.css` and `assets`
files) was approved and executed. The OpenAI-compatible provider was chosen for
Phase 2, with Ollama for free offline demos. The original "no redesign"
constraint was later superseded by an explicit request for a fresh light/dark
theme, delivered in Phase 6. **All phases 0–6 are complete**; only the optional
OAuth + roles work (5.13) remains deliberately deferred.
