"""
HumanizeDOC — Block Classifier
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Labels every ``DocumentBlock`` as either HUMANIZE (send to LLM) or
PRESERVE (copy verbatim to output).

Rules are applied in strict priority order so that, for example,
a heading inside the references section is still PRESERVE.
"""

from __future__ import annotations

import logging
from typing import List

from humanizedoc.backend.models import BlockType, DocumentBlock

logger = logging.getLogger(__name__)

# ── Style names that are always preserved ─────────────────────────
_HEADING_STYLES = frozenset({
    "Heading 1", "Heading 2", "Heading 3", "Heading 4",
    "Heading 5", "Title", "Subtitle",
})

# ── Text markers that start the references section ────────────────
_REFERENCES_MARKERS = frozenset({
    "references",
    "bibliography",
    "works cited",
    "reference list",
    "sources",
})

# ── Min words for a block to be considered worth humanizing ───────
_MIN_WORD_COUNT = 5


def classify_blocks(blocks: List[DocumentBlock]) -> List[DocumentBlock]:
    """Classify each block as HUMANIZE or PRESERVE (in-place mutation).

    Returns the same list for convenience.
    """
    in_references_section = False

    for block in blocks:
        text_stripped = block.text.strip()
        text_lower = text_stripped.lower()
        word_count = len(text_stripped.split()) if text_stripped else 0

        # ── RULE 1: Empty blocks → PRESERVE ──────────────────────
        if text_stripped == "":
            block.block_type = BlockType.PRESERVE
            continue

        # ── RULE 2: Headings → PRESERVE ──────────────────────────
        if block.style_name in _HEADING_STYLES:
            block.block_type = BlockType.PRESERVE

            # ── RULE 3: Check if this heading starts references ──
            if text_lower in _REFERENCES_MARKERS:
                in_references_section = True
                logger.info(
                    "References section detected at block %s: '%s'",
                    block.block_id,
                    text_stripped,
                )
            continue

        # ── RULE 3 (cont.): Everything after references → PRESERVE
        if in_references_section:
            block.block_type = BlockType.PRESERVE
            continue

        # ── RULE 4: Table header rows → PRESERVE ─────────────────
        if block.block_id.startswith("table_"):
            # block_id format: table_{t}_row_{r}_col_{c}_para_{p}
            parts = block.block_id.split("_")
            try:
                row_idx_pos = parts.index("row") + 1
                r_idx = int(parts[row_idx_pos])
                if r_idx == 0:
                    block.block_type = BlockType.PRESERVE
                    continue
            except (ValueError, IndexError):
                pass
            # Other table cells fall through to remaining rules

        # ── RULE 5: Footnote content → HUMANIZE ──────────────────
        if block.formatting.is_footnote and text_stripped:
            block.block_type = BlockType.HUMANIZE
            continue

        # ── RULE 6: Very short blocks (< 5 words) → PRESERVE ─────
        if word_count < _MIN_WORD_COUNT:
            block.block_type = BlockType.PRESERVE
            continue

        # ── RULE 7: All remaining non-empty text → HUMANIZE ──────
        block.block_type = BlockType.HUMANIZE

    return blocks
