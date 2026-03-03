"""
HumanizeDOC — Google Gemini LLM Backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fallback implementation using Google's ``gemini-1.5-flash`` model.
The Gemini Python SDK is synchronous, so calls are wrapped with
``loop.run_in_executor`` to stay non-blocking.
"""

from __future__ import annotations

import asyncio
import logging

import google.generativeai as genai

from humanizedoc.backend.backends.base import HumanizerBackend
from humanizedoc.backend.config import settings

logger = logging.getLogger(__name__)


class GeminiBackend(HumanizerBackend):
    """Google Gemini 1.5 Flash humanizer backend."""

    def __init__(self) -> None:
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=self.SYSTEM_PROMPT,
        )
        self.max_retries = 2

    async def humanize(
        self,
        text: str,
        style: str,
        context: str = "",
    ) -> str:
        """Send *text* to Gemini and return the humanized result."""
        user_message = self.build_user_message(text, context, style)
        temperature = 0.7

        for attempt in range(self.max_retries):
            try:
                # Gemini SDK is synchronous — run in a thread executor
                loop = asyncio.get_running_loop()
                gen_config = {
                    "temperature": temperature,
                    "max_output_tokens": 2048,
                }
                response = await loop.run_in_executor(
                    None,
                    lambda cfg=gen_config: self.model.generate_content(
                        user_message,
                        generation_config=cfg,
                    ),
                )
                result = response.text.strip()

                if self.validate_output(text, result):
                    logger.info(
                        "Gemini humanization succeeded on attempt %d",
                        attempt + 1,
                    )
                    return result

                # Validation failed — bump temperature and retry
                logger.warning(
                    "Gemini output failed validation (attempt %d), "
                    "retrying with temperature %.1f → %.1f",
                    attempt + 1,
                    temperature,
                    min(temperature + 0.1, 1.0),
                )
                temperature = min(temperature + 0.1, 1.0)

            except Exception as exc:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(
                        f"Gemini API failed after {self.max_retries} attempts: {exc}"
                    ) from exc
                wait = 2**attempt
                logger.warning(
                    "Gemini API error (attempt %d), retrying in %ds: %s",
                    attempt + 1,
                    wait,
                    exc,
                )
                await asyncio.sleep(wait)

        # All retries exhausted — return original text unchanged
        logger.error("All Gemini retries exhausted; returning original text.")
        return text
