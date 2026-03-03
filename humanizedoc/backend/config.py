"""
HumanizeDOC — Application Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pydantic v2 Settings class that reads every environment variable
from .env / OS environment and validates them at startup.
"""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised, validated configuration for the HumanizeDOC backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM API Keys ───────────────────────────────────────────────
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # ── LLM Backend Selection ──────────────────────────────────────
    humanizer_backend: str = "groq"  # "groq" | "gemini"

    # ── Azure Storage ──────────────────────────────────────────────
    azure_storage_connection_string: str = ""
    azure_blob_container_name: str = "humanizedoc-uploads"

    # ── Document Limits ────────────────────────────────────────────
    max_file_size_mb: int = 15
    max_words_per_request: int = 12_000

    # ── Chunking ───────────────────────────────────────────────────
    chunk_size_words: int = 500

    # ── File Lifecycle ─────────────────────────────────────────────
    file_expiry_minutes: int = 60

    # ── Rate Limiting ──────────────────────────────────────────────
    rate_limit_per_ip_per_day: int = 5

    # ── Derived helpers (not env vars) ─────────────────────────────
    @property
    def max_file_size_bytes(self) -> int:
        """Max upload size in bytes."""
        return self.max_file_size_mb * 1_024 * 1_024

    # ── Validators ─────────────────────────────────────────────────
    @field_validator("humanizer_backend")
    @classmethod
    def _validate_backend(cls, v: str) -> str:
        allowed = {"groq", "gemini"}
        v_lower = v.strip().lower()
        if v_lower not in allowed:
            raise ValueError(
                f"HUMANIZER_BACKEND must be one of {allowed}, got '{v}'"
            )
        return v_lower

    @field_validator("groq_api_key")
    @classmethod
    def _validate_groq_key(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "GROQ_API_KEY is required. "
                "Set it in your .env file or as an environment variable."
            )
        return v

    @field_validator("azure_storage_connection_string")
    @classmethod
    def _validate_azure_conn(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "AZURE_STORAGE_CONNECTION_STRING is required. "
                "Set it in your .env file or as an environment variable."
            )
        return v


# ── Singleton instance — import this everywhere ───────────────────
settings = Settings()
