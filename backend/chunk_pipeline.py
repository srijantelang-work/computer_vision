"""
Chunk Pipeline — Video ingestion, 5-second chunking, and orchestrated rPPG processing.

Takes a video file path, splits it into 5-second segments, processes each chunk
through the rPPG processor, and yields results incrementally for SSE streaming.
"""
from __future__ import annotations

import time
import logging
import cv2
import numpy as np
from typing import Generator
from .rppg_processor import process_chunk

logger = logging.getLogger(__name__)

CHUNK_DURATION = 6


def get_video_metadata(video_path: str) -> dict:
    """Extract metadata from a video file."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if fps <= 0 or total_frames <= 0:
        raise ValueError("Invalid video: could not determine FPS or frame count.")

    duration_s = total_frames / fps
    return {
        "fps": round(fps, 2),
        "total_frames": total_frames,
        "duration_s": round(duration_s, 2),
        "width": width,
        "height": height,
    }


def validate_video(metadata: dict) -> list[str]:
    """Validate video metadata and return a list of warnings."""
    warnings = []
    if metadata["duration_s"] < CHUNK_DURATION:
        warnings.append(f"Video too short ({metadata['duration_s']:.1f}s). Min {CHUNK_DURATION}s required.")
    if metadata["fps"] < 15:
        warnings.append(f"Low framerate ({metadata['fps']} FPS). Recommended >= 15 FPS.")
    if metadata["width"] < 320 or metadata["height"] < 240:
        warnings.append(f"Low resolution ({metadata['width']}x{metadata['height']}).")
    return warnings


def _read_chunk_frames(cap: cv2.VideoCapture, num_frames: int) -> np.ndarray | None:
    """Read N frames from VideoCapture, converting BGR→RGB. Returns (N,H,W,3) or None."""
    frames = []
    for _ in range(num_frames):
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    if not frames:
        return None
    return np.array(frames, dtype=np.uint8)


def process_video(video_path: str) -> Generator[dict, None, None]:
    """
    Process a video in 5-second chunks, yielding results incrementally.
    Yields metadata, then chunk results, then a final complete event.
    """
    metadata = get_video_metadata(video_path)
    logger.info(f"Processing: {metadata['duration_s']}s, {metadata['fps']} FPS, {metadata['width']}x{metadata['height']}")

    warnings = validate_video(metadata)
    for w in warnings:
        logger.warning(w)

    if metadata["duration_s"] < CHUNK_DURATION:
        yield {"type": "error", "message": f"Video too short ({metadata['duration_s']:.1f}s)."}
        return

    yield {
        "type": "metadata",
        "video": metadata,
        "warnings": warnings,
        "total_chunks": int(np.ceil(metadata["duration_s"] / CHUNK_DURATION)),
    }

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        yield {"type": "error", "message": "Failed to open video."}
        return

    fps = metadata["fps"]
    frames_per_chunk = int(CHUNK_DURATION * fps)
    chunk_results = []
    chunk_num = 0
    pipeline_start = time.perf_counter()

    while True:
        chunk_num += 1
        time_start = (chunk_num - 1) * CHUNK_DURATION

        frames = _read_chunk_frames(cap, frames_per_chunk)
        if frames is None or len(frames) == 0:
            break

        actual_duration = len(frames) / fps
        is_partial = len(frames) < frames_per_chunk
        if is_partial and actual_duration < 1.0:
            break

        chunk_start = time.perf_counter()
        result = process_chunk(frames, fps)
        chunk_elapsed = (time.perf_counter() - chunk_start) * 1000

        time_end = time_start + actual_duration
        chunk_result = {
            "type": "chunk",
            "chunk": chunk_num,
            "time_start": round(time_start, 1),
            "time_end": round(time_end, 1),
            "time_label": f"{int(time_start)}-{int(time_end)}s",
            "bpm": result["bpm"],
            "rr": result["rr"],
            "sqi": result["sqi"],
            "method": result["method"],
            "face_detected": result["face_detected"],
            "latency_ms": round(chunk_elapsed, 1),
            "frames_processed": len(frames),
            "is_partial": is_partial,
        }
        chunk_results.append(chunk_result)
        logger.info(f"Chunk {chunk_num}: BPM={result['bpm']}, SQI={result['sqi']}, Latency={chunk_elapsed:.0f}ms")
        yield chunk_result

    cap.release()
    pipeline_elapsed = (time.perf_counter() - pipeline_start) * 1000

    from .metrics import aggregate_results
    overall = aggregate_results(chunk_results, pipeline_elapsed)

    yield {
        "type": "complete",
        "metadata": metadata,
        "warnings": warnings,
        "chunks": chunk_results,
        "overall": overall,
    }
