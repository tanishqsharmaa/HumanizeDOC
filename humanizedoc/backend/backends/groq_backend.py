"""
HumanizeDOC — Groq LLM Backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Async implementation using the Groq SDK with ``llama-3.1-70b-versatile``.
Retries with temperature escalation on validation failure, exponential
back-off on API errors.
"""

from __future__ import annotations

import asyncio
import logging

from groq import AsyncGroq

from humanizedoc.backend.backends.base import HumanizerBackend
from humanizedoc.backend.config import settings

logger = logging.getLogger(__name__)


class GroqBackend(HumanizerBackend):
    """Groq-hosted Llama 3.1 70B humanizer backend."""

    def __init__(self) -> None:
        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = "llama-3.1-70b-versatile"
        self.max_retries = 2

    async def humanize(
        self,
        text: str,
        style: str,
        context: str = "",
    ) -> str:
        """Send *text* to Groq and return the humanized result."""
        user_message = self.build_user_message(text, context, style)
        temperature = 0.7

        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=temperature,
                    max_tokens=2048,
                )
                result = response.choices[0].message.content.strip()

                if self.validate_output(text, result):
                    logger.info(
                        "Groq humanization succeeded on attempt %d", attempt + 1
                    )
                    return result

                # Validation failed — bump temperature and retry
                logger.warning(
                    "Groq output failed validation (attempt %d), "
                    "retrying with temperature %.1f → %.1f",
                    attempt + 1,
                    temperature,
                    min(temperature + 0.1, 1.0),
                )
                temperature = min(temperature + 0.1, 1.0)

            except Exception as exc:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(
                        f"Groq API failed after {self.max_retries} attempts: {exc}"
                    ) from exc
                wait = 2**attempt
                logger.warning(
                    "Groq API error (attempt %d), retrying in %ds: %s",
                    attempt + 1,
                    wait,
                    exc,
                )
                await asyncio.sleep(wait)

        # All retries exhausted — return original text unchanged
        logger.error("All Groq retries exhausted; returning original text.")
        return text
