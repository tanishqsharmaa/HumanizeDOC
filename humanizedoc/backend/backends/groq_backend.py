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

    async def humanize(self, text: str, style: str, context: str = "") -> str:
        """Send *text* to Groq and return the humanized result (two-pass)."""
        user_message = self.build_user_message(text, context, style)
        temperature = 0.85  # higher = more unpredictable = lower AI score

        for attempt in range(self.max_retries):
            try:
                # Pass 1 — main rewrite
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=temperature,
                    max_tokens=2048,
                )
                pass1 = response.choices[0].message.content.strip()

                if not self.validate_output(text, pass1):
                    # Validation failed — bump temperature and retry
                    logger.warning(
                        "Groq Pass 1 failed validation (attempt %d), "
                        "retrying with temperature %.2f → %.2f",
                        attempt + 1,
                        temperature,
                        min(temperature + 0.1, 1.0),
                    )
                    temperature = min(temperature + 0.1, 1.0)
                    continue

                # Pass 2 — polish pass to break remaining AI patterns
                polish_prompt = (
                    "You are given text written by a student. "
                    "It may still sound slightly AI-generated in places. "
                    "Your job: identify the 2-3 most AI-sounding sentences and rewrite "
                    "ONLY those sentences to sound more natural and student-like. "
                    "Leave everything else exactly as-is. "
                    "Output the full text with those sentences replaced. Nothing else."
                )

                response2 = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": polish_prompt},
                        {"role": "user", "content": pass1},
                    ],
                    temperature=0.9,
                    max_tokens=2048,
                )
                pass2 = response2.choices[0].message.content.strip()

                if self.validate_output(text, pass2):
                    logger.info(
                        "Groq two-pass humanization succeeded on attempt %d",
                        attempt + 1,
                    )
                    return pass2

                # Pass 2 validation failed — fall back to Pass 1
                logger.warning(
                    "Groq Pass 2 failed validation (attempt %d), "
                    "falling back to Pass 1 result",
                    attempt + 1,
                )
                return pass1

            except Exception as exc:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(
                        f"Groq API failed after {self.max_retries} attempts: {exc}"
                    ) from exc
                wait = 2 ** attempt
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
