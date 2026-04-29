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


def process_chunk_rppg(frames: np.ndarray, fps: float) -> Optional[dict]:
    """
    Process a chunk of frames using the open-rppg deep learning model.
    
    Args:
        frames: numpy array of shape (N, H, W, 3), dtype uint8, RGB
        fps: video framerate
    
    Returns:
        dict with 'bpm', 'rr', 'sqi' or None if processing fails
    """
    global _rppg_model, _rppg_available

    if not _rppg_available:
        if _rppg_model is None:
            _init_rppg_model()
        if not _rppg_available:
            return None

    try:
        result = _rppg_model.process_video_tensor(frames, fps=fps)

        bpm = result.get("hr")
        sqi = result.get("SQI", 0.0)

        # Extract respiratory rate from HRV metrics if available
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

# Initialize Haar cascade for face detection (built into OpenCV)
_face_cascade = None


def _get_face_cascade():
    """Lazily load the Haar cascade face detector."""
    global _face_cascade
    if _face_cascade is None:
        import cv2
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _face_cascade = cv2.CascadeClassifier(cascade_path)
        if _face_cascade.empty():
            logger.error(f"Failed to load Haar cascade from {cascade_path}")
            _face_cascade = None
    return _face_cascade


def _detect_face_roi(frames: np.ndarray) -> Optional[np.ndarray]:
    """
    Detect face and extract forehead+cheek ROI using OpenCV Haar cascade.
    
    For each frame, detects the face bounding box, then extracts the
    forehead region (top 30%) and cheek regions (middle 40%) as the ROI
    for mean RGB signal extraction.
    
    Args:
        frames: (N, H, W, 3) uint8 RGB frames
    
    Returns:
        rgb_signals: (N, 3) mean RGB values across the face ROI per frame,
                     or None if face detection fails for all frames
    """
    import cv2

    cascade = _get_face_cascade()
    if cascade is None:
        logger.error("Haar cascade not available.")
        return None

    rgb_signals = []
    last_face_box = None  # Track face across frames

    for frame in frames:
        # Convert RGB → grayscale for detection
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

        # Detect faces
        faces = cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
        )

        if len(faces) > 0:
            # Use the largest face
            face_box = max(faces, key=lambda f: f[2] * f[3])
            last_face_box = face_box
        elif last_face_box is not None:
            # Use last known face position (tracking)
            face_box = last_face_box
        else:
            # No face ever detected
            rgb_signals.append([0.0, 0.0, 0.0])
            continue

        x, y, w, h = face_box

        # Extract ROI: forehead (top 30%) + cheeks (middle 30-70%)
        # Forehead ROI
        fh_y1 = max(0, y + int(0.05 * h))
        fh_y2 = y + int(0.35 * h)
        fh_x1 = x + int(0.2 * w)
        fh_x2 = x + int(0.8 * w)

        # Left cheek ROI
        lc_y1 = y + int(0.4 * h)
        lc_y2 = y + int(0.7 * h)
        lc_x1 = x + int(0.05 * w)
        lc_x2 = x + int(0.35 * w)

        # Right cheek ROI
        rc_y1 = y + int(0.4 * h)
        rc_y2 = y + int(0.7 * h)
        rc_x1 = x + int(0.65 * w)
        rc_x2 = x + int(0.95 * w)

        # Clamp to frame bounds
        fh = frame.shape[0]
        fw = frame.shape[1]

        def _clamp_roi(y1, y2, x1, x2):
            return (
                max(0, min(y1, fh)),
                max(0, min(y2, fh)),
                max(0, min(x1, fw)),
                max(0, min(x2, fw)),
            )

        fh_y1, fh_y2, fh_x1, fh_x2 = _clamp_roi(fh_y1, fh_y2, fh_x1, fh_x2)
        lc_y1, lc_y2, lc_x1, lc_x2 = _clamp_roi(lc_y1, lc_y2, lc_x1, lc_x2)
        rc_y1, rc_y2, rc_x1, rc_x2 = _clamp_roi(rc_y1, rc_y2, rc_x1, rc_x2)

        # Extract mean RGB from each ROI and average them
        rois = []
        for (ry1, ry2, rx1, rx2) in [(fh_y1, fh_y2, fh_x1, fh_x2),
                                       (lc_y1, lc_y2, lc_x1, lc_x2),
                                       (rc_y1, rc_y2, rc_x1, rc_x2)]:
            if ry2 > ry1 and rx2 > rx1:
                roi = frame[ry1:ry2, rx1:rx2]
                rois.append(roi.mean(axis=(0, 1)))

        if rois:
            mean_rgb = np.mean(rois, axis=0)
            rgb_signals.append(mean_rgb.tolist())
        else:
            rgb_signals.append([0.0, 0.0, 0.0])

    if not rgb_signals or all(s == [0.0, 0.0, 0.0] for s in rgb_signals):
        return None

    return np.array(rgb_signals, dtype=np.float64)


