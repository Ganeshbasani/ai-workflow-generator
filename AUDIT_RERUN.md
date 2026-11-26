# 🔁 AUDIT RE-RUN — Phase 5B Production Hardening + Phase 6 UI Refresh

> **Historical report.** This audit records the state on 2026-11-21. The 2026-11-23 core generation and UI changes alter provider behavior, so the older pass counts, screenshots, and production claims below are not evidence for the current revision. See the current verification section in `README.md`.

**Date:** 2026-11-21
**Baseline:** [`AUDIT_REPORT.md`](AUDIT_REPORT.md) (2026-01-19, prototype at ~3/10)
**Scope:** repository, runtime dependencies, HTTP boundary, container image, CI configuration and the redesigned Streamlit UI
**Method:** read-only re-inspection plus execution of the same quality gates used in CI, followed by a real-browser interaction check of the new UI. No finding is marked resolved on assertion alone; each row below cites a test, a config file or an executed command.

---

## 1. Executive summary

| Severity | Baseline | Now |
|---|---:|---:|
| 🔴 Critical / security High | 6 | **0** |
| 🟠 High / Medium-High | 3 | **0** |
| 🟡 Medium and below | 17 | **0 open** (3 documented, accepted design limits) |

**Result: zero 🔴/🟠 findings.** The original top defect — domain selection having no effect — is not only fixed but proven with the same ambiguous-input reproduction from the baseline audit. Dependency auditing initially found 26 known vulnerabilities in the pinned `pypdf 6.16.2`; the pin was raised to the patched `7.1.1` and the audit re-run is clean. The subsequent Phase 6 UI refresh replaced the original shell with a fresh light/dark tabbed interface without changing the service stack or domain logic; all gates were re-run afterwards, including a real-browser check that caught and fixed a browser-only CCv2 JavaScript syntax error AppTest could not see. The demo GIF was regenerated from the redesigned app.

Residual items are explicit, documented limitations rather than open defects: per-process rate limits/metrics/SQLite, URL-token rather than real authentication (OAuth deliberately deferred), and PDF glyph fallback for CJK/RTL/emoji. See the "Honest Limitations" section of `README.md`.

---

## 2. Correctness findings (C-01 → C-15)

| ID | Baseline finding | Resolution / evidence | Status |
|---|---|---|---|
| 🔴 C-01 | Domain selector had zero effect | `category` is a typed argument to `GenerationService`; scored domain selection in `providers/rule.py`, LLM system prompt in `providers/llm.py`. Verified live: ambiguous description "Run the test and review the result." yields `education` / `software` / `hospital` steps for the three categories. `test_regressions.py`, `eval/` gates | ✅ |
| 🔴 C-02 | Prompt metadata leaked into output | Prompt instructs structured output; transport metadata lives in `GenerationRequest` fields, not in the description string. `test_regressions.py`, `test_llm_provider.py` | ✅ |
| 🔴 C-03 | PDF export crashed on non-Latin-1 text | Bundled DejaVu Unicode fonts in `fpdf2`; emoji / em-dash / CJK / RTL matrix in `test_exporters.py` and `test_app_ui_phase4.py` | ✅ |
| 🔴 C-04 | Substring matching false positives | Word tokenisation + alias normalisation (`_WORD_RE`, `_ALIASES`); regression cases cover "approve the plan" false positives | ✅ |
| 🔴 C-05 | Cross-domain contamination | Domain-scoped rule sets and one selected domain per request; cross-domain isolation regression test | ✅ |
| 🟠 C-06 | Domain-grouped rather than user-intent ordering | Sentence-by-sentence matching plus `validate_workflow()` topological order shared by cards, diagram and all exports | ✅ |
| 🟠 C-07 | Errors/sentinels rendered as steps | Typed exception hierarchy + dedicated error channel; UI and API both render `error`/`message`, never a step. 422/402/413/429/502/500 mapping in `api/errors.py` | ✅ |
| 🟡 C-08 | Global dedup collapsed repeats | Dedup is per sentence; repeated stages survive (`test_regressions.py`) | ✅ |
| 🟡 C-09 | Header showed current, not generated, category | Category is stored on the generated `Workflow`; every surface renders the artifact's own value | ✅ |
| 🟠 C-10 | Deprecated APIs + unpinned dependencies | All runtime and dev deps pinned (incl. `pandas==3.1.1`); `st.iframe` replaces `components.v1.html`; drag-and-drop and palette use Custom Components v2 only; no `txt=`/`ln=`/`set_font("Arial")` or `use_container_width`. Suite runs with `-W error::DeprecationWarning`; both inline JS modules pass `node --check`. `pypdf` pin patched to 7.1.1 | ✅ |
| 🟡 C-11 | Exports mutually inconsistent | Pydantic `Workflow` is the single source of truth; pure exporters consume it, tested for cross-export consistency | ✅ |
| 🟡 C-12 | Redundant work on every rerun | Cached settings/factory and in-process metrics; no repeated parsing of display strings | ✅ |
| 🟡 C-13 | Fragile sentence tokenization | `_SENTENCE_RE` splits on punctuation/newlines with alias normalisation | ✅ |
| 🟡 C-14 | Casing lost in fallback | First sentence retains its original casing (`test_regressions.py`) | ✅ |
| 🟡 C-15 | Silent failure on non-UTF-8 uploads | `ingest/documents.py` handles decode failures with a typed, user-safe message | ✅ |

