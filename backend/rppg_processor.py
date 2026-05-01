"""
rPPG Signal Processor — Dual-mode engine for heart rate and respiratory rate estimation.

Mode A (Primary): Uses open-rppg deep learning models (EfficientPhys, PhysNet, etc.)
Mode B (Fallback): Classical CHROM algorithm with MediaPipe face detection

The processor automatically falls back to CHROM if the DL model fails or is unavailable.
"""
from __future__ import annotations

import time
import logging
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks
from scipy.fft import rfft, rfftfreq
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Mode A: open-rppg Deep Learning Model
# ─────────────────────────────────────────────

_rppg_model = None
_rppg_available = False


def _init_rppg_model(model_name: str = "EfficientPhys.rlap"):
    """Lazily initialize the open-rppg model. Called once on first use."""
    global _rppg_model, _rppg_available
    try:
        import rppg
        _rppg_model = rppg.Model(model_name)
        _rppg_available = True
        logger.info(f"open-rppg model '{model_name}' loaded successfully.")
    except Exception as e:
        _rppg_available = False
        logger.warning(f"open-rppg unavailable ({e}). Will use CHROM fallback.")


import threading
_rppg_lock = threading.Lock()

def process_chunk_rppg(frames: np.ndarray, fps: float) -> Optional[dict]:
    """
    Process a chunk of frames using the open-rppg deep learning model.
    """
    global _rppg_model, _rppg_available

    if not _rppg_available:
        if _rppg_model is None:
            _init_rppg_model()
        if not _rppg_available:
            return None

    try:
        # Wrap in lock because open-rppg seems non-thread-safe
        with _rppg_lock:
            result = _rppg_model.process_video_tensor(frames, fps=fps)

        if result is None:
            return None

        bpm = result.get("hr")
        sqi = result.get("SQI", 0.0)
        hrv = result.get("hrv", {})
        rr = hrv.get("breathingrate") if hrv else None

        if bpm is None or (isinstance(bpm, float) and np.isnan(bpm)):
            return None

        return {
            "bpm": round(float(bpm), 1),
            "rr": round(float(rr), 1) if rr is not None else None,
            "sqi": round(float(sqi), 3) if sqi is not None else 0.0,
        }
    except Exception as e:
        logger.warning(f"open-rppg processing failed: {e}")
        return None


# ─────────────────────────────────────────────
# Mode B: Classical CHROM Algorithm (Fallback)
# ─────────────────────────────────────────────

_face_cascade = None

def _get_face_cascade():
    """Lazily load the Haar cascade face detector."""
    global _face_cascade
    if _face_cascade is None:
        import cv2
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _face_cascade = cv2.CascadeClassifier(cascade_path)
    return _face_cascade


def _detect_face_roi(frames: np.ndarray) -> Optional[np.ndarray]:
    """
    Detect face and extract forehead+cheek ROI using MediaPipe (Primary) or Haar Cascade (Fallback).
    """
    import cv2
    
    mp_face_detection = None
    try:
        import mediapipe as mp
        if hasattr(mp, 'solutions'):
            mp_face_detection = mp.solutions.face_detection
    except (ImportError, AttributeError):
        mp_face_detection = None
    
    rgb_signals = []
    last_face_box = None

    def _extract_from_box(frame, face_box):
        x, y, w, h = face_box
        fh_y1, fh_y2 = max(0, y + int(0.05 * h)), y + int(0.35 * h)
        fh_x1, fh_x2 = x + int(0.2 * w), x + int(0.8 * w)
        lc_y1, lc_y2 = y + int(0.4 * h), y + int(0.7 * h)
        lc_x1, lc_x2 = x + int(0.05 * w), x + int(0.35 * w)
        rc_y1, rc_y2 = y + int(0.4 * h), y + int(0.7 * h)
        rc_x1, rc_x2 = x + int(0.65 * w), x + int(0.95 * w)
        
        fh, fw, _ = frame.shape
        def _clamp(y1, y2, x1, x2):
            return max(0, min(y1, fh)), max(0, min(y2, fh)), max(0, min(x1, fw)), max(0, min(x2, fw))
        
        rois = []
        for (ry1, ry2, rx1, rx2) in [_clamp(fh_y1, fh_y2, fh_x1, fh_x2), _clamp(lc_y1, lc_y2, lc_x1, lc_x2), _clamp(rc_y1, rc_y2, rc_x1, rc_x2)]:
            if ry2 > ry1 and rx2 > rx1:
                rois.append(frame[ry1:ry2, rx1:rx2].mean(axis=(0, 1)))
        
        return np.mean(rois, axis=0).tolist() if rois else [0.0, 0.0, 0.0]

    use_mp = mp_face_detection is not None
    face_detector = None
    if use_mp:
        try:
            face_detector = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
        except:
            use_mp = False

    cascade = _get_face_cascade() if not use_mp else None

    for i, frame in enumerate(frames):
        face_box = None
        if i % 30 == 0 or last_face_box is None:
            if use_mp:
                results = face_detector.process(frame)
                if results.detections:
                    bbox = results.detections[0].location_data.relative_bounding_box
                    h, w, _ = frame.shape
                    face_box = [int(bbox.xmin * w), int(bbox.ymin * h), int(bbox.width * w), int(bbox.height * h)]
            else:
                if cascade:
                    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                    faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))
                    if len(faces) > 0:
                        face_box = max(faces, key=lambda f: f[2] * f[3]).tolist()
            
            if face_box:
                last_face_box = face_box
        else:
            face_box = last_face_box

        if face_box:
            rgb_signals.append(_extract_from_box(frame, face_box))
        else:
            rgb_signals.append([0.0, 0.0, 0.0])

    if use_mp and face_detector:
        face_detector.close()

    if not rgb_signals or all(np.array_equal(s, [0.0, 0.0, 0.0]) for s in rgb_signals):
        return None

    return np.array(rgb_signals, dtype=np.float64)


