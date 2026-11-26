# 📋 AUDIT REPORT — AI Workflow Generator

> **✅ RE-AUDIT STATUS (2026-11-21):** This document is the **original baseline audit** of the prototype. All 🔴 Critical and 🟠 High findings have been resolved during Phases 0–5; the patched dependency set passes `pip-audit`, and no deprecated APIs remain. See [`AUDIT_RERUN.md`](AUDIT_RERUN.md) for the finding-by-finding verification and [`MASTER_UPGRADE_ROADMAP.md`](MASTER_UPGRADE_ROADMAP.md) for the work log. Historical findings below are retained for traceability, not as open issues.

**Audit type:** Read-only repository inspection (no application code modified)
**Date:** 2026-01-19
**Auditor role:** Senior Software Architect / AI Engineer / Backend Engineer / Code Auditor
**Verification environment:** Python 3.12.10, `fpdf2 2.9.0`, `streamlit 1.67.0`, `pypdf 6.16.2`
**Repository state after audit:** `git status` → *clean* (audit byproducts removed)

---

## 1. Executive Summary

This is a **small, readable, well-intentioned prototype** with a genuinely attractive dark UI — and a workflow engine that is a **keyword matcher, not an AI system**. The project is at **prototype maturity (~3/10)** and is **not production-ready**.

The single most important finding: **the app's headline feature — industry/domain selection — has zero effect on the generated output.** This was verified empirically, not inferred.

| Dimension | Grade | One-line verdict |
|---|---|---|
| Visual design / UI identity | **B+** | Cohesive, modern, worth preserving exactly |
| Workflow engine correctness | **D** | Substring keyword rules; verified false positives, cross-domain contamination |
| Code quality & structure | **C−** | 2 monolithic files, no layers, no types, no docstrings |
| Security posture | **D+** | One reachable XSS, no upload limits, no secret management |
| Testing | **F** | Zero tests of any kind |
| Deployment readiness | **D** | Unpinned deps, deprecated APIs, no CI/CD, no container |
| Documentation accuracy | **C** | Good prose; README example does not match real output |
| **Overall** | **3/10** | Strong foundation for an upgrade, weak as a showcase today |

**Verdict:** The project is an excellent *starting point* for a production upgrade, but in its current state it would **not** survive a technical interview deep-dive. The good news: every critical issue is fixable within a few focused phases, and the existing visual identity can be preserved verbatim.

---

## 2. Repository Inventory

### 2.1 Tracked files (8 total, 536 lines)

| File | Lines | Role | Status |
|---|---:|---|---|
| `app.py` | 132 | Streamlit UI + PDF/CSV export + file parsing | **Active** — but over-merged responsibilities |
| `workflow.py` | 94 | Rule-based workflow engine | **Active** — core logic, heavily flawed |
| `requirements.txt` | 4 | Dependencies (unpinned) | **Active** — risk |
| `README.md` | 129 | Documentation | **Active** — partially inaccurate |
| `index.html` | 56 | Jinja/Flask template (`{% if steps %}`, `url_for`) | **⛔ DEAD CODE** |
| `style.css` | 121 | Stylesheet for the above template | **⛔ DEAD CODE** |
| `assets` | 2 bytes | A single `\r\n` newline — not a directory | **⛔ ACCIDENTAL COMMIT** |
| `.devcontainer/devcontainer.json` | 33 | Codespaces config | Active, but **disables security features** |

### 2.2 Missing (expected in a production repo)

`.gitignore` · `LICENSE` · `tests/` · `.github/workflows/` · `Dockerfile` · `pyproject.toml` · `.env.example` · `CONTRIBUTING.md` · `Makefile`

### 2.3 Dead code evidence

- `index.html` uses Jinja2 syntax (`{% if steps %}`, `{{ loop.index }}`) and `url_for('static', ...)`.
- `grep` across all `.py` and `.md` files for `index.html`, `style.css`, `url_for`, `render_template`, `Flask` → **zero matches**.
- Git history shows commit `7330e21` ("Convert app to Flask") followed by `4d8dbc1` ("Migrate index route to Streamlit interface"). The Flask frontend was **left behind** when the app migrated to Streamlit.
- `assets` is a 2-byte file containing only a CRLF, created by commit `75e4d4a` ("Create assets") — a mistaken file-vs-directory commit.

