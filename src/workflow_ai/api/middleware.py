"""Request-ID, ownership seam, size-limit and latency middleware."""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..logging_config import get_logger, request_id_var, sanitize_request_id
from .errors import make_error_response
from .metrics import Metrics

logger = get_logger(__name__)


def _owner_from_header(value: str | None) -> tuple[bool, str | None]:
    """Validate the auth-ready ``X-Owner-Id`` seam without implementing auth."""
    if value is None or not value.strip():
        return True, None
    owner = value.strip()
    if len(owner) > 128 or any(ord(char) < 32 or ord(char) == 127 for char in owner):
        return False, None
    return True, owner


class RequestContextMiddleware:
    """Add correlation, scoping, abuse and observability at the HTTP edge."""

    def __init__(
        self, app: ASGIApp, *, max_request_bytes: int, metrics: Metrics
    ) -> None:
        self.app = app
        self.max_request_bytes = max_request_bytes
        self.metrics = metrics

    @staticmethod
    def _declared_size(request: Request) -> int | None:
        value = request.headers.get("content-length")
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        request_id = sanitize_request_id(request.headers.get("x-request-id")) or uuid4().hex[:12]
        valid_owner, owner_id = _owner_from_header(request.headers.get("x-owner-id"))
        request.state.request_id = request_id
        request.state.owner_id = owner_id

        token = request_id_var.set(request_id)
        started = perf_counter()
        method = request.method
        path = request.url.path
        status = 500
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started, status
            if message["type"] == "http.response.start":
                response_started = True
                status = int(message["status"])
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            if not valid_owner:
                response = make_error_response(
                    request_id=request_id,
                    status=400,
                    code="invalid_owner_id",
                    message="The X-Owner-Id header is invalid.",
                )
            elif (declared := self._declared_size(request)) is not None and (
                declared > self.max_request_bytes
            ):
                response = make_error_response(
                    request_id=request_id,
                    status=413,
                    code="request_too_large",
                    message="The request body is too large.",
                )
            else:
                await self.app(scope, receive, send_wrapper)
                return

            await response(scope, receive, send_wrapper)
        except Exception as exc:  # final user-safe boundary; logged by type only
            logger.error(
                "api.unhandled request_id=%s type=%s", request_id, type(exc).__name__
            )
            if response_started:
                raise
            response = make_error_response(
                request_id=request_id,
                status=500,
                code="internal_error",
                message="Something went wrong. Please try again.",
            )
            await response(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            template = getattr(route, "path", None)
            if not isinstance(template, str):
                template = path
            self.metrics.record_request(
                method=method,
                path=template,
                status=status,
                latency_ms=(perf_counter() - started) * 1000,
            )
            request_id_var.reset(token)
