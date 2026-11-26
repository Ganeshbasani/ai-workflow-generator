# 🧠 AI WORKFLOW ENGINE ANALYSIS

**Subject:** Deep dive into `workflow.py` (94 lines) + design for a genuine LLM-powered successor.
**Method:** Static code review **and** dynamic execution of the existing engine against 20+ adversarial inputs.
**Status:** Read-only. No code modified.
**Date:** 2026-01-19

---

## 1. What the Engine Actually Is

Despite the README's framing ("Rule-Based Intelligent Workflow Engine", "Designed to simulate AI-style reasoning"), the engine is a **flat keyword-substring classifier**:

```python
for sentence in sentences:
    if any(w in s for w in ["student", "admission", ...]):     # domain gate
        if "apply" in s: raw_steps.append("Process student admission")   # keyword → canned string
```

- **No language understanding.** No parsing, no semantics, no context window, no training data.
- **No "AI"** in any technical sense — deterministic string containment tests.
- **Output is canned prose**, selected from ~35 hard-coded templates.

This is not a criticism of the *approach* for a prototype — keyword rules are a legitimate, fast, free, and fully offline baseline. The problem is that the project **presents it as AI**, and it demonstrably fails on ordinary inputs.

---

## 2. Empirical Test Results

All results below were produced by executing `workflow.generate_workflow` as-is.

### 2.1 Inputs that work (the happy paths)

| Input | Output | Verdict |
|---|---|---|
| `Customer registers. Places order. Makes payment. Generate invoice.` | Register new client/customer → Process order request → Process payment transaction → Generate tax invoice | ✅ Correct & ordered |
| `A patient books an appointment, gets diagnosed, receives a prescription and is discharged with a bill.` | Schedule doctor appointment → Perform medical diagnosis → Process discharge and final billing | ✅ Mostly correct (misses `Issue medical prescription`) |

**Observation:** the engine performs acceptably on **short, single-domain, keyword-rich, well-formed** descriptions. That is a narrow but real band of usability.

### 2.2 Inputs that fail (verified)

| # | Input | Actual output | Defect |
|---|---|---|---|
| 1 | *(any vague text, exact app prompt)* | **`Step 1: Category: hospitals`** | **C-02** metadata leak |
| 2 | `Approve — the plan` | `['Step 1: Category: hospitals']` (via app) → PDF crash | **C-03** |
| 3 | `Onboard a new employee, assign a mentor, schedule training, then run a probation review after 90 days.` | **1 step**: `Register new client/customer` | 5-step process → 1 wrong step |
| 4 | `When payment fails, retry twice; otherwise ship the order and send an email receipt.` | 5 flat steps, **no retry, no branch** | No condition/loop modeling |
| 5 | `send the parcel` | includes **`Complete workflow process`** | `"end" in "send"` |
| 6 | `render the page` | includes **`Complete workflow process`** | `"end" in "render"` |
| 7 | `extend the subscription` | includes **`Complete workflow process`** | `"end" in "extend"` |
| 8 | `review the listing` | **`Schedule property viewing`** | `"view" in "review"` |
| 9 | `verification of records` | raw echo (no match) | no stemming |
| 10 | `Pay the invoice for the server.` | `Generate tax invoice` + `Monitor server health` | semantic nonsense |
| 11 | `Register the customer ... patient appointment ... teacher ... software bug ... rental property.` | 5 contradictory steps, **wrong order** | **C-05, C-06** |
| 12 | `The quick brown fox jumps over the lazy dog.` | echoed as a "workflow step" | false success |
| 13 | 500× full business process | **3 steps** | **C-08** dedup collapse |
| 14 | `A hospital should admit patients, run tests, and if results are abnormal escalate to ICU, else discharge.` | 3 steps, **escalation branch lost** | no decision branches |
| 15 | `Do the thing.` | `Step 1: Do the thing` | meaningless output presented as success |

### 2.3 Accuracy summary

| Category | Approx. pass rate (of tested inputs) |
|---|---|
| Short, single-domain, keyword-rich | **~90%** |
| Multi-clause / multi-domain | **~10%** |
| Vague or abstract language | **~0%** (echoes or leaks metadata) |
| Conditional / branch / loop descriptions | **0%** — not representable |
| Long / repetitive inputs | **0%** — collapsed by dedup |

**Honest verdict:** the engine is a *keyword template picker*. Its effective accuracy on realistic, unconstrained user input is **low**, and its ceiling is bounded by the number of hand-written rules.

---

## 3. Limitations of Keyword-Based Processing (structural)

