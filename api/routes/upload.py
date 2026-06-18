"""Upload endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, UploadFile

from api.models import UploadResponse, UploadStatus
from src.ingestion.upload_handler import (
    delete_upload,
    get_upload_status,
    list_uploads,
    process_upload,
    save_upload,
    validate_upload,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    ticker: str = Form(...),
    year: str = Form(...),
):
    """Upload a PDF document for indexing."""
    content = await file.read()
    file_size = len(content)

    valid, msg = validate_upload(file.filename or "unknown.pdf", file_size)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    doc_id = save_upload(content, file.filename or "document.pdf", ticker, year)
    background_tasks.add_task(process_upload, doc_id)

    return UploadResponse(
        doc_id=doc_id,
        status="processing",
        filename=file.filename or "document.pdf",
        ticker=ticker.upper(),
        year=year,
    )


@router.get("/upload/{doc_id}/status", response_model=UploadStatus)
def upload_status(doc_id: str) -> UploadStatus:
    """Check upload processing status."""
    status = get_upload_status(doc_id)
    if not status:
        raise HTTPException(status_code=404, detail="Document not found")
    return UploadStatus(
        doc_id=status["doc_id"],
        filename=status["filename"],
        status=status["status"],
        chunk_count=status["chunk_count"],
        error=status.get("error"),
    )


@router.get("/uploads", response_model=list[UploadStatus])
def list_all_uploads() -> list[UploadStatus]:
    """List all uploaded documents."""
    uploads = list_uploads()
    return [
        UploadStatus(
            doc_id=u["doc_id"],
            filename=u["filename"],
            status=u["status"],
            chunk_count=u["chunk_count"],
            error=u.get("error"),
        )
        for u in uploads
    ]


@router.delete("/upload/{doc_id}")
def delete_uploaded(doc_id: str):
    """Delete uploaded document."""
    if not delete_upload(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted"}
