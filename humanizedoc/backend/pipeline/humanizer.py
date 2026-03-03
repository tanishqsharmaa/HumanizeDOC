"""
HumanizeDOC — Humanizer Orchestration Loop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Processes all chunks through the configured LLM backend sequentially,
then maps the humanzied output back to individual paragraph blocks.
"""

from __future__ import annotations

import logging
import re
from typing import Awaitable, Callable, Dict, List, Optional

from humanizedoc.backend.backends import get_humanizer_backend
from humanizedoc.backend.models import (
    Chunk,
    ChunkStatus,
    DocumentBlock,
    Job,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Main orchestration loop
# ═══════════════════════════════════════════════════════════════════

async def humanize_all_chunks(
    chunks: List[Chunk],
    style: str,
    job: Job,
    on_chunk_complete: Optional[Callable[[Chunk], Awaitable[None]]] = None,
    on_chunk_failed: Optional[Callable[[Chunk, str], Awaitable[None]]] = None,
) -> Dict[str, str]:
    """Process all chunks sequentially through the LLM backend.

    Returns a dict mapping ``chunk_id → humanized_text``.

    Chunks are processed one-at-a-time to respect rate limits and
    maintain narrative flow. If a chunk fails, the original text is
    used as fallback and processing continues (partial output is
    always better than no output).
    """
    backend = get_humanizer_backend()
    results: Dict[str, str] = {}

    for chunk in chunks:
        chunk.status = ChunkStatus.PROCESSING

        try:
            humanized_text = await backend.humanize(
                text=chunk.text,
                style=style,
                context=chunk.context_text,
            )

            # Success
            chunk.status = ChunkStatus.DONE
            results[chunk.chunk_id] = humanized_text
            job.completed_chunks += 1

            logger.info(
                "Chunk %s humanized (%d→%d words)",
                chunk.chunk_id,
                chunk.word_count,
                len(humanized_text.split()),
            )

            if on_chunk_complete is not None:
                await on_chunk_complete(chunk)

        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
            logger.error("Chunk %s failed: %s", chunk.chunk_id, error_message)

            # Fallback to original text
            chunk.status = ChunkStatus.FAILED
            results[chunk.chunk_id] = chunk.text
            job.failed_chunks += 1

            if on_chunk_failed is not None:
                await on_chunk_failed(chunk, error_message)

    return results


# ═══════════════════════════════════════════════════════════════════
# Map humanized chunk text back to individual blocks
# ═══════════════════════════════════════════════════════════════════

def map_humanized_back_to_blocks(
    chunks: List[Chunk],
    results: Dict[str, str],
    original_blocks: List[DocumentBlock],
) -> Dict[str, str]:
    """Split each chunk's humanized text back into per-paragraph texts.

    Returns a dict mapping ``block_id → humanized_paragraph_text``.

    Strategy:
    1. Split on double-newlines (``\\n\\n``).
    2. If the split count matches the chunk's block count → 1:1 mapping.
    3. If not, use sentence-boundary redistribution (best-fit).
    4. Last resort: all text to first block, empty for the rest.
    """
    # Build a quick lookup: block_id → DocumentBlock
    block_map = {b.block_id: b for b in original_blocks}
    output: Dict[str, str] = {}

    for chunk in chunks:
        humanized_text = results.get(chunk.chunk_id, chunk.text)
        block_ids = chunk.block_ids
        n_blocks = len(block_ids)

        if n_blocks == 0:
            continue

        if n_blocks == 1:
            output[block_ids[0]] = humanized_text.strip()
            continue

        # ── Strategy 1: split on double-newlines ──────────────────
        paragraphs = [p.strip() for p in humanized_text.split("\n\n") if p.strip()]

        if len(paragraphs) == n_blocks:
            for bid, para in zip(block_ids, paragraphs):
                output[bid] = para
            continue

        # ── Strategy 2: sentence-boundary redistribution ──────────
        sentences = _split_into_sentences(humanized_text)
        if len(sentences) >= n_blocks:
            distributed = _distribute_sentences(sentences, block_ids, block_map)
            output.update(distributed)
            continue

        # ── Strategy 3: last resort ──────────────────────────────
        output[block_ids[0]] = humanized_text.strip()
        for bid in block_ids[1:]:
            output[bid] = ""

    return output


# ═══════════════════════════════════════════════════════════════════
# Sentence splitting helpers
# ═══════════════════════════════════════════════════════════════════

# Regex: split after sentence-ending punctuation followed by space or EOL
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _split_into_sentences(text: str) -> List[str]:
    """Split *text* into sentences using punctuation boundaries."""
    raw = _SENTENCE_RE.split(text.strip())
    return [s.strip() for s in raw if s.strip()]


def _distribute_sentences(
    sentences: List[str],
    block_ids: List[str],
    block_map: Dict[str, DocumentBlock],
) -> Dict[str, str]:
    """Distribute *sentences* across *block_ids* proportionally.

    Each block gets a number of sentences proportional to its original
    word count relative to the total.
    """
    n_blocks = len(block_ids)
    n_sentences = len(sentences)

    # Calculate original word-count weights
    weights = []
    for bid in block_ids:
        block = block_map.get(bid)
        wc = len(block.text.split()) if block else 1
        weights.append(max(wc, 1))
    total_weight = sum(weights)

    # Assign sentence counts proportionally
    assigned: List[int] = []
    remaining = n_sentences
    for i, w in enumerate(weights):
        if i == n_blocks - 1:
            # Last block gets whatever is left
            assigned.append(remaining)
        else:
            count = max(1, round(n_sentences * w / total_weight))
            count = min(count, remaining - (n_blocks - 1 - i))  # leave ≥1 for each remaining
            assigned.append(count)
            remaining -= count

    # Build output
    result: Dict[str, str] = {}
    idx = 0
    for bid, count in zip(block_ids, assigned):
        chunk_sentences = sentences[idx : idx + count]
        result[bid] = " ".join(chunk_sentences)
        idx += count

    return result
