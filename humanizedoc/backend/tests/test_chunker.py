"""Tests for the chunker (``pipeline.chunker``)."""

from __future__ import annotations

import pytest

from humanizedoc.backend.models import (
    BlockType,
    ChunkStatus,
    DocumentBlock,
    FormattingMeta,
)
from humanizedoc.backend.pipeline.chunker import build_chunks


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _words(n: int) -> str:
    """Generate a string of exactly *n* words."""
    return " ".join(f"word{i}" for i in range(n))


def _block(
    block_id: str,
    word_count: int = 50,
    block_type: BlockType = BlockType.HUMANIZE,
    style_name: str = "Normal",
) -> DocumentBlock:
    """Create a DocumentBlock with a specific word count."""
    return DocumentBlock(
        block_id=block_id,
        block_type=block_type,
        text=_words(word_count),
        paragraph_index=0,
        style_name=style_name,
        formatting=FormattingMeta(),
    )


# ═══════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════

class TestBuildChunks:
    """Tests for ``build_chunks``."""

    def test_ten_paragraphs_group_near_target(self):
        """10 × 50 words = 500 total ⇒ should produce 1 chunk."""
        blocks = [_block(f"b{i:02d}", word_count=50) for i in range(10)]
        chunks = build_chunks(blocks, target_chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0].chunk_id == "chunk_000"
        assert chunks[0].word_count >= 450

    def test_twenty_paragraphs_produce_two_chunks(self):
        """20 × 50 words = 1000 total ⇒ should produce ~2 chunks."""
        blocks = [_block(f"b{i:02d}", word_count=50) for i in range(20)]
        chunks = build_chunks(blocks, target_chunk_size=500)
        assert len(chunks) == 2

    def test_oversized_block_becomes_own_chunk(self):
        """A single block > target_chunk_size gets its own chunk."""
        blocks = [
            _block("b00", word_count=50),
            _block("b01", word_count=50),
            _block("b02", word_count=700),   # oversized
            _block("b03", word_count=50),
        ]
        chunks = build_chunks(blocks, target_chunk_size=500)
        # The oversized block should be in its own chunk
        oversized_chunk = [c for c in chunks if "b02" in c.block_ids]
        assert len(oversized_chunk) == 1
        assert oversized_chunk[0].block_ids == ["b02"]

    def test_context_text_first_chunk_is_empty(self):
        """First chunk always has empty context_text."""
        blocks = [_block(f"b{i:02d}", word_count=100) for i in range(10)]
        chunks = build_chunks(blocks, target_chunk_size=500)
        assert chunks[0].context_text == ""

    def test_context_text_subsequent_chunk_has_previous_last_para(self):
        """chunk[1].context_text == last paragraph text of chunk[0]."""
        blocks = [_block(f"b{i:02d}", word_count=100) for i in range(12)]
        chunks = build_chunks(blocks, target_chunk_size=500)
        assert len(chunks) >= 2
        # The context should be the text of the last block in chunk 0
        last_block_id_chunk0 = chunks[0].block_ids[-1]
        last_block_text = next(
            b.text for b in blocks if b.block_id == last_block_id_chunk0
        )
        assert chunks[1].context_text == last_block_text

    def test_preserve_blocks_excluded_from_chunks(self):
        """PRESERVE blocks should not appear in any chunk."""
        blocks = [
            _block("b00", word_count=100, block_type=BlockType.HUMANIZE),
            _block("b01", word_count=100, block_type=BlockType.PRESERVE),
            _block("b02", word_count=100, block_type=BlockType.HUMANIZE),
            _block("b03", word_count=100, block_type=BlockType.PRESERVE),
            _block("b04", word_count=100, block_type=BlockType.HUMANIZE),
            _block("b05", word_count=100, block_type=BlockType.HUMANIZE),
            _block("b06", word_count=100, block_type=BlockType.HUMANIZE),
        ]
        chunks = build_chunks(blocks, target_chunk_size=500)
        all_block_ids = [bid for c in chunks for bid in c.block_ids]
        assert "b01" not in all_block_ids
        assert "b03" not in all_block_ids

    def test_heading_blocks_skipped(self):
        """Blocks with heading style_name should be skipped even if HUMANIZE."""
        blocks = [
            _block("b00", word_count=100, style_name="Heading 1"),
            _block("b01", word_count=200),
            _block("b02", word_count=200),
            _block("b03", word_count=200),
        ]
        # Force the heading to HUMANIZE to test the guard
        blocks[0].block_type = BlockType.HUMANIZE
        chunks = build_chunks(blocks, target_chunk_size=500)
        all_block_ids = [bid for c in chunks for bid in c.block_ids]
        assert "b00" not in all_block_ids

    def test_empty_input_returns_empty(self):
        """No blocks → no chunks."""
        assert build_chunks([], target_chunk_size=500) == []

    def test_all_preserve_returns_empty(self):
        """All PRESERVE blocks → no chunks."""
        blocks = [
            _block("b00", block_type=BlockType.PRESERVE),
            _block("b01", block_type=BlockType.PRESERVE),
        ]
        assert build_chunks(blocks, target_chunk_size=500) == []

    def test_all_chunks_have_pending_status(self):
        """Every chunk starts with PENDING status."""
        blocks = [_block(f"b{i:02d}", word_count=100) for i in range(10)]
        chunks = build_chunks(blocks, target_chunk_size=500)
        assert all(c.status == ChunkStatus.PENDING for c in chunks)

    def test_chunk_ids_sequential(self):
        """Chunk IDs should be sequential: chunk_000, chunk_001, …"""
        blocks = [_block(f"b{i:02d}", word_count=200) for i in range(10)]
        chunks = build_chunks(blocks, target_chunk_size=500)
        for idx, chunk in enumerate(chunks):
            assert chunk.chunk_id == f"chunk_{idx:03d}"
