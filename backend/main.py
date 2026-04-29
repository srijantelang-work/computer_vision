"""
FastAPI Application — Near Real-Time rPPG Processing API.

Endpoints:
    POST /upload       — Upload a face video for processing
    GET  /stream/{id}  — SSE stream of chunk-by-chunk results
    GET  /result/{id}  — Final aggregated result
    GET  /health       — Health check
"""
from __future__ import annotations

import os
import uuid
import json
import asyncio
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Any

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="rPPG Processor API",
    description="Near real-time remote photoplethysmography — BPM estimation from face video",
    version="0.1.0",
)

# CORS — allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job storage ──
# In production, use Redis or a proper task queue.
# For this prototype, dict-based storage is sufficient.
jobs: dict[str, dict[str, Any]] = {}

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".webm"}
MAX_FILE_SIZE_MB = 200
UPLOAD_DIR = Path(tempfile.gettempdir()) / "rppg_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "rppg-processor"}


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """
    Upload a face video for rPPG processing.
    
    Accepts .mp4, .avi, .mkv, .mov, .webm files up to 200MB.
    Returns a job_id to use with /stream/{job_id} and /result/{job_id}.
    """
    # Validate file extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Save uploaded file to temp directory
    job_id = str(uuid.uuid4())[:8]
    file_path = UPLOAD_DIR / f"{job_id}{ext}"

    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
                raise HTTPException(status_code=400, detail=f"File too large. Max {MAX_FILE_SIZE_MB}MB.")
            f.write(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # Initialize job
    jobs[job_id] = {
        "status": "queued",
        "file_path": str(file_path),
        "filename": file.filename,
        "events": [],  # SSE event queue
        "result": None,
    }

    # Start background processing
    asyncio.create_task(_process_job(job_id))

    logger.info(f"Job {job_id} created for '{file.filename}'")
    return {"job_id": job_id, "status": "processing"}


async def _process_job(job_id: str):
    """Background task: run the chunk pipeline and populate the event queue."""
    job = jobs.get(job_id)
    if not job:
        return

    job["status"] = "processing"

    try:
        from .chunk_pipeline import process_video

        # Run the CPU-intensive pipeline in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        events = await loop.run_in_executor(None, lambda: list(process_video(job["file_path"])))

        for event in events:
            job["events"].append(event)
            if event.get("type") == "complete":
                job["result"] = event
                job["status"] = "complete"
            elif event.get("type") == "error":
                job["status"] = "error"

        if job["status"] != "complete" and job["status"] != "error":
            job["status"] = "complete"

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        job["status"] = "error"
        job["events"].append({"type": "error", "message": str(e)})
    finally:
        # Clean up the uploaded file
        try:
            os.unlink(job["file_path"])
        except OSError:
            pass


@app.get("/stream/{job_id}")
async def stream_results(job_id: str):
    """
    SSE endpoint — streams chunk results as they become available.
    
    Each event is a JSON object with type: "metadata", "chunk", "complete", or "error".
    The stream closes after the "complete" or "error" event.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    async def event_generator():
        job = jobs[job_id]
        sent_count = 0

        while True:
            # Send any new events
            while sent_count < len(job["events"]):
                event = job["events"][sent_count]
                sent_count += 1
                yield {"data": json.dumps(event)}

                # Close stream on terminal events
                if event.get("type") in ("complete", "error"):
                    return

            # If job finished but we've sent everything, close
            if job["status"] in ("complete", "error") and sent_count >= len(job["events"]):
                return

            # Poll interval — wait for new events
            await asyncio.sleep(0.3)

    return EventSourceResponse(event_generator())


@app.get("/result/{job_id}")
async def get_result(job_id: str):
    """
    Get the final aggregated result for a completed job.
    
    Returns 202 if still processing, 200 with result if complete, 500 on error.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    job = jobs[job_id]

    if job["status"] == "processing" or job["status"] == "queued":
        return JSONResponse(status_code=202, content={"status": "processing", "job_id": job_id})

    if job["status"] == "error":
        error_events = [e for e in job["events"] if e.get("type") == "error"]
        msg = error_events[-1]["message"] if error_events else "Unknown error"
        raise HTTPException(status_code=500, detail=msg)

    return job["result"]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
