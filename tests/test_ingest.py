"""Unit tests for bounded document ingestion."""

from __future__ import annotations

import pytest

from workflow_ai.config import Settings
from workflow_ai.errors import DocumentError, DocumentTooLargeError
from workflow_ai.ingest import extract_text


class Upload:
    def __init__(self, data: bytes, name: str = "notes.txt", mime: str = "text/plain") -> None:
        self._data = data
        self.name = name
        self.type = mime

    def getvalue(self) -> bytes:
        return self._data


def test_utf8_text() -> None:
    assert extract_text(Upload("hello café".encode()), Settings()) == "hello café"


def test_utf16_text() -> None:
    assert extract_text(Upload("hello".encode("utf-16")), Settings()) == "hello"


def test_context_is_truncated() -> None:
    settings = Settings(max_context_chars=5)
    assert extract_text(Upload(b"abcdefghij"), settings) == "abcde"


def test_oversized_upload_is_rejected() -> None:
    with pytest.raises(DocumentTooLargeError):
        extract_text(Upload(b"x" * 100), Settings(max_upload_bytes=10))


def test_invalid_pdf_is_rejected() -> None:
    with pytest.raises(DocumentError, match="valid PDF"):
        extract_text(Upload(b"not a pdf", name="x.pdf", mime="application/pdf"), Settings())


def test_unsupported_upload_object() -> None:
    with pytest.raises(DocumentError):
        extract_text(object(), Settings())
