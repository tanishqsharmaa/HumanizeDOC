"""
HumanizeDOC — FastAPI Application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Main entry point. Exposes four API routes:

- ``POST /api/upload``       — Upload a .docx, start background processing
- ``GET  /api/status/{id}``  — Poll job progress
- ``GET  /api/download/{id}``— Get SAS download URL for completed job
- ``GET  /api/health``       — Health check
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
import os
import tempfile
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from humanizedoc.backend.config import settings
from humanizedoc.backend.models import (
    DownloadResponse,
    Job,
    JobStatus,
    StatusResponse,
    UploadResponse,
)
from humanizedoc.backend.pipeline.chunker import build_chunks
from humanizedoc.backend.pipeline.classifier import classify_blocks
from humanizedoc.backend.pipeline.humanizer import (
    humanize_all_chunks,
    map_humanized_back_to_blocks,
)
from humanizedoc.backend.pipeline.parser import count_words, parse_docx
from humanizedoc.backend.pipeline.reconstructor import reconstruct_docx
from humanizedoc.backend.storage.azure_blob import (
    delete_file,
    download_file,
    get_download_url,
    upload_file,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


# ═══════════════════════════════════════════════════════════════════
# Application
# ═══════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup / shutdown lifecycle hook."""
    logger.info(
        "HumanizeDOC API starting — backend=%s, max_file=%dMB, chunk=%d words",
        settings.humanizer_backend,
        settings.max_file_size_mb,
        settings.chunk_size_words,
    )
    yield
    logger.info("HumanizeDOC API shutting down.")


app = FastAPI(
    title="HumanizeDOC API",
    version="1.0.0",
    description="Upload an AI-written .docx and get it back humanized.",
    lifespan=lifespan,
)

# ── CORS (permissive for MVP) ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)


# ═══════════════════════════════════════════════════════════════════
# In-memory stores (MVP — replace with Redis / DB in production)
# ═══════════════════════════════════════════════════════════════════

# Job store
jobs: Dict[str, Job] = {}

# Rate limiter: IP → list of upload timestamps (last 24 h)
_rate_tracker: Dict[str, list[float]] = defaultdict(list)

_SECONDS_PER_DAY = 86_400


def _check_rate_limit(ip: str) -> None:
    """Raise HTTP 429 if *ip* has exceeded the daily upload limit."""
    now = time.time()
    cutoff = now - _SECONDS_PER_DAY

    # Purge stale entries
    _rate_tracker[ip] = [ts for ts in _rate_tracker[ip] if ts > cutoff]

    if len(_rate_tracker[ip]) >= settings.rate_limit_per_ip_per_day:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded. Maximum {settings.rate_limit_per_ip_per_day} "
                f"documents per day. Please try again tomorrow."
            ),
        )


def _record_upload(ip: str) -> None:
    """Record an upload timestamp for *ip*."""
    _rate_tracker[ip].append(time.time())


# ═══════════════════════════════════════════════════════════════════
# Temp file helpers (cross-platform)
# ═══════════════════════════════════════════════════════════════════

def _temp_path(job_id: str, suffix: str) -> str:
    """Return a temp file path for *job_id*."""
    return os.path.join(tempfile.gettempdir(), f"{job_id}_{suffix}.docx")


def _cleanup_temp_files(job_id: str) -> None:
    """Silently remove temp files for *job_id*."""
    for suffix in ("original", "humanized"):
        path = _temp_path(job_id, suffix)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health_check():
    """Lightweight health check."""
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    style: str = Query(default="academic", pattern="^(academic|essay|report)$"),
):
    """Upload a .docx document for humanization."""
    client_ip = request.client.host if request.client else "unknown"

    # ── Rate limit ────────────────────────────────────────────────
    _check_rate_limit(client_ip)

    # ── Validate file extension ───────────────────────────────────
    filename = file.filename or ""
    if not filename.lower().endswith(".docx"):
        raise HTTPException(
            status_code=400,
            detail="Only .docx files are accepted.",
        )

    # ── Read file contents and validate size ──────────────────────
    contents = await file.read()
    max_bytes = settings.max_file_size_bytes
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File too large ({len(contents) / 1_048_576:.1f} MB). "
                f"Maximum is {settings.max_file_size_mb} MB."
            ),
        )

    # ── Save to temp + upload to blob ─────────────────────────────
    job_id = str(uuid.uuid4())
    local_path = _temp_path(job_id, "original")

    with open(local_path, "wb") as f:
        f.write(contents)

    blob_input_path = f"uploads/{job_id}/original.docx"
    await upload_file(local_path, blob_input_path)

    # ── Create job ────────────────────────────────────────────────
    job = Job(
        job_id=job_id,
        original_filename=filename,
        status=JobStatus.UPLOADING,
        blob_input_path=blob_input_path,
        blob_output_path=f"uploads/{job_id}/humanized.docx",
        created_at=datetime.now(timezone.utc),
    )
    jobs[job_id] = job

    # ── Record rate limit hit ─────────────────────────────────────
    _record_upload(client_ip)

    # ── Launch background processing ──────────────────────────────
    asyncio.create_task(process_job(job_id, style))

    logger.info(
        "Upload accepted: job=%s file=%s size=%d ip=%s",
        job_id,
        filename,
        len(contents),
        client_ip,
    )
    return UploadResponse(
        job_id=job_id,
        message="Document uploaded successfully. Processing started.",
    )