---

## 3. Security findings (S-01 → S-10)

| ID | Baseline severity | Resolution / evidence | Status |
|---|---|---|---|
| S-01 | High — reflected XSS | All interpolated HTML is escaped; themed diagram escapes labels. XSS regression test in `test_regressions.py` | ✅ |
| S-02 | Medium — upload hardening | `max_upload_bytes`, page/char caps, MIME + extension checks, patched pypdf. `test_ingest.py` | ✅ |
| S-03 | Medium — devcontainer disabled CORS/XSRF | Rewritten `.devcontainer/devcontainer.json` does not pass either flag; API port 8000 forwarded | ✅ |
| S-04 | Medium — no secret management | `.gitignore`, `.env.example`, Streamlit-secrets guidance in README; gitleaks in CI, `detect-private-key` pre-commit hook | ✅ |
| S-05 | Medium — no input caps | `Settings` limits for description/context/tokens, request-size middleware, rate limit, daily cost ceiling. `test_limits.py`, `test_api.py` | ✅ |
| S-06 | Low-Med — exception details leaked | Typed error taxonomy maps to user-safe messages; logs contain types/lengths only | ✅ |
| S-07 | Low — no authentication | Replaced by owner scoping: URL session token for UI, `X-Owner-Id` header seam for a future auth layer. OAuth + roles explicitly deferred (roadmap 5.13) and documented as a limitation | ✅ accepted |
| S-08 | Low — no rate limiting | Per-session rate limiter and daily cost tracker reused by UI and API; 429/402 tests | ✅ |
| S-09 | Low — CSV formula injection | `_safe_cell()` neutralises formula-leading characters. Exporter tests | ✅ |
| S-10 | Info — no secret scan / CI | GitHub Actions gitleaks job on every PR; pre-commit `detect-private-key`; no secrets in tracked files | ✅ |

---

## 4. Executed verification evidence

| Gate | Command | Result |
|---|---|---|
| Full suite + coverage | `coverage run -m pytest -q` → `coverage report` | 216 passed, 96% (≥ 85% gate) |
| Deprecations | `pytest -q -W error::DeprecationWarning` | no deprecation warnings |
| Lint | `ruff check .` | clean |
| Types | `mypy app.py src/workflow_ai` (strict) | clean |
| CCv2 JavaScript syntax | `node --check` on both inline modules (tested via `tests/test_ui_components.py`) | both modules parse; browser-only `else` syntax bug fixed |
| Real-browser interaction | headless Chrome against `streamlit run app.py`: palette + Ctrl+K, generate, Editor tab, Alt+arrow reorder, dark/compact toggles, Analytics | all interactions passed; no `BidiComponent Error` |
| Hooks | `pre-commit run --all-files` | all hooks pass |
| Dependency audit | `pip-audit -r requirements-dev.txt` | 0 known vulnerabilities (pypdf 7.1.1; `pandas==3.1.1` pinned) |
| Demo capture | seven headless-Chrome scenes stitched into `docs/demo.gif` | real redesigned UI, no fabricated frames |
| YAML / config | `pre-commit validate-config`, `docker compose config`, PyYAML parse of all YAML | valid |
| Container build | `docker build -t ai-workflow-generator:local .` | succeeded, runtime deps only, non-root UID 10001 |
| Container probes | `docker run -p 8100:8000 …` → `/health`, `/ready`, `/openapi.json` | `ok`, `ready`/`rule`, 14 paths incl. `/api/v1/workflows/generate` |
| End-to-end generate | `POST /api/v1/workflows/generate` (no key) | 4 ordered steps, `provider: rule`, project persisted to `/data` |
| Graceful shutdown | `docker stop -t 15` | exit 0, clean uvicorn shutdown log |
| Domain effect | three categories, ambiguous description | three distinct domains and step sets |

CI repeats these gates on every pull request, builds the image from a clean checkout, probes it, and publishes to GHCR only on `v*` tags. All changes remain uncommitted and unpushed, as requested.

---

## 5. Conclusion

The prototype's five critical and three high-severity correctness defects, plus the high-severity security defect, are closed with executable evidence. The dependency set is pinned and patched, the deprecated API surface is gone, and the same services are reachable from both Streamlit and a versioned HTTP API. The Phase 6 UI refresh replaced the original shell with a fresh light/dark tabbed interface — verified in a real browser, including the command palette, inline editor, drag/keyboard reordering, theme/density toggles and analytics — while leaving the service stack and domain logic untouched. The application is ready for an interview deep-dive and for a follow-up phase that introduces real authentication and multi-instance infrastructure when those needs actually exist.
