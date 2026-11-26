# 🏗️ CURRENT ARCHITECTURE — AI Workflow Generator

**Scope:** As-is architecture, execution flow, component inventory, and architectural weaknesses.
**Status:** Historical snapshot of the **pre-upgrade** application — see `README.md` and
`MASTER_UPGRADE_ROADMAP.md` for the current layered architecture (Phases 0–4 complete).
**Date:** 2026-01-19

> **Update (task 0.13):** the dead `index.html`, `style.css` and `assets` files
> described below were approved for removal and have been deleted. References
> to them in this document are retained as historical audit evidence only.

---

## 1. Architecture at a Glance

The application is a **single-process, single-file Streamlit monolith** with a pure-function rule engine.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Script Process                     │
│                            app.py (132 lines)                    │
│                                                                  │
│  ┌──────────────┐   ┌───────────────┐   ┌────────────────────┐  │
│  │  UI Layer     │   │  IO / Export  │   │  State             │  │
│  │  - selectbox  │   │  - extract_   │   │  st.session_state  │  │
│  │  - uploader   │   │    text()     │   │  ['steps']         │  │
│  │  - text_area  │   │  - create_pdf │   │  (list[str])       │  │
│  │  - buttons    │   │  - pandas CSV │   │                    │  │
│  └──────┬───────┘   └───────┬───────┘   └─────────┬──────────┘  │
│         │  full_prompt (f-string)                 ▲             │
│         ▼                                         │             │
│  ┌─────────────────────────────────────────────────┴──────────┐  │
│  │              workflow.generate_workflow(text)              │  │
│  │                    workflow.py (94 lines)                  │  │
│  │  validate → lower → regex split → 6 domain rule blocks    │  │
│  │            → generic catch-all → dedup → "Step N: ..."     │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
          │                                   │
          ▼                                   ▼
   Browser (renders HTML             Downloads (CSV bytes,
   with unsafe_allow_html)           PDF bytes)
```

**There are no layers, no modules, no package, no configuration object, no data models, and no service boundary.**

---

## 2. Execution Flow (happy path)

```
1.  st.set_page_config(page_title="Architect AI", layout="centered")
2.  Inject custom CSS + hero HTML via st.markdown(unsafe_allow_html=True)
3.  User selects category            (selectbox, 6 options)
4.  User optionally uploads PDF/TXT   (st.file_uploader)
5.  User types description            (st.text_area)
6.  User clicks "⚡ Generate Workflow"
      │
      ├─ 6a. extract_text(uploaded_file)
      │       ├─ application/pdf → pypdf.PdfReader → page.extract_text()
      │       └─ otherwise      → .getvalue().decode("utf-8")
      │       └─ except Exception → st.error(...) → return ""
      │
      ├─ 6b. full_prompt = f"Category: {category}\nContext: {user_input}\nAdditional Info: {file_content}"
      │
      ├─ 6c. if user_input.strip() or file_content.strip():
      │        steps = generate_workflow(full_prompt)
      │        if steps:  st.session_state['steps'] = steps     # always true
      │        else:      st.error(...)                          # DEAD CODE
      │      else: st.warning("Please provide a description or upload a file.")
      │
7.  if 'steps' in st.session_state:            # every subsequent rerun
      ├─ Render each step as HTML card (prefix stripped, unsafe_allow_html)
      ├─ pd.DataFrame(steps).to_csv()  → download button      ← rebuilt every rerun
      └─ create_pdf(steps)             → download button      ← rebuilt every rerun