| Limitation | Why it matters | Evidence |
|---|---|---|
| **Substring matching** | `x in s` matches inside longer words, in both directions | `send`/`render`/`extend` → `end`; `review` → `view`; `verification` ≠ `verify` |
| **No morphology** | No stemming/lemmatization → misses inflections | `verification`, `verified`, `verifies` all miss `verify` |
| **No word boundaries** | No `\b` anchors anywhere | C-04 table |
| **No negation handling** | "do **not** process payment" → `Process payment transaction` | rule fires on keyword regardless of polarity |
| **No coreference / context** | "it", "then", "they" resolve to nothing | step 4 above |
| **No ordering semantics** | "then", "after", "before", "finally" ignored | C-06 |
| **No conditional/loop semantics** | `if/else/retry/until/parallel` not representable | steps 4, 14 |
| **No role/owner extraction** | Cannot say *who* performs a step | model limitation |
| **No confidence** | Every output is equally certain, including garbage | step 12, 15 |
| **Fixed rule-block order** | Output order ≠ input order | C-06 |
| **Global dedup** | Legitimate repetition destroyed | C-08 |
| **Domain gates not exclusive** | All 6 blocks run on every sentence | C-05 |
| **Category never consulted** | UI's primary control is inert | C-01 |
| **Fragile tokenizer** | Splits on every `.` `?` `!`; ignores `;` | C-13 |
| **Flat `list[str]` output** | Cannot express a graph | model limitation |
| **Scale ceiling** | More domains = more nested `if`s in one 94-line function | maintainability |

**Fundamental conclusion:** these are not bugs to patch — they are **properties of the approach**. Adding more keywords improves one case and worsens another (false positives grow monotonically with vocabulary size). A structural replacement is required.

---

## 4. Design: Genuine LLM-Powered Generation

### 4.1 Recommended architecture

```
User input + category + optional document
              │
              ▼
   ┌─────────────────────┐
   │ GenerationService    │  validates input, enforces limits,
   └──────────┬──────────┘  builds provider-agnostic request
              │
              ▼
   ┌─────────────────────┐     ┌──────────────────────────┐
   │ WorkflowProvider     │◄────│ Provider registry        │
   │  (Protocol)          │     │  1. LLMProvider  (primary)│
   └──────────┬──────────┘     │  2. RuleProvider (fallback)│
              │                └──────────────────────────┘
              ▼
   ┌─────────────────────┐
   │ Schema validation    │  Pydantic parse; on failure →
   │ + repair loop        │  structured re-prompt (max 2 retries)
   └──────────┬──────────┘
              ▼
        Workflow (structured model)
              │
    ┌─────────┼──────────┬───────────┐
    ▼         ▼          ▼           ▼
  Diagram   Exports    Persistence  Editor / Tracking
```

### 4.2 Structured output — the core requirement

Generation must return a **typed object**, not strings:

```python
class StepType(str, Enum):
    task = "task"
    decision = "decision"
    approval = "approval"
    notification = "notification"
    start = "start"
    end = "end"

class WorkflowStep(BaseModel):
    id: str                     # stable, e.g. "s1"
    title: str
    description: str
    step_type: StepType
    owner_role: str | None      # "HR Officer", "Payment Gateway"
    depends_on: list[str]       # DAG edges → enables diagrams + ordering
    condition: str | None       # for decision nodes: "payment_status == 'failed'"
    on_true: str | None         # branch target
    on_false: str | None
    estimated_duration: str | None
    system_hint: str | None     # suggested tool/integration

class Workflow(BaseModel):
    id: str
    title: str
    domain: str
    summary: str
    steps: list[WorkflowStep]
    assumptions: list[str]
    risks: list[str]
    missing_information: list[str]
```

**Why this specific shape:**
- `depends_on` makes the workflow a **DAG** → diagrams, topological ordering, and execution tracking all fall out for free.
- `condition` / `on_true` / `on_false` represent **decision branches** — the capability the current engine completely lacks.
- `assumptions` / `missing_information` let the AI be **honest about uncertainty** instead of fabricating confidence — a strong interview talking point.
- Stable `id`s make editing and status tracking possible.

### 4.3 Prompting strategy

```
SYSTEM:
  You are a business/workflow architect.
  Output ONLY JSON matching this JSON Schema (embedded).
  Rules:
   - Every step must have a unique id and valid depends_on references.
   - Use decision nodes for genuine branches; do not invent branches.
   - Never fabricate regulatory/legal steps — list them in missing_information.
   - Prefer 5–15 steps. Be concrete and actionable.
   - Match the requested domain's vocabulary.

USER:
  Domain: {category}
  Goal: {user_input}
  Context from document (may be empty): {file_text, truncated to N chars}
```

**Key techniques worth demonstrating in interviews:**
1. **Schema-constrained decoding** — ask the provider for JSON mode / structured output so the model *cannot* emit prose.
2. **Validate → repair → retry** — parse with Pydantic; on `ValidationError`, send the error back to the model with the invalid output and request a corrected version (max 2 attempts).
3. **Deterministic fallback** — on timeout, quota, network, or persistent invalid output → call `RuleProvider` (the existing engine, cleaned up) and clearly badge the result as *"Offline mode — rule-based"*.
4. **Graceful degradation ladder:** `LLM → LLM+repair → Rule engine → explicit, human-readable error`. Never show raw exceptions; never silently return garbage.

