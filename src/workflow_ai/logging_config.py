"""Logging setup with a per-request correlation ID.

Only the package logger is configured; the root logger and third-party loggers
are left alone so importing the library never changes host application logging.
"""

from __future__ import annotations

import logging
import re
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_UNSAFE_REQUEST_ID = re.compile(r"[^A-Za-z0-9._:-]")
_CONFIGURATION_DONE = False
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] [request_id=%(request_id)s] %(message)s"
PACKAGE_LOGGER = "workflow_ai"


class RequestIdFilter(logging.Filter):
    """Attach the current correlation id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the ``workflow_ai`` logger once."""
    global _CONFIGURATION_DONE
    if _CONFIGURATION_DONE:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(RequestIdFilter())

    package_logger = logging.getLogger(PACKAGE_LOGGER)
    package_logger.setLevel(level)
    package_logger.addHandler(handler)
    package_logger.propagate = False

    _CONFIGURATION_DONE = True


def sanitize_request_id(value: str | None) -> str | None:
    """Reduce an external correlation id to a safe, bounded log token."""
    if value is None:
        return None
    cleaned = _UNSAFE_REQUEST_ID.sub("-", value.strip())[:64]
    return cleaned or None


def get_logger(name: str) -> logging.Logger:
    """Return a named logger under the package namespace."""
    configure_logging()
    if not name.startswith(PACKAGE_LOGGER):
        name = f"{PACKAGE_LOGGER}.{name}"
    return logging.getLogger(name)
