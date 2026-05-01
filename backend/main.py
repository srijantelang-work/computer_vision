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

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the rPPG model asynchronously on startup to avoid the 9s delay on first chunk
    from .rppg_processor import _init_rppg_model
    logger.info("Initializing rPPG model on startup...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _init_rppg_model)
    logger.info("rPPG model initialization finished.")
    yield

app = FastAPI(
    title="rPPG Processor API",
    description="Near real-time remote photoplethysmography — BPM estimation from face video",
    version="0.1.0",
    lifespan=lifespan,
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
        logger.info(f"File uploaded and saved: {file_path} ({len(content)} bytes)")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
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


def _background_processor(job_id: str, file_path: str):
    """Synchronous function to run the pipeline and incrementally append to job events."""
    try:
        from .chunk_pipeline import process_video
        logger.info(f"Background thread starting process_video for {job_id}")
        
        for event in process_video(file_path):
            if jobs[job_id].get("status") == "cancelled":
                logger.info(f"Job {job_id} was cancelled. Stopping background processing.")
                break
                
            jobs[job_id]["events"].append(event)
            logger.info(f"Job {job_id} event yielded: {event.get('type')}")
            
            if event.get("type") == "complete":
                jobs[job_id]["result"] = event
                jobs[job_id]["status"] = "complete"
                logger.info(f"Job {job_id} marked as complete.")
            elif event.get("type") == "error":
                jobs[job_id]["status"] = "error"
                logger.error(f"Job {job_id} received error event: {event.get('message')}")
                
        if jobs[job_id]["status"] not in ("complete", "error"):
            jobs[job_id]["status"] = "complete"
            logger.info(f"Job {job_id} finished iterating, marked complete.")

    except Exception as e:
        logger.error(f"Job {job_id} pipeline failed fatally: {e}", exc_info=True)
        jobs[job_id]["status"] = "error"
        jobs[job_id]["events"].append({"type": "error", "message": str(e)})
    finally:
        try:
            os.unlink(file_path)
            logger.info(f"Cleaned up temp file for job {job_id}")
        except OSError:
            pass


async def _process_job(job_id: str):
    """Async wrapper to run the background processor in a thread pool."""
    job = jobs.get(job_id)
    if not job:
        return

    job["status"] = "processing"
    logger.info(f"Async _process_job dispatched for {job_id}")
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _background_processor, job_id, job["file_path"])


@app.get("/stream/{job_id}")
async def stream_results(job_id: str, request: Request):
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
        polls_without_data = 0

        while True:
            if await request.is_disconnected():
                logger.info(f"Client disconnected from SSE stream for job {job_id}. Cancelling job.")
                job["status"] = "cancelled"
                return

            # Send any new events
            had_data = False
            while sent_count < len(job["events"]):
                event = job["events"][sent_count]
                sent_count += 1
                had_data = True
                polls_without_data = 0
                logger.info(f"Streaming event to client: {event.get('type')} for job {job_id}")
                yield {"data": json.dumps(event)}

                # Close stream on terminal events
                if event.get("type") in ("complete", "error"):
                    return

            # If job finished but we've sent everything, close
            if job["status"] in ("complete", "error") and sent_count >= len(job["events"]):
                return

            # Heartbeat keepalive — send SSE comment every ~2s of silence
            # This prevents proxies and browsers from timing out the connection
            if not had_data:
                polls_without_data += 1
                if polls_without_data % 6 == 0:  # Every ~1.8s (6 × 0.3s)
                    yield {"comment": "keepalive"}

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
