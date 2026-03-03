"""
HumanizeDOC — Humanizer Backend (Abstract Base)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Defines the pluggable ``HumanizerBackend`` ABC that every LLM backend
must implement.  Contains the locked system prompt, user-message builder,
and output-validation logic shared by all backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class HumanizerBackend(ABC):
    """Abstract base for LLM humanization backends (Groq, Gemini, …)."""

    # ── LOCKED system prompt — used verbatim by all backends ──────
    SYSTEM_PROMPT: str = (
        "You are rewriting academic text written by a student. Your goal is to make\n"
        "the text pass Turnitin's AI detection system by making it sound authentically\n"
        "human-written.\n"
        "\n"
        "RULES:\n"
        "1. VARY sentence length dramatically.\n"
        "   Mix short sentences (5-8 words) with long, complex sentences (30-45 words).\n"
        "   AI text has uniform sentence length — humans do not.\n"
        "\n"
        "2. INCREASE unpredictability.\n"
        "   Choose slightly unexpected but correct word choices.\n"
        '   NEVER use: "crucial", "delve", "it is worth noting", "in conclusion",\n'
        '   "furthermore", "showcases", "underscores", "it is important to note",\n'
        '   "it\'s worth mentioning", "testament to".\n'
        "\n"
        "3. ADD human writing patterns:\n"
        "   - Occasional contractions (don't, isn't, there's)\n"
        "   - One rhetorical question per 4-5 paragraphs\n"
        '   - One informal transition per section ("Put simply," or "Here\'s the thing:")\n'
        "\n"
        "4. PRESERVE all facts, arguments, and data exactly.\n"
        "   Never change numbers, dates, names, or statistics.\n"
        "\n"
        "5. MAINTAIN academic register. Keep it educated, just more natural.\n"
        "\n"
        "6. NEVER add new information. NEVER remove key arguments. Rephrase only.\n"
        "\n"
        "7. OUTPUT the rewritten text only. No preamble. No explanations."
    )

    # ── Abstract method every backend must implement ──────────────
    @abstractmethod
    async def humanize(
        self,
        text: str,
        style: str,
        context: str = "",
    ) -> str:
        """Humanize *text* using the backend LLM.

        Parameters
        ----------
        text:
            The chunk text to rewrite.
        style:
            One of ``"academic"``, ``"essay"``, ``"report"``.
        context:
            Last paragraph of the previous chunk (for continuity).

        Returns
        -------
        str
            Humanized text, or the original text if all retries fail.
        """
        ...

    # ── Shared helpers ────────────────────────────────────────────

    def build_user_message(
        self,
        text: str,
        context: str,
        style: str,
    ) -> str:
        """Build the user message combining context and text to humanize."""
        style_instructions = {
            "academic": "This is an academic essay or research paper.",
            "essay": "This is a university essay with a clear argument.",
            "report": "This is a formal report or technical document.",
        }
        style_note = style_instructions.get(style, style_instructions["academic"])

        if context:
            return (
                f"CONTEXT (read only — do not rewrite, use for continuity only):\n"
                f"{context}\n\n"
                f"WRITING STYLE NOTE: {style_note}\n\n"
                f"TEXT TO HUMANIZE:\n{text}"
            )
        return f"WRITING STYLE NOTE: {style_note}\n\nTEXT TO HUMANIZE:\n{text}"

    def validate_output(self, original: str, humanized: str) -> bool:
        """Return ``True`` if the humanized output passes sanity checks.

        Checks:
        - Not empty
        - Not identical to the original
        - Word count within ±15 % of the original
        """
        if not humanized or not humanized.strip():
            return False
        if humanized.strip() == original.strip():
            return False
        orig_words = len(original.split())
        hum_words = len(humanized.split())
        if orig_words == 0:
            return False
        ratio = hum_words / orig_words
        return 0.85 <= ratio <= 1.15
