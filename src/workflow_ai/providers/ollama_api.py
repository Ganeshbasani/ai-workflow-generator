"""Small native Ollama chat transport for reasoning-model compatibility."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from urllib.request import Request, urlopen


def chat_completion(
    *,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    timeout: int,
    temperature: float,
    max_tokens: int,
    context_tokens: int | None = None,
    json_mode: bool = False,
) -> Any:
    """Call Ollama's native API and adapt its response to the SDK shape used here."""
    endpoint = base_url.rstrip("/")
    if endpoint.endswith("/v1"):
        endpoint = endpoint[:-3]
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if context_tokens is not None:
        payload["options"]["num_ctx"] = context_tokens
    if json_mode:
        payload["format"] = "json"

    request = Request(
        f"{endpoint}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read())

    message = result.get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Ollama returned no assistant content.")
    usage = SimpleNamespace(
        prompt_tokens=result.get("prompt_eval_count", 0),
        completion_tokens=result.get("eval_count", 0),
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=usage,
    )