def _bandpass_filter(signal: np.ndarray, lowcut: float, highcut: float, fs: float, order: int = 4) -> np.ndarray:
    """Apply a Butterworth bandpass filter."""
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist

    # Clamp to valid range
    low = max(low, 0.001)
    high = min(high, 0.999)

    if low >= high:
        return signal

    b, a = butter(order, [low, high], btype="band")
    return filtfilt(b, a, signal)


def _estimate_rate_fft(signal: np.ndarray, fs: float, freq_low: float, freq_high: float) -> Optional[float]:
    """
    Estimate rate (BPM or breaths/min) from a signal using FFT.
    
    Args:
        signal: 1D time series
        fs: sampling frequency (FPS)
        freq_low: lower bound of frequency range (Hz)
        freq_high: upper bound of frequency range (Hz)
    
    Returns:
        rate in beats/breaths per minute, or None if estimation fails
    """
    if len(signal) < 10:
        return None

    # Remove DC component
    signal = signal - np.mean(signal)

    # Apply Hann window
    window = np.hanning(len(signal))
    signal = signal * window

    # FFT
    freqs = rfftfreq(len(signal), d=1.0 / fs)
    fft_vals = np.abs(rfft(signal))

    # Mask to frequency range of interest
    mask = (freqs >= freq_low) & (freqs <= freq_high)
    if not np.any(mask):
        return None

    masked_freqs = freqs[mask]
    masked_fft = fft_vals[mask]

    # Find dominant frequency
    peak_idx = np.argmax(masked_fft)
    dominant_freq = masked_freqs[peak_idx]

    # Convert to rate per minute
    rate = dominant_freq * 60.0
    return round(rate, 1)


def _compute_sqi(signal: np.ndarray, fs: float, freq_low: float = 0.7, freq_high: float = 3.5) -> float:
    """
    Compute Signal Quality Index (SQI) as the ratio of spectral power
    in the physiological range to total spectral power.
    
    Returns value between 0.0 (poor) and 1.0 (excellent).
    """
    if len(signal) < 10:
        return 0.0

    signal = signal - np.mean(signal)
    freqs = rfftfreq(len(signal), d=1.0 / fs)
    fft_vals = np.abs(rfft(signal)) ** 2  # Power spectrum

    total_power = np.sum(fft_vals)
    if total_power == 0:
        return 0.0

    mask = (freqs >= freq_low) & (freqs <= freq_high)
    signal_power = np.sum(fft_vals[mask])

    sqi = signal_power / total_power
    return round(float(np.clip(sqi, 0.0, 1.0)), 3)


