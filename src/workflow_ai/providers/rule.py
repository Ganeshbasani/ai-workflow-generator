"""Deterministic offline provider — the stabilised rule engine as a provider."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..config import Settings
from ..errors import InputValidationError
from ..models import GenerationRequest, StepType, Workflow, WorkflowStep
from .base import WorkflowProvider

CATEGORY_TO_DOMAIN = {
    "educational institutes": "education",
    "business organizations": "business",
    "real estate": "real_estate",
    "software industries": "software",
    "software projects": "software",
    "hospitals": "hospital",
}

_ALIASES = {
    "verify": "verify",
    "verified": "verify",
    "verifies": "verify",
    "verification": "verify",
    "enrolled": "enroll",
    "enrolling": "enroll",
    "enrollment": "enroll",
    "applied": "apply",
    "application": "apply",
    "applications": "apply",
    "applicant": "apply",
    "appointments": "appointment",
    "booked": "book",
    "booking": "book",
    "patients": "patient",
    "doctors": "doctor",
    "diagnosed": "diagnose",
    "diagnosis": "diagnose",
    "prescription": "prescribe",
    "prescriptions": "prescribe",
    "discharged": "discharge",
    "orders": "order",
    "invoices": "invoice",
    "payments": "payment",
    "failed": "fail",
    "failure": "fail",
    "failing": "fail",
    "shipments": "ship",
    "shipped": "ship",
    "deliveries": "delivery",
    "listing": "list",
    "listings": "list",
    "viewing": "view",
    "viewings": "view",
    "tenants": "tenant",
    "properties": "property",
    "rental": "rent",
    "rentals": "rent",
    "agreements": "agreement",
    "contracts": "contract",
    "exams": "exam",
    "tests": "test",
    "results": "result",
    "grades": "grade",
    "courses": "course",
    "students": "student",
    "teachers": "teacher",
    "requirements": "requirement",
    "features": "feature",
    "bugs": "bug",
    "developers": "developer",
    "development": "develop",
    "deployed": "deploy",
    "deployment": "deploy",
    "releases": "release",
    "reviews": "review",
    "servers": "server",
    "backups": "backup",
    "users": "user",
    "authenticate": "auth",
    "authentication": "auth",
    "authorized": "auth",
    "emails": "email",
    "notifications": "notification",
}

_WORD_RE = re.compile(r"[a-z0-9]+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_IF_RE = re.compile(r"^if\s+(.+)$", re.IGNORECASE)
_ELSE_RE = re.compile(r"\s+(?:otherwise|else)\s+", re.IGNORECASE)
_SEQUENCE_RE = re.compile(
    r"\s+(?:and\s+then|then|after that|subsequently|finally|next)\s+", re.IGNORECASE
)
_LEADING_TRANSITION_RE = re.compile(
    r"^(?:first(?:ly)?|next|then|after that|subsequently|finally|lastly)[,:]?\s+",
    re.IGNORECASE,
)
_STOP_CONDITION_WORDS = {"a", "an", "the", "is", "are", "was", "were", "not", "no"}
_META_REQUEST_WORDS = {
    "please", "create", "generate", "build", "design", "make", "draw", "map",
    "me", "my", "a", "an", "the", "ai", "workflow", "workflows", "process",
    "flowchart", "generator", "for", "of", "this", "that",
}
META_REQUEST_MESSAGE = (
    "Describe the real process by adding at least one clear action and its object, "
    "then say who does what and how it ends. "
    "A request such as 'Create a workflow' alone is not enough to build accurate steps."
)


def _normalise(word: str) -> str:
    if word in _ALIASES:
        return _ALIASES[word]
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


@dataclass(frozen=True)
class _Domain:
    key: str
    gates: tuple[str, ...]


_DOMAINS: tuple[_Domain, ...] = (
    _Domain(
        "education",
        ("student", "admission", "course", "exam", "teacher", "school"),
    ),
    _Domain(
        "business",
        ("customer", "order", "payment", "invoice", "client", "employee"),
    ),
    _Domain(
        "real_estate",
        ("property", "house", "tenant", "buyer", "rent", "list"),
    ),
    _Domain(
        "hospital",
        ("patient", "doctor", "appointment", "medical", "health", "ward"),
    ),
    _Domain(
        "software",
        ("software", "code", "sprint", "feature", "bug", "developer", "git"),
    ),
    _Domain(
        "infrastructure",
        ("user", "login", "server", "database", "cloud", "auth"),
    ),
)


def _tokenise(sentence: str) -> set[str]:
    return {_normalise(token) for token in _WORD_RE.findall(sentence.lower())}


def is_meta_workflow_request(description: str) -> bool:
    """Reject requests to create a workflow that never describe the process."""
    words = _WORD_RE.findall(description.lower())
    return bool(words) and not (set(words) - _META_REQUEST_WORDS)


def _clean_phrase(value: str) -> str:
    """Keep the user's action wording while removing sequencing scaffolding."""
    cleaned = _LEADING_TRANSITION_RE.sub("", value.strip()).strip(" ,;:")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned.rstrip(".!? ")