---

## 3. Critical Findings (Verified Empirically)

> Every finding below was **reproduced by executing the existing code**. Reproduction steps are included so they can be re-verified.

### 🔴 C-01 — Domain selection has **zero effect** on output
**Severity:** Critical · **File:** `app.py:79-82`, `app.py:97`, `workflow.py:3`

`app.py` builds a formatted prompt:
```python
full_prompt = f"Category: {category}\nContext: {user_input}\nAdditional Info: {file_content}"
steps = generate_workflow(full_prompt)
```
But `workflow.py` never reads the category — it just lowercases and regex-splits the whole string.

**Reproduction:**
```
Category: Hospitals          | Approve the plan  -> ['Step 1: Category: hospitals']
Category: Real Estate        | Approve the plan  -> ['Step 1: Category: real estate']
Category: Software Industries| Approve the plan  -> ['Step 1: Category: software industries']
```
Identical structure every time. **The user-facing dropdown is decorative.**

---

### 🔴 C-02 — Injected prompt metadata leaks into the workflow output
**Severity:** Critical · **File:** `workflow.py:88-92` (fallback), `app.py:97`

When no keyword matches, the fallback returns `sentences[0]` — which is the **app's own injected label**, not user content.

**Reproduction (exact app.py prompt construction):**
```
Input : Category: Hospitals / Context: "Approve the plan" / Additional Info:
Output: ['Step 1: Category: hospitals']
```
The UI then renders **"Step 1: Category: hospitals"** inside a styled workflow card as if it were a generated step. This is the most demo-destructive bug in the project: a recruiter typing any vague sentence sees the app's internal plumbing displayed as its output.

---

### 🔴 C-03 — PDF export crashes the entire app on non-Latin-1 text
**Severity:** Critical · **File:** `app.py:22-33`, `app.py:129`

`create_pdf()` uses FPDF2 core fonts (Latin-1 only). Any em-dash `—`, curly quote `“`, bullet `•`, arrow `→`, or emoji raises an **unhandled** `FPDFUnicodeEncodingException`.

**Reproduction:**
```
generate_workflow('Approve — the plan')  ->  ['Step 1: Approve — the plan']
create_pdf(steps)                        ->  FPDFUnicodeEncodingException
    Character "—" ... is outside the range of characters supported by the font used: "helvetica"
```
**Why it is critical:** `create_pdf(steps)` at `app.py:129` is called **unconditionally on every Streamlit rerun** while results exist — not only when the download button is clicked. So a user who types an em-dash triggers a full-page traceback on their very next interaction.

The fallback path (`workflow.py:91`) echoes raw user text, so this is **directly reachable from the UI**.

---

### 🔴 C-04 — Substring keyword matching produces false positives
**Severity:** High · **File:** `workflow.py` (all rules use `if "x" in s`)

`"x" in s` matches **anywhere inside any word**. Verified false positives:

| User text | Actual output | Root cause |
|---|---|---|
| `send the parcel` | `Complete workflow process` | `"end" in "send"` |
| `render the page` | `Complete workflow process` | `"end" in "render"` |
| `extend the subscription` | `Complete workflow process` | `"end" in "extend"` |
| `review the listing` | `Schedule property viewing` | `"view" in "review"` |
| `verification of records` | *(raw echo — no match)* | `"verify" not in "verification"` |

Note the asymmetry: matching is **too loose** on short words and **too strict** on morphology (no stemming). Both directions are wrong.

---

### 🔴 C-05 — Cross-domain contamination
**Severity:** High · **File:** `workflow.py:22-71`

Domain blocks are **not mutually exclusive** — all six run against every sentence. One sentence mentioning several domains triggers contradictory steps from all of them.

**Reproduction:**
```
"Register the customer and schedule a patient appointment for the teacher
 to review the software bug on the rental property."
→ Step 1: Register new client/customer
→ Step 2: Schedule property viewing        ← "review" contains "view"
→ Step 3: Collect rental payment           ← "rental" contains "rent"
→ Step 4: Schedule doctor appointment
→ Step 5: Conduct code review
```
The user's actual intent (register → appoint → review bug) is entirely lost, replaced by five unrelated canned strings.

---

