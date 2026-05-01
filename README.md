# Near Real-Time rPPG Integration

A prototype that processes a face video incrementally in 5-second chunks to estimate heart rate (BPM) and respiratory rate (RR) in near real-time.

## How It Works

Extracts the **Blood Volume Pulse (BVP)** using **remote photoplethysmography (rPPG)** via the **CHROM** algorithm:

1. **ROI Extraction**: Uses **Haar Cascades** to detect the face and isolate the forehead/cheeks.
2. **Spatial Pooling**: Averages RGB pixels across the Region of Interest (ROI) to form a time-series signal.
3. **Specular Reflection Cancellation**: Projects RGB into orthogonal chrominance signals ($X_s = 3R - 2G$, $Y_s = 1.5R + G - 1.5B$) and combines them ($S = X_s - \alpha Y_s$) to eliminate lighting and motion noise.
4. **Frequency Analysis**: Applies a **Bandpass Filter** (0.7-3.5 Hz) and **Fast Fourier Transform (FFT)** to extract the dominant BPM frequency.

## Setup

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Sample Output

The backend streams chunk results incrementally via Server-Sent Events (SSE):

```json
{
  "type": "chunk",
  "chunk": 1,
  "time_label": "0-5s",
  "bpm": 72.5,
  "rr": 16.2,
  "sqi": 0.85,
  "method": "chrom"
}
```

## Failure Cases & Mitigations

- **Motion Blur**: Addressed by calculating a Signal Quality Index (SQI). The final result is a weighted median, ensuring noisy chunks are ignored.
- **Poor Lighting / Skin Tone Variance**: If the primary deep learning model (`open-rppg`) fails or lacks confidence, the system instantly falls back to the robust classical CHROM algorithm.