def _chrom_algorithm(rgb_signals: np.ndarray) -> np.ndarray:
    """
    CHROM (Chrominance-based) algorithm for rPPG signal extraction.
    
    Reference: De Haan & Jeanne, "Robust Pulse Rate from Chrominance-Based rPPG", 2013
    
    Args:
        rgb_signals: (N, 3) array of mean RGB values per frame
    
    Returns:
        rppg_signal: (N,) extracted pulse signal
    """
    # Normalize each channel by its mean
    mean_rgb = rgb_signals.mean(axis=0)
    mean_rgb[mean_rgb == 0] = 1.0  # Avoid division by zero
    normalized = rgb_signals / mean_rgb

    # CHROM: build chrominance signals
    # Xs = 3R - 2G, Ys = 1.5R + G - 1.5B
    r = normalized[:, 0]
    g = normalized[:, 1]
    b = normalized[:, 2]

    xs = 3.0 * r - 2.0 * g
    ys = 1.5 * r + g - 1.5 * b

    # Combine using standard deviation ratio
    std_xs = np.std(xs)
    std_ys = np.std(ys)

    if std_ys == 0:
        return xs

    alpha = std_xs / std_ys
    rppg_signal = xs - alpha * ys

    return rppg_signal


def process_chunk_chrom(frames: np.ndarray, fps: float) -> Optional[dict]:
    """
    Process a chunk of frames using the classical CHROM algorithm.
    
    Args:
        frames: numpy array of shape (N, H, W, 3), dtype uint8, RGB
        fps: video framerate
    
    Returns:
        dict with 'bpm', 'rr', 'sqi' or None if processing fails
    """
    # Step 1: Face detection + ROI extraction
    rgb_signals = _detect_face_roi(frames)
    if rgb_signals is None:
        logger.warning("CHROM: Face detection failed for this chunk.")
        return None

    # Step 2: CHROM algorithm → raw rPPG signal
    rppg_signal = _chrom_algorithm(rgb_signals)

    # Step 3: Bandpass filter for heart rate (0.7–3.5 Hz → 42–210 BPM)
    hr_signal = _bandpass_filter(rppg_signal, 0.7, 3.5, fps)

    # Step 4: Estimate BPM via FFT
    bpm = _estimate_rate_fft(hr_signal, fps, 0.7, 3.5)

    # Step 5: Respiratory rate (0.1–0.5 Hz → 6–30 breaths/min)
    rr_signal = _bandpass_filter(rppg_signal, 0.1, 0.5, fps)
    rr = _estimate_rate_fft(rr_signal, fps, 0.1, 0.5)

    # Step 6: Signal quality
    sqi = _compute_sqi(hr_signal, fps)

    if bpm is None:
        return None

    return {
        "bpm": bpm,
        "rr": rr,
        "sqi": sqi,
    }


# ─────────────────────────────────────────────
# Public API: Unified processor
# ─────────────────────────────────────────────

def process_chunk(frames: np.ndarray, fps: float) -> dict:
    """
    Process a 5-second chunk of video frames to estimate heart rate and respiratory rate.
    
    Tries the open-rppg deep learning model first; falls back to CHROM if that fails.
    
    Args:
        frames: numpy array of shape (N, H, W, 3), dtype uint8, RGB color space
        fps: video framerate
    
    Returns:
        dict with keys:
            - bpm (float | None): estimated heart rate in beats per minute
            - rr (float | None): estimated respiratory rate in breaths per minute
            - sqi (float): signal quality index, 0.0–1.0
            - method (str): "open-rppg" or "chrom"
            - face_detected (bool): whether a face was found
    """
    start = time.perf_counter()

    # Try Mode A: open-rppg
    result = process_chunk_rppg(frames, fps)
    if result is not None:
        elapsed = (time.perf_counter() - start) * 1000
        return {
            **result,
            "method": "open-rppg",
            "face_detected": True,
            "processing_ms": round(elapsed, 1),
        }

    # Fallback to Mode B: CHROM
    logger.info("Falling back to CHROM algorithm.")
    result = process_chunk_chrom(frames, fps)
    elapsed = (time.perf_counter() - start) * 1000

    if result is not None:
        return {
            **result,
            "method": "chrom",
            "face_detected": True,
            "processing_ms": round(elapsed, 1),
        }

    # Complete failure — no face, no signal
    elapsed = (time.perf_counter() - start) * 1000
    return {
        "bpm": None,
        "rr": None,
        "sqi": 0.0,
        "method": "failed",
        "face_detected": False,
        "processing_ms": round(elapsed, 1),
    }