@app.get("/api/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    """Poll the processing status of a job."""
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    remaining_chunks = job.total_chunks - job.completed_chunks - job.failed_chunks
    estimated_seconds = remaining_chunks * 10 if remaining_chunks > 0 else 0

    return StatusResponse(
        job_id=job.job_id,
        status=job.status,
        total_chunks=job.total_chunks,
        completed_chunks=job.completed_chunks,
        failed_chunks=job.failed_chunks,
        chunks=job.chunks,
        estimated_seconds_remaining=estimated_seconds if job.status != JobStatus.DONE else 0,
    )


@app.get("/api/download/{job_id}", response_model=DownloadResponse)
async def download_document(job_id: str):
    """Get a time-limited download URL for a completed job."""
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job.status != JobStatus.DONE:
        raise HTTPException(
            status_code=400,
            detail=f"Job not complete yet. Current status: {job.status.value}",
        )

    download_url = await get_download_url(
        job.blob_output_path,
        expiry_minutes=settings.file_expiry_minutes,
    )

    processing_time = 0.0
    if job.completed_at and job.created_at:
        processing_time = (job.completed_at - job.created_at).total_seconds()

    return DownloadResponse(
        job_id=job.job_id,
        download_url=download_url,
        original_word_count=job.original_word_count,
        humanized_word_count=job.humanized_word_count,
        processing_time_seconds=round(processing_time, 2),
    )


# ═══════════════════════════════════════════════════════════════════
# Background pipeline
# ═══════════════════════════════════════════════════════════════════

async def process_job(job_id: str, style: str) -> None:
    """Run the complete humanization pipeline as a background task."""
    job = jobs[job_id]
    local_input = _temp_path(job_id, "original")
    local_output = _temp_path(job_id, "humanized")

    try:
        # ── 1. PARSE ──────────────────────────────────────────────
        job.status = JobStatus.PARSING
        logger.info("[%s] Parsing document…", job_id)

        # Ensure local file exists (re-download from blob if needed)
        if not os.path.exists(local_input):
            await download_file(job.blob_input_path, local_input)

        blocks = parse_docx(local_input)

        # ── 2. CLASSIFY ──────────────────────────────────────────
        blocks = classify_blocks(blocks)
        job.original_word_count = count_words(blocks)

        if job.original_word_count > settings.max_words_per_request:
            raise ValueError(
                f"Document exceeds {settings.max_words_per_request:,} word limit "
                f"({job.original_word_count:,} words found)."
            )

        # ── 3. CHUNK ─────────────────────────────────────────────
        job.status = JobStatus.CHUNKING
        logger.info("[%s] Chunking (%d words)…", job_id, job.original_word_count)

        chunks = build_chunks(blocks, settings.chunk_size_words)
        job.chunks = chunks
        job.total_chunks = len(chunks)

        # ── 4. HUMANIZE ──────────────────────────────────────────
        job.status = JobStatus.HUMANIZING
        logger.info("[%s] Humanizing %d chunks…", job_id, len(chunks))

        async def _on_chunk_complete(chunk):
            logger.info(
                "[%s] Chunk %s done (%d/%d)",
                job_id, chunk.chunk_id,
                job.completed_chunks, job.total_chunks,
            )

        async def _on_chunk_failed(chunk, err):
            logger.warning(
                "[%s] Chunk %s failed: %s", job_id, chunk.chunk_id, err
            )

        results = await humanize_all_chunks(
            chunks, style, job,
            on_chunk_complete=_on_chunk_complete,
            on_chunk_failed=_on_chunk_failed,
        )

        # ── 5. MAP BACK TO BLOCKS ────────────────────────────────
        humanized_block_map = map_humanized_back_to_blocks(
            chunks, results, blocks
        )
        job.humanized_word_count = sum(
            len(t.split()) for t in humanized_block_map.values()
        )

        # ── 6. RECONSTRUCT ───────────────────────────────────────
        job.status = JobStatus.RECONSTRUCTING
        logger.info("[%s] Reconstructing document…", job_id)

        reconstruct_docx(local_input, blocks, humanized_block_map, local_output)

        # ── 7. UPLOAD OUTPUT ─────────────────────────────────────
        await upload_file(local_output, job.blob_output_path)

        job.status = JobStatus.DONE
        job.completed_at = datetime.now(timezone.utc)
        logger.info("[%s] ✅ Job complete.", job_id)

    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error_message = str(exc)
        logger.error("[%s] ❌ Job failed: %s", job_id, exc, exc_info=True)

    finally:
        _cleanup_temp_files(job_id)