### 🟠 C-06 — Step ordering follows rule-block order, not user intent
**Severity:** Medium-High · **File:** `workflow.py:22-71`

Rules execute in hard-coded block order (Education → Business → Real Estate → Hospital → Software → IT → Generic), so output ordering is **domain-grouped, not chronological**. Confirmed in C-05: the *property* steps appear before the *hospital* step even though property was mentioned last.

---

### 🟠 C-07 — Error/sentinel strings masquerade as workflow steps
**Severity:** Medium-High · **File:** `workflow.py:5,92`, `app.py:101-105`

`generate_workflow` returns **the same type** (`list[str]`) for success, validation failure, and "nothing detected". Consequences:

- `if steps:` at `app.py:102` is **always truthy** (the function never returns an empty list).
- The branch `st.error("The workflow engine returned no results...")` at `app.py:105` is **dead code**.
- Messages like `Please enter a valid workflow description` render inside styled step cards as if they were generated content.

There is **no error channel** — the contract between UI and engine is ambiguous.

---

### 🟠 C-08 — Global deduplication collapses legitimate repeated steps
**Severity:** Medium · **File:** `workflow.py:81-86`

Dedup is global across the entire input. A process that legitimately repeats a step (e.g. per-customer payment processing) collapses to one.

**Reproduction:** 500 repetitions of a full business process → **3 steps total**.

---

### 🟠 C-09 — Results header shows the wrong category
**Severity:** Medium · **File:** `app.py:113`

The header uses the **current** `st.selectbox` value, not the category in effect when the workflow was generated. Generate under *Hospitals*, switch to *Real Estate*, and the header reads **"Real Estate Workflow"** above hospital steps. The generated artifact is not self-describing.

---

### 🟠 C-10 — Deprecated library APIs + unpinned dependencies = guaranteed future breakage
**Severity:** Medium-High · **File:** `requirements.txt`, `app.py:25-32,127,130`

Verified against current releases:

| Usage in `app.py` | Status in current version | Impact |
|---|---|---|
| `set_font("Arial", ...)` | **DeprecationWarning:** *"Substituting font arial by core font helvetica — deprecated since v2.7.8, and will soon be removed"* | PDF export breaks on next `fpdf2` release |
| `pdf.cell(..., txt=..., ln=True)` | `txt` deprecated since 2.7.6; `ln` deprecated since 2.5.2 | Breaks on removal |
| `st.download_button(..., use_container_width=True)` | **Deprecated** in `streamlit` 1.67 (both `st.button` and `st.download_button`) | Breaks on removal |
| `requirements.txt`: `streamlit`, `pandas`, `fpdf2`, `pypdf` — **no versions** | Non-reproducible installs | Any fresh install can break without a code change |

---

### 🟡 C-11 — Exports are mutually inconsistent
**Severity:** Low-Medium · **File:** `app.py:30`, `app.py:116`, `app.py:126`

Three different renderings of the same data:

| Surface | `"Step 1: Register new client/customer"` becomes |
|---|---|
| UI card | `Register new client/customer` (prefix stripped) |
| PDF | `Register new client/customer` (prefix stripped) |
| **CSV** | `Step 1: Register new client/customer` (**prefix kept**) |

The `split(":", 1)[1]` stripping logic is duplicated three times (`app.py:30`, `app.py:116`, `index.html:41`).

---

### 🟡 C-12 — Unnecessary work on every rerun
**Severity:** Low-Medium · **File:** `app.py:126,129`

Both exports are rebuilt on **every** Streamlit interaction (widget change, hover, etc.) while results exist — not on click. `pandas` is imported solely to call `to_csv()` once, pulling in `numpy` for a job the standard library `csv` module does for free.

---

### 🟡 C-13 — Fragile sentence tokenization
**Severity:** Low-Medium · **File:** `workflow.py:11`

`re.split(r"[.!?\n]+", text)` splits on **every** period, breaking decimals (`3.5`), abbreviations (`Dr.`, `e.g.`), versions (`v1.2.3`), and URLs. Semicolons — a common list delimiter in process descriptions — are **not** split at all (verified: `retry twice; otherwise ship...` stayed one sentence).

---

### 🟡 C-14 — Casing destroyed in the fallback path
**Severity:** Low · **File:** `workflow.py:8,91`

