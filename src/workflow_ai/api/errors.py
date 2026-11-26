"""Boundary mapping from typed domain exceptions to user-safe JSON envelopes."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..errors import (
    CostCeilingError,
    DocumentError,
    DocumentTooLargeError,
    InputValidationError,
    ProviderError,
    RateLimitError,
    WorkflowError,
    WorkflowValidationError,
)
from ..logging_config import get_logger

logger = get_logger(__name__)

_SAFE_HTTP_MESSAGES = {
    400: "The request could not be understood.",
    401: "Authentication is required.",
    403: "You do not have access to this resource.",
    404: "The requested resource was not found.",
    405: "This method is not allowed.",
    413: "The request body is too large.",
    415: "This content type is not supported.",
}


def make_error_response(
    *,
    request_id: str,
    status: int,
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
) -> JSONResponse:
    """Build the single error shape used by every API failure."""
    content: dict[str, Any] = {
        "error": code,
        "message": message,
        "request_id": request_id,
    }
    if details:
        content["details"] = details
    return JSONResponse(
        status_code=status,
        content=content,
        headers={"X-Request-ID": request_id},
    )


def _workflow_error_response(exc: WorkflowError, request_id: str) -> JSONResponse:
    """Map the typed hierarchy to status codes without leaking internals."""
    if isinstance(exc, InputValidationError):
        status, code = 422, "validation_error"
    elif isinstance(exc, RateLimitError):
        status, code = 429, "rate_limited"
    elif isinstance(exc, CostCeilingError):
        status, code = 402, "cost_ceiling_reached"
    elif isinstance(exc, DocumentTooLargeError):
        status, code = 413, "document_too_large"
    elif isinstance(exc, DocumentError):
        status, code = 422, "document_error"
    elif isinstance(exc, WorkflowValidationError):
        status, code = 502, "workflow_validation_error"
    elif isinstance(exc, ProviderError):
        status, code = 502, "provider_error"
    else:
        status, code = 500, "internal_error"
    return make_error_response(
        request_id=request_id,
        status=status,
        code=code,
        message=exc.user_message,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach all boundary handlers to an application instance."""

    @app.exception_handler(WorkflowError)
    async def workflow_error_handler(request: Request, exc: WorkflowError) -> JSONResponse:
        return _workflow_error_response(exc, getattr(request.state, "request_id", "-"))

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Pydantic's ``input``/``ctx`` fields can contain document text; emit
        # only field locations and messages.
        details = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ())),
                "message": str(error.get("msg", "Invalid value.")),
            }
            for error in exc.errors()
        ]
        return make_error_response(
            request_id=getattr(request.state, "request_id", "-"),
            status=422,
            code="request_validation_error",
            message="Please check your input and try again.",
            details=details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        status = int(exc.status_code)
        return make_error_response(
            request_id=getattr(request.state, "request_id", "-"),
            status=status,
            code="http_error",
            message=_SAFE_HTTP_MESSAGES.get(status, "Request could not be completed."),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log only the exception type: exception text may contain user data.
        logger.error(
            "api.unexpected_error request_id=%s type=%s",
            getattr(request.state, "request_id", "-"),
            type(exc).__name__,
        )
        return make_error_response(
            request_id=getattr(request.state, "request_id", "-"),
            status=500,
            code="internal_error",
            message="Something went wrong. Please try again.",
        )