def _workflow_title(first_action: str) -> str:
    """Build a short, readable title from the first described process action."""
    title = _clean_phrase(first_action)
    trigger = re.match(
        r"^(?:when|once|after|before)\b[^,]+,\s*(.+)$", title, re.IGNORECASE
    )
    if trigger:
        title = trigger.group(1).strip()
    title = re.split(r"\s+(?:and then|then|and|or)\s+|[,;]", title, maxsplit=1)[0]
    title = title.strip(" ,;:")
    if not title:
        return "Workflow draft"
    title = title[0].upper() + title[1:]
    if len(title) > 64:
        shortened = title[:64].rsplit(" ", 1)[0].strip()
        title = shortened or title[:64]
    if len(title.split()) == 1 and not title.lower().endswith("workflow"):
        title = f"{title} workflow"
    return title


def _sequence_parts(sentence: str) -> list[str]:
    """Split only explicit sequence connectors; keep compound actions intact."""
    if sentence.lstrip().lower().startswith("if "):
        return [sentence.strip()]
    return [part.strip(" ,;:") for part in _SEQUENCE_RE.split(sentence) if part.strip(" ,;:")]


def _conditional_parts(sentence: str) -> tuple[str, str, str | None] | None:
    """Split a written if/else clause without changing its action wording."""
    match = _IF_RE.match(sentence.strip())
    if match is None:
        return None
    body = match.group(1).strip().rstrip(".!?")
    split = _ELSE_RE.search(body)
    no_action = None
    if split:
        no_action = body[split.end() :].strip(" ,;:")
        body = body[: split.start()].strip(" ,;:")

    separator = re.search(r",\s*|\s+then\s+|;\s*", body, re.IGNORECASE)
    if separator is None:
        return None
    condition = body[: separator.start()].strip(" ,;:")
    yes_action = body[separator.end() :].strip(" ,;:")
    if not condition or not yes_action:
        return None
    return condition, yes_action, no_action or None


def _condition_key(condition: str) -> tuple[str, bool]:
    """Normalize a condition enough to pair explicit positive/negative paths."""
    words = [_normalise(word) for word in _WORD_RE.findall(condition.lower())]
    negative = "not" in words or "no" in words or "unless" in words
    key = " ".join(word for word in words if word not in _STOP_CONDITION_WORDS)
    return key, negative


def _binary_outcome(condition: str) -> bool | None:
    """Recognize explicit yes/no labels without interpreting other conditions."""
    words = [_normalise(word) for word in _WORD_RE.findall(condition.lower())]
    if words in (["yes"], ["true"]):
        return True
    if words in (["no"], ["false"]):
        return False
    return None


def _decision_condition_from_source(source: str) -> str | None:
    """Reuse a stated decision criterion before pairing explicit yes/no paths."""
    match = re.search(
        r"\b(?:decid\w*|determin\w*|check\w*|confirm\w*|verif\w*|assess\w*|evaluat\w*)"
        r"\s+(?:whether|if)\s+(.+?)(?:[.!?]|$)",
        source,
        re.IGNORECASE,
    )
    return _clean_phrase(match.group(1)) if match else None


def _step_type_for(action: str) -> StepType:
    """Infer only a visible BPMN-style kind from explicit action vocabulary."""
    words = _tokenise(action)
    if words & {"start", "begin", "receive", "arrive", "submit"}:
        return StepType.start
    if words & {"complete", "finish", "end", "close", "deliver"}:
        return StepType.end
    if words & {"approve", "authorize", "signoff"}:
        return StepType.approval
    if words & {"notify", "email", "message", "send"}:
        return StepType.notification
    return StepType.task