`text.lower()` runs before tokenization, then `.capitalize()` restores only the first letter. `AI Workflow` → `Ai workflow`. Original user wording is lost.

---

### 🟡 C-15 — Silent failure on non-UTF-8 uploads
**Severity:** Low-Medium · **File:** `app.py:16-20`

`.decode("utf-8")` raises `UnicodeDecodeError` for any other encoding (Latin-1, UTF-16 — common in Windows-notepad exports). The broad `except Exception` returns `""`, so **the file appears to upload successfully but contributes nothing**, with only a generic error toast. `page.extract_text()` can also return `None`, causing `text += None` → `TypeError` (same swallowed path).

---

## 4. Security Findings

| ID | Severity | Finding | Location |
|---|---|---|---|
| **S-01** | **High** | **Reflected XSS.** User-derived text is interpolated into HTML rendered with `unsafe_allow_html=True`. Reachable via the fallback path, which echoes raw input. | `app.py:117-122` |
| **S-02** | Medium | **No file-upload hardening.** No size cap (Streamlit default 200 MB), no page-count limit, MIME type trusted from the client, untrusted PDF parsed by `pypdf` (historical DoS/CVE surface). | `app.py:8-20, 84` |
| **S-03** | Medium | **Security features disabled in devcontainer:** `--server.enableCORS false --server.enableXsrfProtection false`. Harmless in Codespaces, dangerous if copied to a deployment script. | `.devcontainer/devcontainer.json:22` |
| **S-04** | Medium | **No secret management.** No `.gitignore`, no `.env.example`, no `.streamlit/secrets.toml` guidance. Today there is no key, but the LLM upgrade introduces one — the scaffolding must exist *before* the key does. | repo root |
| **S-05** | Medium | **No input length caps.** A 46 KB payload was accepted and processed. Harmless for regex; a **cost/DoS vector** once an LLM is behind it. | `app.py:86-97` |
| **S-06** | Low-Med | **Exception details leaked to the UI** (`st.error(f"Error reading file: {e}")`) — internal paths/framework info disclosed. | `app.py:19` |
| **S-07** | Low | **No authentication/authorization.** Acceptable for a public read-only demo; must be addressed before any shared persistence. | — |
| **S-08** | Low | **No rate limiting / abuse protection** on a publicly hosted Streamlit app. | — |
| **S-09** | Low | **CSV formula injection** if a user-controlled fallback string (`=HYPERLINK(...)`) is exported and opened in Excel. Self-inflicted today; becomes real if workflows are shared. | `app.py:126` |
| **S-10** | Info | **No secret scan / no CI.** A manual `git log -p` scan found **no leaked secrets** in history — a genuine positive. | — |

---

## 5. Non-Functional Assessment

### 5.1 Performance — **Not a problem today**
Measured on the current engine:

| Input | Size | Time | Result |
|---|---:|---:|---|
| 500 repeated business sentences | 46,499 chars | **0.010 s** | 3 steps (dedup collapsed them) |
| 5,000 short sentences | ~30,000 chars | **0.014 s** | 5 steps |

**Honest conclusion:** the rule engine is fast. Performance is **not** a real bottleneck and should not be cited as one. The genuine scalability limits are architectural: a monolithic rule table that cannot grow, and a synchronous UI with no persistence.

### 5.2 Maintainability — Weak
- Two files, no package structure, no separation of concerns (`app.py` does UI + parsing + PDF + CSV + state).
- No type hints, no docstrings, no logging, no linting/formatting config.
- Rules are an unstructured wall of `if` statements — adding a domain means editing a 94-line file full of unrelated conditionals.
- Data contract is `list[str]` with a `"Step N: "` prefix baked in — presentation embedded in the data model.

### 5.3 Scalability — Architectural ceiling
The engine cannot represent dependencies, branches, roles, durations, or conditions. No amount of rule tuning reaches that; it requires a **new data model**.

### 5.4 UI/UX — The project's strongest asset
**Preserve verbatim:** `#020617` background, indigo `#6366f1` accent, Inter typography, gradient hero title, badge pill, left-bordered step cards with `fadeIn` animation, centered layout.

