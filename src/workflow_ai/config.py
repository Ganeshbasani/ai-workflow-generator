"""Typed application configuration and secret resolution.

Values come from environment variables, a git-ignored ``.env`` file, or
Streamlit secrets. No secret ever has a hardcoded value in source.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Input limits
    max_input_chars: int = 4_000
    max_context_chars: int = 20_000
    max_upload_bytes: int = 5 * 1024 * 1024
    max_pdf_pages: int = 50

    # Provider configuration
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: SecretStr | None = None
    # Set to http://localhost:11434/v1 for offline Ollama, or a compatible URL
    # for Groq / OpenRouter / Together / vLLM.
    llm_base_url: str | None = None
    request_timeout_seconds: int = 20
    # Local models need time for cold load and token generation; keep this
    # budget independent from the shorter timeout used by hosted APIs.
    ollama_request_timeout_seconds: int = 240
    # A smaller default keeps local 4B models responsive; raise it for longer
    # workflows on machines with faster inference hardware.
    ollama_max_output_tokens: int = 1_000
    # Bound Ollama's KV cache and inference buffers on machines with limited RAM.
    ollama_context_tokens: int = 4096
    temperature: float = 0.0

    # Reliability
    max_repair_retries: int = 2
    retry_backoff_seconds: float = 0.5
    max_output_tokens: int = 2_000
    max_prompt_tokens: int = 6_000

    # Cost / abuse controls
    max_requests_per_session: int = 100
    rate_limit_window_seconds: int = 3_600
    daily_cost_ceiling_usd: float = 1.0

    # Persistence (Phase 3). Override for tests or a writable cloud volume.
    database_path: str = "workflows.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()


def _streamlit_secret(name: str) -> str | None:
    """Read a Streamlit secret if a runtime is available; otherwise ``None``."""
    try:
        import streamlit as st

        secrets = st.secrets
        value = secrets.get(name) if hasattr(secrets, "get") else None
        return str(value) if value else None
    except Exception:
        # Bare/test mode has no secrets store. This is expected offline.
        return None


def resolve_api_key(settings: Settings) -> str | None:
    """Resolve the LLM key: Streamlit secrets first, then env/.env.

    Returns ``None`` when neither source is configured, which is a valid
    signal to run in offline rule-based mode.
    """
    try:
        secret_key = _streamlit_secret("LLM_API_KEY")
    except Exception:
        # A broken secrets store must never prevent offline operation.
        secret_key = None
    if secret_key:
        return secret_key
    if settings.llm_api_key is not None:
        return settings.llm_api_key.get_secret_value()
    return None


def is_ollama_endpoint(base_url: str | None) -> bool:
    """Identify Ollama endpoints that need Ollama-specific request options."""
    normalized = (base_url or "").lower()
    return "11434" in normalized or "ollama" in normalized
