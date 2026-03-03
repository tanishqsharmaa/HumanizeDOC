"""
HumanizeDOC — Backend Factory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides ``get_humanizer_backend()`` to instantiate the correct LLM
backend based on the ``HUMANIZER_BACKEND`` environment variable.
"""

from __future__ import annotations

from humanizedoc.backend.backends.base import HumanizerBackend
from humanizedoc.backend.config import settings


def get_humanizer_backend() -> HumanizerBackend:
    """Return an instance of the configured humanizer backend.

    Reads ``settings.humanizer_backend`` (``"groq"`` or ``"gemini"``)
    and returns the matching backend class.

    Raises ``ValueError`` for unknown backend names.
    """
    backend_name = settings.humanizer_backend.lower()

    if backend_name == "groq":
        from humanizedoc.backend.backends.groq_backend import GroqBackend
        return GroqBackend()

    if backend_name == "gemini":
        from humanizedoc.backend.backends.gemini_backend import GeminiBackend
        return GeminiBackend()

    raise ValueError(f"Unknown HUMANIZER_BACKEND: {backend_name!r}")
