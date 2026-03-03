"""Tests for the block classifier (``pipeline.classifier``)."""

from __future__ import annotations

import pytest

from humanizedoc.backend.models import (
    BlockType,
    DocumentBlock,
    FormattingMeta,
)
from humanizedoc.backend.pipeline.classifier import classify_blocks


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _block(
    block_id: str = "block_0001",
    text: str = "Some placeholder text with enough words to be significant",
    style_name: str = "Normal",
    is_table_cell: bool = False,
    is_footnote: bool = False,
) -> DocumentBlock:
    """Create a DocumentBlock for testing with sensible defaults."""
    return DocumentBlock(
        block_id=block_id,
        block_type=BlockType.HUMANIZE,  # classifier will set real value
        text=text,
        paragraph_index=0,
        style_name=style_name,
        formatting=FormattingMeta(
            is_table_cell=is_table_cell,
            is_footnote=is_footnote,
        ),
    )


# ═══════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════

class TestClassifyBlocks:
    """Tests for ``classify_blocks``."""

    # ── RULE 1: Empty blocks → PRESERVE ──────────────────────────

    def test_empty_block_is_preserve(self):
        blocks = [_block(text="")]
        classify_blocks(blocks)
        assert blocks[0].block_type == BlockType.PRESERVE

    def test_whitespace_only_block_is_preserve(self):
        blocks = [_block(text="   ")]
        classify_blocks(blocks)
        assert blocks[0].block_type == BlockType.PRESERVE

    # ── RULE 2: Headings → PRESERVE ──────────────────────────────

    @pytest.mark.parametrize("heading_style", [
        "Heading 1", "Heading 2", "Heading 3", "Heading 4",
        "Heading 5", "Title", "Subtitle",
    ])
    def test_heading_styles_are_preserve(self, heading_style: str):
        blocks = [_block(style_name=heading_style, text="Some Heading Text Here")]
        classify_blocks(blocks)
        assert blocks[0].block_type == BlockType.PRESERVE

    # ── RULE 3: References section → all subsequent PRESERVE ─────

    def test_references_heading_triggers_preserve_for_all_after(self):
        blocks = [
            _block(block_id="b0", text="Normal paragraph one with enough words for testing purposes", style_name="Normal"),
            _block(block_id="b1", text="References", style_name="Heading 1"),
            _block(block_id="b2", text="Author A. Title of work. Journal, 2024.", style_name="Normal"),
            _block(block_id="b3", text="Author B. Another work. Conference, 2023.", style_name="Normal"),
        ]
        classify_blocks(blocks)
        assert blocks[0].block_type == BlockType.HUMANIZE
        assert blocks[1].block_type == BlockType.PRESERVE  # heading
        assert blocks[2].block_type == BlockType.PRESERVE  # after references
        assert blocks[3].block_type == BlockType.PRESERVE  # after references

    @pytest.mark.parametrize("marker", [
        "references", "bibliography", "works cited", "reference list", "sources",
    ])
    def test_various_reference_markers(self, marker: str):
        blocks = [
            _block(block_id="b0", text=marker.title(), style_name="Heading 1"),
            _block(block_id="b1", text="Some reference entry with words to check it out", style_name="Normal"),
        ]
        classify_blocks(blocks)
        assert blocks[1].block_type == BlockType.PRESERVE

    # ── RULE 4: Table header rows (row 0) → PRESERVE ─────────────

    def test_table_header_row_is_preserve(self):
        blocks = [
            _block(
                block_id="table_0_row_0_col_0_para_0",
                text="Column Header Name Here Right Now",
                is_table_cell=True,
            ),
        ]
        classify_blocks(blocks)
        assert blocks[0].block_type == BlockType.PRESERVE

    def test_table_body_row_is_humanize(self):
        blocks = [
            _block(
                block_id="table_0_row_1_col_0_para_0",
                text="This body cell has enough words to pass the minimum word count threshold",
                is_table_cell=True,
            ),
        ]
        classify_blocks(blocks)
        assert blocks[0].block_type == BlockType.HUMANIZE

    # ── RULE 5: Footnote content → HUMANIZE ──────────────────────

    def test_footnote_with_text_is_humanize(self):
        blocks = [
            _block(
                block_id="footnote_1_para_0",
                text="This footnote explains an important detail for the reader here",
                is_footnote=True,
            ),
        ]
        classify_blocks(blocks)
        assert blocks[0].block_type == BlockType.HUMANIZE

    # ── RULE 6: Very short blocks (< 5 words) → PRESERVE ─────────

    def test_short_block_is_preserve(self):
        blocks = [_block(text="Too short")]
        classify_blocks(blocks)
        assert blocks[0].block_type == BlockType.PRESERVE

    def test_four_word_block_is_preserve(self):
        blocks = [_block(text="Just four words here")]
        classify_blocks(blocks)
        assert blocks[0].block_type == BlockType.PRESERVE

    # ── RULE 7: All remaining → HUMANIZE ─────────────────────────

    def test_normal_paragraph_is_humanize(self):
        blocks = [
            _block(text="This is a perfectly normal paragraph with many words for humanization."),
        ]
        classify_blocks(blocks)
        assert blocks[0].block_type == BlockType.HUMANIZE

    # ── Integration: mixed blocks ────────────────────────────────

    def test_mixed_document_classification(self):
        blocks = [
            _block(block_id="b0", text="Introduction", style_name="Heading 1"),
            _block(block_id="b1", text="This paragraph discusses the main topic of the essay in detail."),
            _block(block_id="b2", text=""),
            _block(block_id="b3", text="OK"),
            _block(block_id="b4", text="Another long paragraph that should definitely be humanized by the LLM."),
            _block(block_id="b5", text="References", style_name="Heading 2"),
            _block(block_id="b6", text="Smith, J. (2024). Example reference entry for testing."),
        ]
        classify_blocks(blocks)
        assert blocks[0].block_type == BlockType.PRESERVE   # heading
        assert blocks[1].block_type == BlockType.HUMANIZE    # normal paragraph
        assert blocks[2].block_type == BlockType.PRESERVE    # empty
        assert blocks[3].block_type == BlockType.PRESERVE    # < 5 words
        assert blocks[4].block_type == BlockType.HUMANIZE    # normal paragraph
        assert blocks[5].block_type == BlockType.PRESERVE    # references heading
        assert blocks[6].block_type == BlockType.PRESERVE    # after references

    def test_returns_same_list(self):
        blocks = [_block()]
        result = classify_blocks(blocks)
        assert result is blocks
