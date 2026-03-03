"""
HumanizeDOC — Azure Blob Storage Helpers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Async wrappers around the synchronous azure-storage-blob SDK.
All I/O is run in a thread executor to stay non-blocking.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional

from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    generate_blob_sas,
)

from humanizedoc.backend.config import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Client singleton
# ═══════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def _get_blob_service_client() -> BlobServiceClient:
    """Return a cached ``BlobServiceClient`` built from the connection string."""
    return BlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    )


def _get_container_client():
    """Return a container client for the configured container."""
    return _get_blob_service_client().get_container_client(
        settings.azure_blob_container_name
    )


# ═══════════════════════════════════════════════════════════════════
# Public async API
# ═══════════════════════════════════════════════════════════════════

async def upload_file(local_path: str, blob_path: str) -> str:
    """Upload a local file to Azure Blob Storage.

    Returns the full blob URL.
    """
    loop = asyncio.get_running_loop()

    def _upload() -> str:
        container = _get_container_client()
        blob_client = container.get_blob_client(blob_path)
        with open(local_path, "rb") as f:
            blob_client.upload_blob(f, overwrite=True)
        logger.info("Uploaded %s → blob:%s", local_path, blob_path)
        return blob_client.url

    return await loop.run_in_executor(None, _upload)


async def download_file(blob_path: str, local_path: str) -> None:
    """Download a blob to a local file path."""
    loop = asyncio.get_running_loop()

    def _download() -> None:
        container = _get_container_client()
        blob_client = container.get_blob_client(blob_path)
        with open(local_path, "wb") as f:
            stream = blob_client.download_blob()
            stream.readinto(f)
        logger.info("Downloaded blob:%s → %s", blob_path, local_path)

    await loop.run_in_executor(None, _download)


async def get_download_url(
    blob_path: str,
    expiry_minutes: Optional[int] = None,
) -> str:
    """Generate a time-limited SAS URL for the blob.

    The URL expires after *expiry_minutes* (defaults to
    ``settings.file_expiry_minutes``).
    """
    if expiry_minutes is None:
        expiry_minutes = settings.file_expiry_minutes

    loop = asyncio.get_running_loop()

    def _generate_sas() -> str:
        service_client = _get_blob_service_client()
        account_name = service_client.account_name

        # Extract account key from connection string
        account_key = _extract_account_key(settings.azure_storage_connection_string)

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=settings.azure_blob_container_name,
            blob_name=blob_path,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes),
        )

        blob_client = _get_container_client().get_blob_client(blob_path)
        return f"{blob_client.url}?{sas_token}"

    return await loop.run_in_executor(None, _generate_sas)


async def delete_file(blob_path: str) -> None:
    """Delete a blob. Silently ignores if the blob doesn't exist."""
    loop = asyncio.get_running_loop()

    def _delete() -> None:
        try:
            container = _get_container_client()
            blob_client = container.get_blob_client(blob_path)
            blob_client.delete_blob()
            logger.info("Deleted blob:%s", blob_path)
        except Exception:
            # Swallow ResourceNotFoundError and any other errors
            logger.debug(
                "Delete blob:%s — blob not found or already deleted.",
                blob_path,
            )

    await loop.run_in_executor(None, _delete)


# ═══════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════

def _extract_account_key(connection_string: str) -> str:
    """Parse ``AccountKey=...`` from an Azure Storage connection string."""
    for part in connection_string.split(";"):
        part = part.strip()
        if part.lower().startswith("accountkey="):
            return part.split("=", 1)[1]
    raise ValueError(
        "Could not extract AccountKey from AZURE_STORAGE_CONNECTION_STRING"
    )