```

### Key observation: **rerun-based rendering**
Streamlit re-executes the whole script on *every* interaction. Everything under `if 'steps' in st.session_state` (lines 110–130) therefore re-runs continuously — including PDF generation — regardless of whether the user intends to download.

---

## 3. Component Inventory

### 3.1 `app.py` — 4 responsibilities in 1 file

| Lines | Responsibility | Should live in |
|---:|---|---|
| 8–20 | File extraction (PDF/TXT) | `services/document_ingest.py` |
| 22–33 | PDF rendering | `services/exporters/pdf_exporter.py` |
| 36–74 | Page config + CSS + hero HTML | `ui/` (or `st.css`) |
| 79–107 | Input collection + orchestration | `ui/` + `services/generation_service.py` |
| 110–130 | Result rendering + export | `ui/` + `services/exporters/` |

### 3.2 `workflow.py` — a single 94-line function

```
generate_workflow(text: str) -> list[str]
  ├─ validate non-empty                       (line 5)
  ├─ text.lower().strip()                     (line 8)   ← destroys casing
  ├─ re.split(r"[.!?\n]+", text)              (line 11)  ← fragile tokenizer
  ├─ for each sentence:                       (lines 17-78)
  │    ├─ Education block        (lines 23-29)   keyword gate: student/admission/course/exam/teacher/school
  │    ├─ Business block         (lines 32-39)   keyword gate: customer/order/payment/invoice/client/employee
  │    ├─ Real Estate block      (lines 42-48)   keyword gate: property/house/tenant/buyer/rent/listing
  │    ├─ Hospital block         (lines 51-56)   keyword gate: patient/doctor/appointment/medical/health/ward
  │    ├─ Software block         (lines 59-65)   keyword gate: software/code/sprint/feature/bug/developer/git
  │    ├─ IT/Infra block         (lines 68-71)   keyword gate: user/login/server/database/cloud
  │    └─ Generic catch-all      (lines 74-78)   start/begin/update/save/store/email/send/end/finish
  ├─ dedup preserving order, prefix "Step N: "  (lines 81-86)
  └─ fallback: echo sentences[0] or sentinel     (lines 88-92)
```

**Structural properties:**
- Blocks are **not mutually exclusive** → cross-domain contamination (C-05).
- Blocks run in **fixed order**, not input order → scrambled output (C-06).
- Every rule uses `if "keyword" in sentence` → substring false positives (C-04).
- Rules are **flat, unstructured conditionals** — no data-driven config, no per-domain isolation.
- Return type `list[str]` **cannot express** dependencies, branches, conditions, roles, or timing.

### 3.3 Data contract (the central architectural flaw)

```
UI ──(f-string)──► engine ──(list[str] with "Step N: " prefix)──► UI
                     ▲                                              │
                     └──────── consumers must re-parse ◄────────────┘
                          app.py:30  (PDF)
                          app.py:116 (HTML)
                          index.html:41 (dead)
                          app.py:126 (CSV — does NOT strip)
```

Two problems compound:
1. **Presentation is baked into the data** — the prefix must be stripped by every consumer, and one (CSV) forgets.
2. **The input is a formatted string, not arguments** — the engine cannot distinguish the category from the description, so it re-parses the UI's own labels as prose (C-01, C-02).

---

## 4. State & Persistence Model

| Aspect | Current behavior |
|---|---|
| In-memory state | `st.session_state['steps']` — a single `list[str]` |
| Persistence | **None.** Refresh, new tab, or crash → everything lost |
| History | **None** |
| Multiple workflows | **None** — one slot, silently overwritten |
| Metadata retained | **None** — category, prompt, file, and timestamp are discarded |
| Concurrency | Streamlit sessions are isolated; no shared state issues (and no sharing capability either) |
| Caching | **None** — no `st.cache_data` / `st.cache_resource` |

**Consequence:** the app cannot support history, saved projects, execution tracking, or collaboration without a persistence layer. This is the largest *missing* capability.

---

## 5. Dependency Graph

```
app.py
 ├── streamlit      (UI framework, runtime)
 ├── pandas         (used ONLY for one to_csv call → heavy, replaceable)
 ├── fpdf           (PDF export; package name "fpdf2")
 ├── pypdf          (PDF text extraction)
 └── workflow.py    (local, pure Python, zero deps)

index.html ──(Jinja2 syntax, url_for)──► NO BACKEND EXISTS   ← orphaned
style.css  ──(referenced only by index.html)──► orphaned
```

**Dependency health:** `requirements.txt` has **4 unpinned lines**. Verified deprecated usages (see `AUDIT_REPORT.md` C-10) make a future break near-certain.

**Notable over-dependency:** `pandas` (+ transitive `numpy`) is imported solely for:
```python
pd.DataFrame(steps, columns=["Workflow"]).to_csv(index=False).encode('utf-8')
```
The standard-library `csv` module does this in three lines with zero transitive dependencies.

---

## 6. Deployment Topology

```
GitHub (Ganeshbasani/ai-workflow-generator)
   │  push
   ▼
Streamlit Community Cloud  ──►  https://ai-workflow-generator-cysztisfr9rbs8ro7fcuuw.streamlit.app/
   │
   └── Runtime: 1 process, 1 file, port 8501
       No container spec, no CI/CD, no health checks, no metrics

