"""
HumanizeDOC — Chunker
~~~~~~~~~~~~~~~~~~~~~~
Groups HUMANIZE blocks into ~500-word chunks, splitting only at paragraph
boundaries and threading context between consecutive chunks.
"""

from __future__ import annotations

import logging
from typing import List

from humanizedoc.backend.models import (
    BlockType,
    Chunk,
    ChunkStatus,
    DocumentBlock,
)

logger = logging.getLogger(__name__)

# ── Heading styles that should never appear in chunks ─────────────
_HEADING_STYLES = frozenset({
    "Heading 1", "Heading 2", "Heading 3", "Heading 4",
    "Heading 5", "Title", "Subtitle",
})


def build_chunks(
    blocks: List[DocumentBlock],
    target_chunk_size: int = 500,
) -> List[Chunk]:
    """Group HUMANIZE blocks into LLM-sized chunks.

    Parameters
    ----------
    blocks:
        Full list of ``DocumentBlock`` objects (HUMANIZE + PRESERVE).
        Only HUMANIZE blocks are included in chunks.
    target_chunk_size:
        Target word count per chunk (default 500, from ``settings.chunk_size_words``).

    Returns
    -------
    List[Chunk]
        Chunks ready for LLM processing, each with context from the
        previous chunk's last paragraph.
    """
    # ── Step 1: Filter to HUMANIZE-only blocks ────────────────────
    humanize_blocks = [
        b for b in blocks if b.block_type == BlockType.HUMANIZE
    ]

    if not humanize_blocks:
        return []

    # ── Step 2: Group into raw chunk groups ───────────────────────
    chunk_groups: List[List[DocumentBlock]] = []
    current_chunk_blocks: List[DocumentBlock] = []
    current_word_count = 0
    overflow_threshold = target_chunk_size * 1.3

    def _flush() -> None:
        """Flush current_chunk_blocks into chunk_groups."""
        nonlocal current_chunk_blocks, current_word_count
        if current_chunk_blocks:
            chunk_groups.append(current_chunk_blocks)
            current_chunk_blocks = []
            current_word_count = 0

    for block in humanize_blocks:
        # Case C — Guard against headings (should already be PRESERVE)
        if block.style_name in _HEADING_STYLES:
            continue

        word_count = len(block.text.split())

        # Case A — Single oversized block
        if word_count > target_chunk_size:
            _flush()
            chunk_groups.append([block])
            continue

        # Case B — Adding this block would exceed overflow threshold
        if current_word_count + word_count > overflow_threshold and current_chunk_blocks:
            _flush()

        # Case D — Normal: accumulate
        current_chunk_blocks.append(block)
        current_word_count += word_count

        # Flush if we've reached target size
        if current_word_count >= target_chunk_size:
            _flush()

    # Flush any remaining blocks
    _flush()

    # ── Step 3 + 4: Build Chunk objects with context ──────────────
    chunks: List[Chunk] = []
    for idx, group in enumerate(chunk_groups):
        text = "\n\n".join(b.text for b in group)

        # Context: last paragraph text from previous chunk group
        if idx == 0:
            context_text = ""
        else:
            prev_group = chunk_groups[idx - 1]
            context_text = prev_group[-1].text

        chunks.append(Chunk(
            chunk_id=f"chunk_{idx:03d}",
            block_ids=[b.block_id for b in group],
            text=text,
            word_count=len(text.split()),
            context_text=context_text,
            status=ChunkStatus.PENDING,
        ))

    logger.info(
        "Built %d chunks from %d HUMANIZE blocks (target=%d words/chunk)",
        len(chunks),
        len(humanize_blocks),
        target_chunk_size,
    )
    return chunks