### 4.4 Honest assessment of what the LLM adds

| Capability | Rules (today) | LLM |
|---|---|---|
| Free / offline / instant | ✅ | ❌ (needs API, costs money, ~1–4 s) |
| Deterministic & reproducible | ✅ | ❌ (needs temperature=0 + seed) |
| Understands vague language | ❌ | ✅ |
| Multi-domain isolation | ❌ | ✅ |
| Decision branches & conditions | ❌ | ✅ |
| Ordering / dependencies | ❌ | ✅ |
| Roles, durations, risks | ❌ | ✅ |
| Explainable rationale | ❌ | ✅ |
| Immune to prompt injection | ✅ | ⚠️ needs hardening |
| Latency | ~10 ms | ~1–4 s |

**Design conclusion:** keep **both**. Rules are the free, instant, offline safety net; the LLM is the quality layer. This hybrid is defensible, cheap, and demonstrates real engineering judgment — which is exactly what interviewers look for.

---

## 5. Anti-Prompt-Injection Hardening (must-have with an LLM)

User text and uploaded documents are **untrusted input**, not instructions.

| Risk | Mitigation |
|---|---|
| Document says *"ignore previous instructions"* | Delimit untrusted content (`<<<DOC>>>...<<<END>>>`); system prompt states untrusted content is data only |
| Output containing unexpected instructions | Validate against schema; reject extraneous keys |
| Cost/DoS via huge prompts | Hard character caps on `user_input` (e.g. 4,000) and document (e.g. 20,000); reject over-limit with a friendly message |
| Rate abuse on public app | Per-session token bucket; daily budget cap |
| Secret exfiltration | Keys only in `st.secrets` / env; never in prompts or logs |
| Log injection | Structured logging with escaping; never log raw document bodies at INFO |

---

## 6. Evaluation — the differentiator

Most prototypes skip evaluation entirely. Adding a small **golden set** is high-value and low-cost:

```
tests/fixtures/golden/
  business_order.json      # input + expected structure (step count range,
  hospital_intake.json     #   required domain keywords, must-have steps,
  vague_input.json         #   must-NOT-have steps, branch presence)
```

**Metrics to track (start simple):**
| Metric | How |
|---|---|
| Schema validity rate | % of responses passing Pydantic on 1st / 2nd / 3rd attempt |
| Domain accuracy | required domain keywords present; foreign-domain steps absent |
| Structural integrity | all `depends_on` resolve; no cycles; exactly one `start`, ≥1 `end` |
| Step-count sanity | within configured bounds |
| Latency p50/p95 | per provider |
| Cost per generation | tokens × price |
| Fallback rate | % of requests served by `RuleProvider` |

Presenting **measured** numbers (even on a 20-case golden set) is a significant differentiator in AI engineering interviews.

---

## 7. Preserving & Rehabilitating the Existing Engine

`workflow.py` should not be deleted — it becomes **`RuleProvider`**, the fallback layer.

**Minimum rehabilitation (still no LLM required):**
1. Pass `category` as a real argument → finally make the dropdown work (C-01).
2. Never inject UI labels into the engine text (C-02).
3. Tokenize with word boundaries: `\b(?:apply|admission)\b` (C-04).
4. Enable **one** domain block per request based on `category` + a domain-scoring function (C-05).
5. Sort output by **sentence index**, not rule-block order (C-06).
6. Return a structured `Workflow` object; move "no results" to an exception/result type (C-07).
7. Dedup **per phase** or by `(step, context)`, not globally (C-08).
8. Add basic stemming (`PorterStemmer` or a tiny suffix-stripper) (C-04).

This yields a respectable offline baseline *before* any LLM work — a natural Phase 1 deliverable.

---

## 8. Summary

| Question | Answer |
|---|---|
| Is the current engine AI? | **No** — deterministic substring keyword matching |
| Does it work at all? | **Yes**, for short, single-domain, keyword-rich inputs (~90%) |
| Does it work on realistic input? | **No** — multi-domain, vague, and conditional inputs largely fail |
| Can it be patched into an AI system? | **No** — limitations are inherent to the approach |
| Should it be deleted? | **No** — repurpose as the deterministic fallback provider |
| What is the single highest-value change? | **Structured (Pydantic) output from an LLM, with schema validation + repair + fallback** |
| What will impress an interviewer most? | Schema-constrained generation, a graceful degradation ladder, and a **measured evaluation harness** |

**Next:** see `MASTER_UPGRADE_ROADMAP.md` for sequencing, and `SECURITY_AND_TESTING_REPORT.md` for the LLM-specific security and test strategy.