def _bandpass_filter(signal: np.ndarray, lowcut: float, highcut: float, fs: float, order: int = 4) -> np.ndarray:
    nyquist = 0.5 * fs
    low, high = max(lowcut / nyquist, 0.001), min(highcut / nyquist, 0.999)
    if low >= high: return signal
    b, a = butter(order, [low, high], btype="band")
    return filtfilt(b, a, signal)


def _estimate_rate_fft(signal: np.ndarray, fs: float, freq_low: float, freq_high: float) -> Optional[float]:
    if len(signal) < 10: return None
    signal = signal - np.mean(signal)
    window = np.hanning(len(signal))
    signal = signal * window
    freqs = rfftfreq(len(signal), d=1.0 / fs)
    fft_vals = np.abs(rfft(signal))
    mask = (freqs >= freq_low) & (freqs <= freq_high)
    if not np.any(mask): return None
    peak_idx = np.argmax(fft_vals[mask])
    rate = freqs[mask][peak_idx] * 60.0
    return round(rate, 1)


def _compute_sqi(signal: np.ndarray, fs: float, freq_low: float = 0.7, freq_high: float = 3.5) -> float:
    if len(signal) < 10: return 0.0
    signal = signal - np.mean(signal)
    freqs = rfftfreq(len(signal), d=1.0 / fs)
    fft_vals = np.abs(rfft(signal)) ** 2
    total_power = np.sum(fft_vals)
    if total_power == 0: return 0.0
    mask = (freqs >= freq_low) & (freqs <= freq_high)
    return round(float(np.clip(np.sum(fft_vals[mask]) / total_power, 0.0, 1.0)), 3)


def _chrom_algorithm(rgb_signals: np.ndarray) -> np.ndarray:
    mean_rgb = rgb_signals.mean(axis=0)
    mean_rgb[mean_rgb == 0] = 1.0
    normalized = rgb_signals / mean_rgb
    r, g, b = normalized[:, 0], normalized[:, 1], normalized[:, 2]
    xs, ys = 3.0 * r - 2.0 * g, 1.5 * r + g - 1.5 * b
    std_xs, std_ys = np.std(xs), np.std(ys)
    if std_ys == 0: return xs
    return xs - (std_xs / std_ys) * ys


def process_chunk_chrom(frames: np.ndarray, fps: float) -> Optional[dict]:
    rgb_signals = _detect_face_roi(frames)
    if rgb_signals is None: return None
    rppg_signal = _chrom_algorithm(rgb_signals)
    hr_signal = _bandpass_filter(rppg_signal, 0.7, 3.5, fps)
    bpm = _estimate_rate_fft(hr_signal, fps, 0.7, 3.5)
    rr_signal = _bandpass_filter(rppg_signal, 0.1, 0.5, fps)
    rr = _estimate_rate_fft(rr_signal, fps, 0.1, 0.5)
    sqi = _compute_sqi(hr_signal, fps)
    if bpm is None: return None
    return {"bpm": bpm, "rr": rr, "sqi": sqi}


def detect_face_in_frame(frame: np.ndarray) -> dict:
    """Robust face detection for a single frame."""
    try:
        import mediapipe as mp
        if hasattr(mp, 'solutions'):
            mp_face_detection = mp.solutions.face_detection
            with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_detection:
                results = face_detection.process(frame)
                if results.detections:
                    bbox = results.detections[0].location_data.relative_bounding_box
                    h, w, _ = frame.shape
                    return {"face_detected": True, "box": [int(bbox.xmin * w), int(bbox.ymin * h), int(bbox.width * w), int(bbox.height * h)]}
    except:
        pass
    cascade = _get_face_cascade()
    if cascade:
        import cv2
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))
        if len(faces) > 0:
            return {"face_detected": True, "box": max(faces, key=lambda f: f[2] * f[3]).tolist()}
    return {"face_detected": False, "box": None}


def process_chunk(frames: np.ndarray, fps: float) -> dict:
    """Unified processor with strict face detection gating."""
    start = time.perf_counter()
    
    # 1. Check for face first (using middle frame for speed)
    face_check = detect_face_in_frame(frames[len(frames)//2])
    
    if not face_check["face_detected"]:
        # CRITICAL: If no face, return failure immediately
        elapsed = (time.perf_counter() - start) * 1000
        return {
            "bpm": None, "rr": None, "sqi": 0.0, "method": "failed",
            "face_detected": False, "processing_ms": round(elapsed, 1)
        }

    # 2. Try Mode A: open-rppg
    result = process_chunk_rppg(frames, fps)
    if result is not None:
        elapsed = (time.perf_counter() - start) * 1000
        return {**result, "method": "open-rppg", "face_detected": True, "processing_ms": round(elapsed, 1)}

    # 3. Fallback to Mode B: CHROM
    result = process_chunk_chrom(frames, fps)
    elapsed = (time.perf_counter() - start) * 1000
    if result is not None:
        return {**result, "method": "chrom", "face_detected": True, "processing_ms": round(elapsed, 1)}

    return {
        "bpm": None, "rr": None, "sqi": 0.0, "method": "failed",
        "face_detected": False, "processing_ms": round(elapsed, 1)
    }