def _decision_title(condition: str) -> str:
    """Create a short label from the condition without adding a new rule."""
    phrase = _clean_phrase(condition)
    if phrase.lower().startswith(("is ", "are ", "does ", "has ", "can ", "was ")):
        return phrase.rstrip("?") + "?"
    return f"Decision: {phrase.rstrip('?')}"


def _select_domain(sentences: tuple[set[str], ...], category: str) -> str | None:
    if not sentences:
        return None
    all_words: set[str] = set()
    for words in sentences:
        all_words.update(words)

    scores: dict[str, float] = {
        domain.key: sum(1 for gate in domain.gates if gate in all_words) for domain in _DOMAINS
    }
    preferred = CATEGORY_TO_DOMAIN.get(category.strip().lower())
    if preferred in scores:
        scores[preferred] += 0.5

    best = max(scores, key=lambda key: scores[key])
    return best if scores[best] > 0 else None


class RuleProvider:
    """Offline, deterministic provider. Also used as the LLM fallback."""

    name = "rule"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate(self, request: GenerationRequest) -> Workflow:
        if not request.description.strip() and not request.additional_context.strip():
            raise InputValidationError("Please enter a valid workflow description.")
        if is_meta_workflow_request(request.description):
            raise InputValidationError(
                "The request names a workflow but does not describe its process.",
                user_message=META_REQUEST_MESSAGE,
            )
        if len(request.description) > self._settings.max_input_chars:
            raise InputValidationError(
                f"Description is too long (maximum {self._settings.max_input_chars:,} characters)."
            )

        context = request.additional_context[: self._settings.max_context_chars]
        sentences = [
            segment
            for part in _SENTENCE_RE.split(request.description.strip())
            if part.strip()
            for segment in _sequence_parts(part.strip())
        ]
        if not sentences or len(_WORD_RE.findall(" ".join(sentences))) < 2:
            raise InputValidationError(
                "The brief is too short to contain a process action.",
                user_message="Add at least one clear action and its object to generate a workflow.",
            )

        sentence_tokens = tuple(_tokenise(part) for part in sentences)
        context_tokens = _tokenise(context) if context else set()
        domain_evidence = (*sentence_tokens, context_tokens) if context_tokens else sentence_tokens
        domain_key = _select_domain(domain_evidence, request.category) or "general"

        steps: list[WorkflowStep] = []
        frontier: list[str] = []
        warnings = [
            "Offline draft: actions keep the wording from your description. "
            "Review inferred branches before using this workflow."
        ]

        def add_step(
            title: str,
            *,
            source: str,
            step_type: StepType = StepType.task,
            dependencies: list[str] | None = None,
            condition: str | None = None,
            on_true: str | None = None,
            on_false: str | None = None,
        ) -> str | None:
            if len(steps) >= 20:
                return None
            step_id = f"s{len(steps) + 1}"
            steps.append(
                WorkflowStep(
                    id=step_id,
                    title=title[:200],
                    description="" if title == _clean_phrase(source) else source[:4_000],
                    step_type=step_type,
                    depends_on=list(frontier if dependencies is None else dependencies),
                    condition=condition,
                    on_true=on_true,
                    on_false=on_false,
                    rationale=f"Source statement: {source[:1_000]}",
                )
            )
            return step_id

        def add_branch(condition: str, yes_action: str, no_action: str | None, source: str) -> bool:
            nonlocal frontier
            required = 3 if no_action else 2
            if len(steps) + required > 20:
                return False
            decision_id = add_step(
                _decision_title(condition),
                source=source,
                step_type=StepType.decision,
                condition=condition,
            )
            if decision_id is None:
                return False
            yes_id = add_step(
                _clean_phrase(yes_action),
                source=yes_action,
                step_type=_step_type_for(yes_action),
                dependencies=[decision_id],
            )
            no_id = (
                add_step(
                    _clean_phrase(no_action),
                    source=no_action,
                    step_type=_step_type_for(no_action),
                    dependencies=[decision_id],
                )
                if no_action
                else None
            )
            decision = steps[steps.index(next(step for step in steps if step.id == decision_id))]
            decision.on_true = yes_id
            decision.on_false = no_id
            frontier = [step_id for step_id in (yes_id, no_id) if step_id]
            return True

        index = 0
        while index < len(sentences) and len(steps) < 20:
            sentence = sentences[index]
            conditional = _conditional_parts(sentence)
            if conditional is not None:
                condition, yes_action, no_action = conditional
                outcome = _binary_outcome(condition)
                if outcome is not None and not no_action and index + 1 < len(sentences):
                    opposite = _conditional_parts(sentences[index + 1])
                    opposite_outcome = _binary_outcome(opposite[0]) if opposite else None
                    if (
                        opposite is not None
                        and opposite[2] is None
                        and opposite_outcome is not None
                        and opposite_outcome is not outcome
                    ):
                        previous = next(
                            (step for step in steps if step.id == frontier[-1]), None
                        ) if frontier else None
                        previous_source = (previous.rationale or previous.title) if previous else ""
                        decision_condition = _decision_condition_from_source(previous_source)
                        if not decision_condition:
                            decision_condition = (
                                f"Outcome of {previous.title}" if previous else "Previous step outcome"
                            )
                            warnings.append(
                                "A yes/no path had no explicit decision criterion. "
                                "Confirm the outcome condition before using this workflow."
                            )
                        true_action = yes_action if outcome else opposite[1]
                        false_action = opposite[1] if outcome else yes_action
                        if add_branch(
                            decision_condition,
                            true_action,
                            false_action,
                            f"{sentence} {sentences[index + 1]}",
                        ):
                            index += 2
                            continue
                if no_action:
                    if add_branch(condition, yes_action, no_action, sentence):
                        index += 1
                        continue
                else:
                    key, negative = _condition_key(condition)
                    paired = None
                    for candidate_index in range(index + 1, min(index + 2, len(sentences))):
                        candidate = _conditional_parts(sentences[candidate_index])
                        if candidate is None or candidate[2] is not None:
                            continue
                        candidate_key, candidate_negative = _condition_key(candidate[0])
                        if key and key == candidate_key and negative != candidate_negative:
                            paired = (candidate_index, candidate, candidate_negative)
                            break
                    if paired is not None:
                        candidate_index, candidate, candidate_negative = paired
                        positive_condition = candidate[0] if negative else condition
                        true_action = candidate[1] if negative else yes_action
                        false_action = yes_action if negative else candidate[1]
                        if add_branch(
                            positive_condition,
                            true_action,
                            false_action,
                            f"{sentence} {sentences[candidate_index]}",
                        ):
                            sentences[candidate_index] = ""
                            index += 1
                            continue
                    elif add_branch(condition, yes_action, None, sentence):
                        warnings.append(
                            f"No alternate path was described for '{condition}'. "
                            "Add its other outcome."
                        )
                        index += 1
                        continue

            action = _clean_phrase(sentence)
            if action:
                step_id = add_step(
                    action,
                    source=sentence,
                    step_type=_step_type_for(action),
                )
                if step_id:
                    frontier = [step_id]
            index += 1

        if len(steps) >= 20 and len(sentences) > index:
            warnings.append(
                "The offline draft reached its 20-step limit; review the remaining source text."
            )
        if not steps:
            raise InputValidationError(
                "No process actions could be extracted from the description.",
                user_message=(
                    "I couldn't find an action in that description. Add the people involved, "
                    "what they do, and the outcome."
                ),
            )

        first_action = _clean_phrase(sentences[0]) or request.category
        title = _workflow_title(first_action)
        return Workflow(
            title=title,
            domain=domain_key,
            summary=(
                f"{len(steps)} ordered steps and explicit decision paths "
                "from your process description."
            ),
            steps=steps,
            assumptions=[
                "Roles, timings, and systems were left blank because the description "
                "did not specify them."
            ],
            risks=[
                "This offline draft uses deterministic text rules. Confirm each action "
                "and decision path before execution."
            ],
            missing_information=warnings,
            suggested_improvements=[
                "Add owners and service times if your team needs operational accountability.",
                "Add the alternate outcome for any decision that has only one described path.",
            ],
        )


# Compile-time structural conformance check.
_PROVIDER_CONTRACT: type[WorkflowProvider] = RuleProvider
