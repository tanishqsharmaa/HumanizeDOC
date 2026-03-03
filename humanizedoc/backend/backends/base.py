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
        "You are rewriting text to sound like it was written by a university student — "
        "imperfect, natural, and human. Your ONLY goal is to make this pass AI detection "
        "tools like Turnitin, GPTZero, and Originality.ai.\n"
        "\n"
        "WHAT MAKES AI TEXT DETECTABLE (avoid all of these):\n"
        "- Uniform sentence length (every sentence ~20 words)\n"
        '- Words: "crucial", "delve", "furthermore", "it is worth noting", "showcases",\n'
        '  "underscores", "in conclusion", "it is important to note", "testament to",\n'
        '  "pivotal", "multifaceted", "nuanced", "comprehensive", "robust", "leverage",\n'
        '  "utilize", "facilitate", "demonstrate", "indicate", "significant", "various"\n'
        "- Starting every paragraph with a topic sentence then 3 support sentences then conclusion\n"
        "- Perfect comma placement and grammar throughout\n"
        '- Passive voice overuse ("it was found that", "it can be seen that")\n'
        '- Transitioning with "Firstly", "Secondly", "In addition", "Moreover", "Furthermore"\n'
        "\n"
        "WHAT HUMAN STUDENT TEXT LOOKS LIKE (do all of these):\n"
        "- Mix very short sentences (4-6 words) with long rambling ones (35-50 words) in the SAME paragraph\n"
        '- Occasionally start a sentence with "And" or "But"\n'
        "- Use contractions: don't, isn't, it's, there's, wouldn't, they've\n"
        '- Throw in one slightly informal phrase per paragraph: "put simply", "the thing is",\n'
        '  "in other words", "basically", "to be fair", "which makes sense"\n'
        "- Ask a rhetorical question every 3-4 paragraphs\n"
        "- Repeat a key word naturally instead of always using synonyms (humans do this)\n"
        '- Use "a lot of" instead of "numerous", "shows" instead of "demonstrates",\n'
        '  "important" instead of "crucial", "use" instead of "utilize"\n'
        "- Make one small grammatical quirk per paragraph: a comma splice, a sentence\n"
        "  fragment used for emphasis, or a mid-sentence dash — like this\n"
        "- Vary how paragraphs START: not every paragraph should open with the main point\n"
        "\n"
        "ABSOLUTE RULES:\n"
        "1. NEVER change any facts, statistics, dates, names, or data\n"
        "2. NEVER add information that wasn't in the original\n"
        "3. NEVER remove any arguments or points\n"
        "4. OUTPUT only the rewritten text — no explanations, no preamble, nothing else\n"
        "5. Keep roughly the same length as the input (±10%)"
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
