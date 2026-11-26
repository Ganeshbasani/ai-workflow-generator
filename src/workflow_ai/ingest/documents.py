"""Document ingestion — pure, bounded, and free of UI concerns."""

from __future__ import annotations

import io

from pypdf import PdfReader

from ..config import Settings
from ..errors import DocumentError, DocumentTooLargeError


def extract_text(upload: object, settings: Settings) -> str:
    """Extract bounded text from a browser or Streamlit uploaded file.

    Raises:
        DocumentTooLargeError: if the file exceeds byte/page limits.
        DocumentError: if the file is malformed or cannot be decoded.
    """
    getvalue = getattr(upload, "getvalue", None)
    if callable(getvalue):
        data = getvalue()
    else:
        file_obj = getattr(upload, "file", None)
        read = getattr(file_obj, "read", None)
        if not callable(read):
            raise DocumentError("Unsupported upload object.")
        data = read()
    if not isinstance(data, bytes):
        raise DocumentError("Upload returned no data.")

    if len(data) > settings.max_upload_bytes:
        raise DocumentTooLargeError(
            f"Upload exceeds {settings.max_upload_bytes // (1024 * 1024)} MB.",
            user_message=(
                "File is too large. The maximum supported size is "
                f"{settings.max_upload_bytes // (1024 * 1024)} MB."
            ),
        )

    filename = str(
        getattr(upload, "name", None) or getattr(upload, "filename", "") or ""
    ).lower()
    declared_type = str(
        getattr(upload, "type", None) or getattr(upload, "content_type", "") or ""
    ).lower()
    is_pdf = filename.endswith(".pdf") or declared_type == "application/pdf"

    try:
        if is_pdf:
            if not data.startswith(b"%PDF-"):
                raise DocumentError(
                    "Invalid PDF magic bytes.",
                    user_message="This file does not appear to be a valid PDF.",
                )
            reader = PdfReader(io.BytesIO(data))
            if len(reader.pages) > settings.max_pdf_pages:
                raise DocumentTooLargeError(
                    f"PDF has {len(reader.pages)} pages.",
                    user_message=(
                        f"This PDF has too many pages. Only the first "
                        f"{settings.max_pdf_pages} pages can be processed."
                    ),
                )
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        else:
            text = ""
            for encoding in ("utf-8-sig", "utf-16", "latin-1"):
                try:
                    text = data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if not text:
                raise DocumentError(
                    "Text file could not be decoded.",
                    user_message="This text file could not be decoded.",
                )
    except DocumentError:
        raise
    except Exception as exc:  # pypdf raises a variety of parser errors
        raise DocumentError(
            f"Failed to parse uploaded document: {type(exc).__name__}",
            user_message="We couldn't read that file. Please try a different one.",
        ) from exc

    return text[: settings.max_context_chars]
