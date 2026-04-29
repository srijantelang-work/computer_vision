Near Real-Time rPPG Integration — Implementation Plan
Build a prototype web app that takes a 60-second face video, processes it in 5-second chunks, and generates per-chunk BPM, overall BPM, respiratory rate (bonus), and runtime/performance metrics.

Resolved Decisions
Question	Decision
Hardware	MacBook Air M4 (Apple Silicon, no NVIDIA GPU). Will use open-rppg with CPU/MPS backend; CHROM/POS classical fallback ready.
Deployment	Google Cloud Run for backend. Vercel for frontend (or serve static from Cloud Run).
Test Video	User has a 60-second face video available.
Timeline	5 days confirmed.
Frontend	React (Vite) with SSE streaming.
Architecture Overview
Upload .mp4/.avi
Split into 5s chunks
Per chunk
SSE stream
After all chunks
Final result
User Browser\n(React on Vercel)
FastAPI on Cloud Run
Chunk Pipeline
Face Detection\n(MediaPipe)
rPPG Signal Extraction\n(open-rppg / CHROM)
BPM + RR Estimation\n(FFT + Bandpass)
Aggregation\n(Weighted Median)
Proposed Changes
Component 1: Backend (FastAPI + Python)
[NEW] backend/main.py
FastAPI application with three endpoints:

Endpoint	Method	Description
/upload	POST	Accept video upload, validate format, assign job_id, kick off background processing
/stream/{job_id}	GET (SSE)	Stream chunk results as they complete
/result/{job_id}	GET	Return final aggregated result
CORS middleware for frontend
Background task processing via asyncio
Temp file storage for uploaded videos
[NEW] backend/chunk_pipeline.py
OpenCV reads uploaded video → extract FPS, total frames, duration
Split into 5-second windows (frames_per_chunk = 5 * FPS)
Per-chunk: extract frames → pass to rppg_processor → time it → push result to SSE queue
Edge case: last chunk < 5s → process but flag it
[NEW] backend/rppg_processor.py
Dual-mode design:

Primary: open-rppg with EfficientPhys.rlap model → process_video_tensor(frames, fps) → returns HR, RR, SQI
Fallback: Pure-numpy CHROM algorithm (MediaPipe face detection → ROI extraction → chrominance signal → bandpass filter → FFT → BPM)
Auto-fallback if DL model fails or times out
NOTE

M4 MacBook has no CUDA. open-rppg uses JAX which has experimental Metal/MPS support. If JAX performance is poor on M4, the CHROM fallback will be fast (~50ms per chunk on CPU). On Cloud Run (x86 Linux), JAX will use CPU by default which should be adequate for a 5-second chunk.

[NEW] backend/metrics.py
Overall BPM: Weighted median across chunks (weighted by SQI)
Overall RR: Same weighted median
Signal Quality: Average SQI → "good" / "fair" / "poor"
Performance: per-chunk latency, total pipeline time, face detection confidence, throughput
[NEW] backend/requirements.txt
[NEW] backend/Dockerfile
For Google Cloud Run deployment — Python 3.11 slim base, install deps, expose port 8080.

Component 2: Frontend (React + Vite)
[NEW] frontend/ (scaffolded via create-vite)
Component	Purpose
VideoUploader.jsx	Drag-and-drop upload, video preview, format validation, progress
ChunkResults.jsx	Live-updating cards via SSE — chunk #, time range, BPM, RR, latency, confidence badge
FinalSummary.jsx	Hero display: Overall BPM, RR, signal quality, total time
BPMChart.jsx	Line chart (Recharts) — BPM trend across chunks
PerformanceStats.jsx	Table: per-chunk latency, confidence, signal quality
Dark theme, medical/scientific aesthetic, green accent for vital signs.

Component 3: Project Root
[NEW] README.md
Project overview, architecture diagram, setup instructions
Sample output JSON + screenshot
Model performance notes, failure cases
AI usage notes (required by assignment)
Deployment link
Failure Cases
Scenario	Detection	Handling
Motion blur / head movement	SQI < threshold	Mark "low confidence", exclude from aggregation
Poor lighting	RGB variance too low	Return bpm: null, flag "insufficient signal"
< 15 FPS video	FPS check on upload	Warn user, attempt with reduced accuracy note
No face detected	MediaPipe returns nothing	Skip chunk, bpm: null, log "face not found"
Video too short	Duration < 5s	Reject upload with error
Skin tone variance	N/A	CHROM handles this better than POS
Project Structure
rppg-prototype/
├── backend/
│   ├── main.py
│   ├── rppg_processor.py
│   ├── chunk_pipeline.py
│   ├── metrics.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── components/
│   │   │   ├── VideoUploader.jsx
│   │   │   ├── ChunkResults.jsx
│   │   │   ├── FinalSummary.jsx
│   │   │   ├── BPMChart.jsx
│   │   │   └── PerformanceStats.jsx
│   │   └── main.jsx
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── sample_output.json
├── README.md
└── Docs/
    ├── assignment.md
    └── plan.md
Build Schedule
Day	Focus	Deliverables
Day 1	Backend core	rppg_processor.py, chunk_pipeline.py, basic main.py. Test locally with sample video.
Day 2	Streaming + API	SSE streaming, aggregation, full API. End-to-end via curl.
Day 3	Frontend	React app, all components, SSE integration, connect to backend.
Day 4	Polish + Metrics	Charts, performance table, error handling, dark theme, test video validation.
Day 5	Deploy + Docs	Dockerize, deploy to Cloud Run, write README, sample output, AI usage notes.
Verification Plan
Automated Tests
Chunking logic (correct frame counts)
CHROM algorithm with synthetic sine-wave signals (known BPM → verify)
Aggregation (weighted median correctness)
API endpoints (upload validation, SSE streaming)
Manual Verification
Upload test video → watch chunk cards appear → verify final summary
Compare BPM against ground truth (if available)
Edge case testing (motion, poor lighting, no face)
Latency benchmarking on M4 + Cloud Run
Deployment Verification
Deploy to Cloud Run, test from external network
Verify shareable link works end-to-end