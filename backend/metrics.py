"""
Metrics — BPM aggregation and performance metric computation.

Provides weighted median aggregation of chunk-level BPM/RR estimates,
using Signal Quality Index (SQI) as weights for robustness against outliers.
"""
from __future__ import annotations

import numpy as np
from typing import Optional


def weighted_median(values: list[float], weights: list[float]) -> Optional[float]:
    """
    Compute the weighted median of a list of values.
    
    More robust than weighted mean — a single outlier chunk (e.g. from motion blur)
    won't skew the overall estimate.
    """
    if not values or not weights:
        return None

    data = sorted(zip(values, weights), key=lambda x: x[0])
    values_sorted = [d[0] for d in data]
    weights_sorted = [d[1] for d in data]

    total_weight = sum(weights_sorted)
    if total_weight == 0:
        return None

    cumulative = 0.0
    for val, w in zip(values_sorted, weights_sorted):
        cumulative += w
        if cumulative >= total_weight / 2.0:
            return round(val, 1)

    return round(values_sorted[-1], 1)


def aggregate_results(chunk_results: list[dict], total_pipeline_ms: float) -> dict:
    """
    Aggregate chunk-level results into overall metrics.
    
    Args:
        chunk_results: list of chunk result dicts from the pipeline
        total_pipeline_ms: total wall-clock time for the entire pipeline
    
    Returns:
        dict with overall BPM, RR, signal quality, and performance stats
    """
    # Filter to chunks with valid BPM readings
    valid_chunks = [c for c in chunk_results if c.get("bpm") is not None]
    all_chunks = chunk_results

    # ── Overall BPM (weighted median) ──
    overall_bpm = None
    if valid_chunks:
        bpm_values = [c["bpm"] for c in valid_chunks]
        bpm_weights = [max(c.get("sqi", 0.5), 0.1) for c in valid_chunks]
        overall_bpm = weighted_median(bpm_values, bpm_weights)

    # ── Overall Respiratory Rate (weighted median) ──
    overall_rr = None
    rr_chunks = [c for c in valid_chunks if c.get("rr") is not None]
    if rr_chunks:
        rr_values = [c["rr"] for c in rr_chunks]
        rr_weights = [max(c.get("sqi", 0.5), 0.1) for c in rr_chunks]
        overall_rr = weighted_median(rr_values, rr_weights)

    # ── Signal Quality ──
    sqi_values = [c.get("sqi", 0.0) for c in all_chunks]
    avg_sqi = round(float(np.mean(sqi_values)), 3) if sqi_values else 0.0

    if avg_sqi >= 0.7:
        quality_label = "good"
    elif avg_sqi >= 0.4:
        quality_label = "fair"
    else:
        quality_label = "poor"

    # ── Performance Stats ──
    latencies = [c.get("latency_ms", 0) for c in all_chunks]
    face_detected_count = sum(1 for c in all_chunks if c.get("face_detected", False))
    total_frames = sum(c.get("frames_processed", 0) for c in all_chunks)

    # ── Method breakdown ──
    methods_used = list(set(c.get("method", "unknown") for c in all_chunks))

    return {
        "overall_bpm": overall_bpm,
        "overall_rr": overall_rr,
        "signal_quality": quality_label,
        "avg_sqi": avg_sqi,
        "total_chunks": len(all_chunks),
        "valid_chunks": len(valid_chunks),
        "failed_chunks": len(all_chunks) - len(valid_chunks),
        "face_detection_rate": round(face_detected_count / len(all_chunks), 2) if all_chunks else 0.0,
        "methods_used": methods_used,
        "performance": {
            "total_pipeline_ms": round(total_pipeline_ms, 1),
            "avg_chunk_latency_ms": round(float(np.mean(latencies)), 1) if latencies else 0.0,
            "min_chunk_latency_ms": round(float(np.min(latencies)), 1) if latencies else 0.0,
            "max_chunk_latency_ms": round(float(np.max(latencies)), 1) if latencies else 0.0,
            "total_frames_processed": total_frames,
        },
    }