Local / Codespaces:  .devcontainer/devcontainer.json
   └── postAttachCommand: streamlit run app.py
         --server.enableCORS false
         --server.enableXsrfProtection false     ← both security features OFF
```

**Missing for production:** container image, CI pipeline, health/readiness endpoints, structured logging, metrics, secrets management, rollback strategy, resource limits.

---

## 7. Architectural Weaknesses (ranked)

| # | Weakness | Impact | Ref |
|---|---|---|---|
| 1 | **No structured data model** — steps are prefixed strings | Blocks diagrams, editing, dependencies, conditions, tracking, and every AI feature on the roadmap | C-11 |
| 2 | **No service/UI separation** — `app.py` mixes 4 concerns | Untestable in isolation; every change risks the UI | §3.1 |
| 3 | **No persistence** | No history, no saved projects, no execution state | §4 |
| 4 | **Ambiguous engine contract** — errors, sentinels, results in one channel | Dead error branch; errors render as content | C-07 |
| 5 | **Formatted-string input** to the engine | Category ignored; metadata leaks to output | C-01, C-02 |
| 6 | **Rule logic not data-driven** | Adding a domain requires editing nested conditionals | §3.2 |
| 7 | **Exporters coupled to UI and to string parsing** | Duplicated prefix-stripping; inconsistent outputs | C-11 |
| 8 | **No configuration layer** | No place for model choice, limits, feature flags, secrets | — |
| 9 | **No observability** — zero logging | Incidents are invisible; LLM cost/latency unknowable | — |
| 10 | **No automated tests** | Refactors are unsafe; regressions ship silently | — |

---

## 8. Target Architecture (preview — detail in `MASTER_UPGRADE_ROADMAP.md`)

The upgrade preserves the UI's visual identity while introducing real layers:

```
┌──────────────────────────────────────────────────────────────────┐
│  UI (Streamlit) — same visual identity, same CSS tokens          │
│  input · result cards · diagram · editor · history · export       │
└────────────────────────────┬─────────────────────────────────────┘
                             │ typed DTOs (Pydantic)
┌────────────────────────────▼─────────────────────────────────────┐
│  Application Services                                            │
│  GenerationService · ExportService · ProjectService · RunService  │
└───────┬──────────────────────────┬───────────────────┬───────────┘
        │                          │                   │
┌───────▼────────┐   ┌─────────────▼──────┐   ┌────────▼─────────┐
│ Provider Layer │   │  Persistence       │   │  Exporters       │
│ (protocol)     │   │  SQLite + repo     │   │  JSON/CSV/PDF/   │
│ ├ LLMProvider  │   │  interface         │   │  Markdown/Mermaid│
│ ├ RuleProvider │   └────────────────────┘   └──────────────────┘
│ └ Fallback     │
└────────────────┘
        │
┌───────▼────────────────────────────────────────────────────────┐
│  Validation & Repair: Pydantic schema + retry-on-invalid-JSON  │
│  Observability: structured logs, request IDs, token/latency    │
└────────────────────────────────────────────────────────────────┘
```

**Design principles for the target:**
1. **Structured data first** — `Workflow` / `Step` Pydantic models are the single source of truth; UI, exports, diagrams, and DB all derive from them.
2. **Provider abstraction** — LLM and rule engines implement one `WorkflowProvider` protocol, so swapping/falling back is a one-line change.
3. **Deterministic fallback preserved** — the existing `workflow.py` logic is **reused as the fallback provider**, not discarded.
4. **Exporters are pure functions** of the model — no UI knowledge, no string re-parsing.
5. **Same visual identity** — color tokens, typography, card style, and layout are carried over unchanged.

---

## 9. Summary

| Question | Answer |
|---|---|
| How many runtime dependencies does the core logic have? | **Zero** (`workflow.py` is pure stdlib) |
| How many Python files actually execute? | **2** (`app.py`, `workflow.py`) |
| How many files are dead? | **3** (`index.html`, `style.css`, `assets`) |
| Is there an API layer? | **No** |
| Is there persistence? | **No** |
| Is there a data model? | **No** — `list[str]` |
| Is there auth? | **No** |
| Is there logging? | **No** |
| Is there CI? | **No** |
| Are there tests? | **No** |
| Biggest single structural blocker to AI features? | **The `"Step N: "` string data contract** |

**Bottom line:** the architecture is *simple* — which is a genuine advantage for a safe refactor — but it is *not layered*. The upgrade path is to introduce structure **around** the existing engine while keeping the UI's look and feel intact.