Targeted gaps (not a redesign):
- **No responsive breakpoints** — `.main-title { font-size: 56px }` will overflow on small screens; zero media queries.
- **Accessibility** — no ARIA labels, no focus-visible styles, `!important`-heavy overrides, color-only step numbering, `<div>`-based layout instead of semantic elements.
- **No empty/loading/error states** beyond basic `st.warning`/`st.error`.
- **No dark-mode toggle** (optional; the dark theme is the identity).
- `layout="centered"` limits width — fine now, but constrains future diagrams.

### 5.5 Documentation accuracy — Partially wrong
| README claim | Reality |
|---|---|
| Example output: `Step 1: Register customer` / `Step 2: Save data to database` | Actual: `Step 1: Register new client/customer`; `Save data to database` only appears if input contains `save`/`store`/`update` |
| "Basic conditional logic (e.g., failed payment)" | **No conditional logic exists** — output is a flat list |
| "Handles small to enterprise-scale workflows" | Untested marketing claim; large inputs collapse via dedup (C-08) |
| "License: MIT" badge | **No `LICENSE` file exists**; text elsewhere says "educational purposes" |
| Project structure section | Omits `index.html`, `style.css`, `assets`, `.devcontainer` |
| "NLP-based intelligent parsing" (future) | Accurate — none exists today |

### 5.6 What is genuinely good (protect this)
1. **Visual identity** — cohesive, modern, interview-worthy. Do not redesign.
2. **Readable, low-dependency code** — 226 lines of Python, easy to reason about and refactor safely.
3. **Correct happy-path coverage** — the business/healthcare/education/software happy paths produce sensible steps.
4. **Right instincts** — dedup, domain taxonomy, non-empty fallback, dual export, optional context file. The *ideas* are correct; the *execution* is keyword-deep.
5. **No secrets in git history** (verified).
6. **Graceful-ish degradation** — never returns an empty list (though this causes C-07).

---

## 6. Issue Severity Summary

| Severity | Count | IDs |
|---|---:|---|
| 🔴 Critical | 5 | C-01, C-02, C-03, C-04, C-05 |
| 🟠 High | 3 | C-06, C-07, C-10 |
| 🟡 Medium | 6 | C-08, C-09, C-11, C-12, C-13, C-15 |
| ⚪ Low | 1 | C-14 |
| 🔒 Security (High→Low) | 10 | S-01 → S-10 |
| **Total findings** | **25** | |

---

## 7. Root Cause Analysis

Almost every defect traces to **three root causes**:

1. **Presentation embedded in the data model.** Steps are `"Step N: text"` strings, forcing every consumer to re-parse them (C-11) and making a real data model impossible.
2. **An ambiguous UI↔engine contract.** The engine returns errors, sentinels, and results through one channel (C-07), and receives a pre-formatted prompt it re-parses as prose (C-01, C-02).
3. **Substring heuristics standing in for language understanding.** C-04, C-05, C-06, C-08, C-13 are all the same underlying flaw: `if "x" in s` is not NLP.

Fixing root causes 1 and 2 is a prerequisite for any credible AI feature. This is why the upgrade must begin with a **structural refactor**, not with bolting on an LLM.

---

## 8. Recommended Immediate Actions (before any new feature)

> **No code has been changed.** These are recommendations awaiting approval.

1. **Fix C-02/C-01** — stop injecting metadata into the engine's text; pass structured arguments (`category`, `context`, `file_text`) instead of one formatted string.
2. **Fix C-03** — bundle a Unicode TTF (e.g. DejaVuSans) or switch PDF backend; move export generation to click-time only.
3. **Fix C-01** — make the category actually influence generation (first with rules, later with the LLM).
4. **Fix S-01** — escape user-derived text before HTML interpolation, or render steps with Streamlit native components.
5. **Pin dependencies** and add `.gitignore`, `LICENSE`, and a `tests/` scaffold.
6. **Delete or clearly quarantine dead code** (`index.html`, `style.css`, `assets`) — ✅ *approved in task 0.13 and removed.*

---

**End of Audit Report.**
Companion documents: `CURRENT_ARCHITECTURE.md` · `AI_WORKFLOW_ENGINE_ANALYSIS.md` · `SECURITY_AND_TESTING_REPORT.md` · `PRODUCTION_READINESS_REPORT.md` · `MASTER_UPGRADE_ROADMAP.md`
