"""ASGI entry point: ``uvicorn api:app``."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from workflow_ai.api import create_app

app = create_app()
