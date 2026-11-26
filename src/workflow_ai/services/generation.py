"""Generation orchestration with a bounded degradation ladder.

Flow: rate/cost checks -> primary provider (LLM, with internal repair)
      -> DAG validation -> rule fallback -> typed, user-safe result.

Only lengths, provider names, domains, timings and costs are logged; never
user text or documents.
"""

from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

from ..config import Settings, is_ollama_endpoint
from ..errors import (
    CostCeilingError,
    DocumentAnalysisError,
    DocumentAnalysisUnavailableError,
    InputValidationError,
    ProviderAuthError,
    ProviderConfigError,
    ProviderConnectionError,
    ProviderError,
    ProviderQuotaError,
    ProviderResourceError,
    ProviderTimeoutError,
    RateLimitError,
    WorkflowValidationError,
)
from ..limits import CostTracker, RateLimiter
from ..logging_config import get_logger, request_id_var, sanitize_request_id
from ..models import GenerationRequest, GenerationResult
from ..providers.base import WorkflowProvider
from ..providers.rule import META_REQUEST_MESSAGE, is_meta_workflow_request
from ..validation import validate_generated_workflow


class GenerationService:
    """Coordinate generation, validation, fallback and provenance metadata."""

    def __init__(
        self,
        provider: WorkflowProvider,
        settings: Settings,
        *,
        fallback: WorkflowProvider | None = None,
        logger: logging.Logger | None = None,
        rate_limiter: RateLimiter | None = None,
        cost_tracker: CostTracker | None = None,
    ) -> None:
        self._provider = provider
        self._settings = settings
        self._fallback = fallback
        self._logger = logger or get_logger(__name__)
        self._rate_limiter = rate_limiter or RateLimiter()
        self._cost_tracker = cost_tracker or CostTracker()

    @property
    def provider_name(self) -> str:
        """Name of the primary provider, used by readiness reporting."""
        return self._provider.name

    @staticmethod
    def _capture_usage(provider: WorkflowProvider) -> tuple[int, int, float, str | None, int]:
        """Read optional usage/metadata attributes exposed by LLM providers."""
        tokens_in = int(getattr(provider, "last_tokens_in", 0) or 0)
        tokens_out = int(getattr(provider, "last_tokens_out", 0) or 0)
        cost = float(getattr(provider, "last_cost_usd", 0.0) or 0.0)
        model = getattr(provider, "model", None)
        attempts = int(getattr(provider, "last_attempts", 1) or 1)
        return tokens_in, tokens_out, cost, model, attempts

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate a validated workflow, degrading to rules when needed.

        Raises:
            InputValidationError: bad user input.
            RateLimitError / CostCeilingError: abuse or budget controls.
            ProviderError: primary and fallback both unavailable.
            WorkflowValidationError: fallback produced an invalid graph.
        """
        token = request_id_var.set(sanitize_request_id(request.request_id) or uuid4().hex[:12])
        started = perf_counter()
        result: GenerationResult | None = None
        tokens_in = 0
        tokens_out = 0
        cost = 0.0
        model: str | None = None
        attempts = 1

        self._logger.info(
            "generation.started provider=%s description_chars=%d context_chars=%d",
            self._provider.name,
            len(request.description),
            len(request.additional_context),
        )

        try:
            if request.require_ai and self._provider.name != "llm":
                raise DocumentAnalysisUnavailableError(
                    "An uploaded document requires an AI-backed provider."
                )
            if not request.document_text.strip() and is_meta_workflow_request(request.description):
                raise InputValidationError(
                    "The request names a workflow but does not describe its process.",
                    user_message=META_REQUEST_MESSAGE,
                )
            self._rate_limiter.check(
                request.session_id,
                self._settings.max_requests_per_session,
                self._settings.rate_limit_window_seconds,
            )
            self._cost_tracker.check(self._settings.daily_cost_ceiling_usd)

            warnings: list[str] = []
            degraded = False
            fallback_reason: str | None = None

            try:
                try:
                    workflow = self._provider.generate(request)
                finally:
                    tokens_in, tokens_out, cost, model, attempts = self._capture_usage(
                        self._provider
                    )

                if not workflow.steps:
                    raise WorkflowValidationError(
                        "The generator returned an empty workflow. "
                        "Add concrete actions and try again."
                    )
                validate_generated_workflow(workflow)
            except (ProviderError, WorkflowValidationError) as exc:
                if request.require_ai:
                    if isinstance(exc, ProviderError):
                        if isinstance(exc, ProviderQuotaError):
                            raise DocumentAnalysisError(
                                str(exc),
                                user_message=(
                                    "The AI provider has no available quota or credits for this "
                                    "document analysis. Check provider billing or usage limits, "
                                    "then try again. No offline workflow was created."
                                ),
                            ) from exc
                        if isinstance(exc, ProviderAuthError):
                            raise DocumentAnalysisError(
                                str(exc),
                                user_message=(
                                    "The AI provider rejected its credentials. Check the API key, "
                                    "or leave it blank when using local Ollama. No offline "
                                    "workflow was created."
                                ),
                            ) from exc
                        if isinstance(exc, ProviderConnectionError):
                            if is_ollama_endpoint(self._settings.llm_base_url):
                                message = (
                                    "The app could not reach Ollama. Keep Ollama running and "
                                    "confirm the model is installed. For Docker, use "
                                    "http://host.docker.internal:11434/v1 as LLM_BASE_URL. "
                                    "No offline workflow was created."
                                )
                            else:
                                message = (
                                    "The app could not reach the configured AI endpoint. Check "
                                    "the endpoint URL and network access. No offline workflow "
                                    "was created."
                                )
                            raise DocumentAnalysisError(str(exc), user_message=message) from exc
                        if isinstance(exc, ProviderConfigError):
                            raise DocumentAnalysisError(
                                str(exc),
                                user_message=(
                                    "The AI provider configuration is incomplete. Check the "
                                    "model name and endpoint settings. No offline workflow was "
                                    "created."
                                ),
                            ) from exc
                        if isinstance(exc, ProviderResourceError):
                            raise DocumentAnalysisError(
                                str(exc),
                                user_message=(
                                    "Ollama ran out of memory while analyzing this document. "
                                    "Try a smaller local model or a shorter document, then retry. "
                                    "No offline workflow was created."
                                ),
                            ) from exc
                        if isinstance(exc, ProviderTimeoutError):
                            if is_ollama_endpoint(self._settings.llm_base_url):
                                message = (
                                    "The local Ollama model took too long to analyze this "
                                    "document. Try a smaller model or run this model on a "
                                    "faster machine, then retry. No offline workflow was created."
                                )
                            else:
                                message = (
                                    "The AI provider took too long to analyze this document. "
                                    "Try again or check the provider's availability. "
                                    "No offline workflow was created."
                                )
                            raise DocumentAnalysisError(str(exc), user_message=message) from exc
                        raise DocumentAnalysisError(
                            str(exc),
                            user_message=(
                                "The AI model could not return a complete, valid workflow from "
                                "this document. Try a shorter document focused on one process, "
                                "or add a brief describing the expected outcome, then retry. "
                                "No offline workflow was created."
                            ),
                        ) from exc
                    raise
                if self._fallback is None:
                    raise
                fallback_reason = exc.user_message
                self._logger.warning(
                    "generation.degraded reason=%s provider=%s",
                    type(exc).__name__,
                    self._provider.name,
                )
                workflow = self._fallback.generate(request)
                validate_generated_workflow(workflow)
                degraded = True
                warnings.append(fallback_reason)

            # Surface the provider's own caveats (e.g. "nothing detected") at
            # the UI boundary without leaking them into logs or exports.
            warnings.extend(workflow.missing_information)

            self._cost_tracker.record(cost)

            latency_ms = (perf_counter() - started) * 1000
            self._logger.info(
                "generation.completed provider=%s model=%s domain=%s steps=%d "
                "latency_ms=%.1f cost_usd=%.6f degraded=%s",
                self._provider.name,
                model,
                workflow.domain,
                len(workflow.steps),
                latency_ms,
                cost,
                degraded,
            )

            actual_provider = self._provider.name
            if degraded and self._fallback is not None:
                actual_provider = self._fallback.name

            result = GenerationResult(
                workflow=workflow,
                provider=actual_provider,
                requested_provider=self._provider.name,
                model=model if not degraded else None,
                degraded=degraded,
                fallback_reason=fallback_reason,
                warnings=warnings,
                latency_ms=latency_ms,
                attempts=attempts + (1 if degraded else 0),
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                estimated_cost_usd=cost,
            )
        except (
            InputValidationError,
            ProviderError,
            WorkflowValidationError,
            RateLimitError,
            CostCeilingError,
        ):
            raise
        except Exception as exc:
            self._logger.exception("generation.failed provider=%s", self._provider.name)
            raise ProviderError("Workflow generation failed. Please try again.") from exc
        finally:
            request_id_var.reset(token)

        assert result is not None  # populated on every non-raising path
        return result
