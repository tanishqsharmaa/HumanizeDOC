"""
HumanizeDOC — Domain Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Every Pydantic model and enum used across the processing pipeline.
All enums use the ``str`` mixin so they serialise to JSON as plain strings.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════
# Enumerations
# ═══════════════════════════════════════════════════════════════════

class BlockType(str, enum.Enum):
    """Whether a document block should be humanized or preserved as-is."""
    HUMANIZE = "HUMANIZE"
    PRESERVE = "PRESERVE"


class ChunkStatus(str, enum.Enum):
    """Processing status of a single chunk."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class JobStatus(str, enum.Enum):
    """High-level lifecycle status of a processing job."""
    UPLOADING = "UPLOADING"
    PARSING = "PARSING"
    CHUNKING = "CHUNKING"
    HUMANIZING = "HUMANIZING"
    RECONSTRUCTING = "RECONSTRUCTING"
    DONE = "DONE"
    FAILED = "FAILED"


# ═══════════════════════════════════════════════════════════════════
# Document-level models
# ═══════════════════════════════════════════════════════════════════

class FormattingMeta(BaseModel):
    """Formatting metadata captured from a single paragraph / run."""
    font_name: Optional[str] = None
    font_size: Optional[int] = None          # half-points (as python-docx returns)
    bold: bool = False
    italic: bool = False
    underline: bool = False
    alignment: Optional[str] = None          # LEFT | CENTER | RIGHT | JUSTIFY
    space_before: Optional[int] = None       # twips
    space_after: Optional[int] = None        # twips
    line_spacing: Optional[float] = None
    is_list_item: bool = False
    list_level: int = 0                      # 0 = not a list item
    list_type: Optional[str] = None          # "bullet" | "numbered" | None
    is_table_cell: bool = False              # True for paragraphs inside table cells
    is_footnote: bool = False                # True for paragraphs inside footnotes


class DocumentBlock(BaseModel):
    """A single paragraph-level block extracted from the DOCX."""
    block_id: str
    block_type: BlockType = BlockType.HUMANIZE
    text: str
    paragraph_index: int
    style_name: str = "Normal"               # e.g. "Heading 1", "Normal"
    formatting: FormattingMeta = Field(default_factory=FormattingMeta)


# ═══════════════════════════════════════════════════════════════════
# Chunk models
# ═══════════════════════════════════════════════════════════════════

class Chunk(BaseModel):
    """A group of HUMANIZE blocks batched together for LLM processing."""
    chunk_id: str
    block_ids: List[str]
    text: str                                # concatenated text of all blocks
    word_count: int = 0
    context_text: str = ""                   # last paragraph of previous chunk
    status: ChunkStatus = ChunkStatus.PENDING


# ═══════════════════════════════════════════════════════════════════
# Job models
# ═══════════════════════════════════════════════════════════════════

class Job(BaseModel):
    """Full state of a document-processing job."""
    job_id: str
    original_filename: str
    status: JobStatus = JobStatus.UPLOADING
    chunks: List[Chunk] = Field(default_factory=list)
    total_chunks: int = 0
    completed_chunks: int = 0
    failed_chunks: int = 0
    original_word_count: int = 0
    humanized_word_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    blob_input_path: str = ""
    blob_output_path: str = ""


# ═══════════════════════════════════════════════════════════════════
# API response schemas
# ═══════════════════════════════════════════════════════════════════

class UploadResponse(BaseModel):
    """Returned when a document is successfully uploaded."""
    job_id: str
    message: str = "Document uploaded successfully. Processing started."


class StatusResponse(BaseModel):
    """Returned when the client polls for job progress."""
    job_id: str
    status: JobStatus
    total_chunks: int = 0
    completed_chunks: int = 0
    failed_chunks: int = 0
    chunks: List[Chunk] = Field(default_factory=list)
    estimated_seconds_remaining: Optional[int] = None


class DownloadResponse(BaseModel):
    """Returned when the humanized document is ready for download."""
    job_id: str
    download_url: str
    original_word_count: int = 0
    humanized_word_count: int = 0
    processing_time_seconds: float = 0.0
