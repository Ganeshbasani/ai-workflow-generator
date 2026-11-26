"""Typed error hierarchy so the UI boundary can map errors to safe messages."""

from __future__ import annotations


class WorkflowError(Exception):
    """Base class for all application errors."""

    user_message = "Something went wrong. Please try again."


class InputValidationError(WorkflowError):
    """User input is missing, malformed, or exceeds a configured limit."""

    def __init__(self, message: str, *, user_message: str | None = None) -> None:
        super().__init__(message)
        # Keep the internal diagnostic separate from the safe user-facing text.
        self.user_message = user_message or "Please check your input and try again."

    user_message = "Please check your input and try again."


class DocumentError(WorkflowError):
    """An uploaded document could not be processed."""

    def __init__(self, message: str, user_message: str | None = None) -> None:
        super().__init__(message)
        self.user_message = user_message or message


class DocumentTooLargeError(DocumentError):
    """Upload exceeds the configured byte or page limit."""


class ProviderError(WorkflowError):
    """A workflow provider failed (timeout, quota, invalid response, ...)."""

    user_message = "The AI provider is unavailable. Trying the offline engine."


class ProviderConfigError(ProviderError):
    """The provider is missing required configuration (e.g. an API key)."""

    user_message = "AI generation is not configured. Offline mode is active."


class DocumentAnalysisUnavailableError(ProviderConfigError):
    """Document analysis cannot silently degrade to keyword extraction."""

    user_message = (
        "Document analysis needs a connected AI model. Connect Ollama or an API provider, "
        "test the connection, then upload the document again."
    )


class DocumentAnalysisError(ProviderError):
    """The model failed to analyze a document; do not imply offline fallback."""

    def __init__(self, message: str, *, user_message: str | None = None) -> None:
        super().__init__(message)
        self.user_message = user_message or (
            "The AI could not analyze this document. Check the provider connection and document "
            "text, then try again. No offline workflow was created."
        )


class ProviderTimeoutError(ProviderError):
    """The provider request exceeded the configured timeout."""


class ProviderResourceError(ProviderError):
    """The local provider could not allocate enough resources for inference."""

    user_message = (
        "Ollama ran out of memory while loading the model. Close other memory-heavy apps or "
        "switch LLM_MODEL to a smaller local model, then try again."
    )


class ProviderConnectionError(ProviderError):
    """The configured provider endpoint could not be reached."""


class ProviderQuotaError(ProviderError):
    """The provider rejected the request due to quota or rate limits."""


class ProviderAuthError(ProviderError):
    """The provider rejected the credentials."""


class WorkflowValidationError(WorkflowError):
    """A provider returned a structurally invalid workflow graph."""

    user_message = "The generated workflow failed validation."


class RateLimitError(WorkflowError):
    """Too many requests in the current session window."""

    def __init__(self, message: str = "Session rate limit reached.") -> None:
        super().__init__(message)
        self.user_message = "Too many requests. Please wait a moment and try again."


class CostCeilingError(WorkflowError):
    """The daily AI spend ceiling has been reached."""

    def __init__(self, message: str = "Daily AI cost ceiling reached.") -> None:
        super().__init__(message)
        self.user_message = (
            "The daily AI budget has been reached. Offline generation is still available."
        )
