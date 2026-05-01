import { useState, useRef, useEffect, useCallback } from 'react';
import Webcam from 'react-webcam';
import { Camera, User, UserCheck, UserX, AlertCircle } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

const FaceDetectionTester = () => {
  const webcamRef = useRef(null);
  const [isDetected, setIsDetected] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [error, setError] = useState(null);
  const [lastCheck, setLastCheck] = useState(null);

  const capture = useCallback(async () => {
    if (!webcamRef.current) return;

    const imageSrc = webcamRef.current.getScreenshot();
    if (!imageSrc) return;

    try {
      const response = await fetch(`${API_BASE}/test-face`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageSrc }),
      });

      if (!response.ok) throw new Error('Failed to reach backend');

      const data = await response.json();
      setIsDetected(data.face_detected);
      setLastCheck(new Date().toLocaleTimeString());
      setError(null);
    } catch (err) {
      console.error('Face test failed:', err);
      setError('Connection to backend failed');
    }
  }, []);

  useEffect(() => {
    let interval;
    if (isTesting) {
      interval = setInterval(capture, 1000); // Check every second
    } else {
      setIsDetected(false);
    }
    return () => clearInterval(interval);
  }, [isTesting, capture]);

  return (
    <div className="glass-panel face-tester-container">
      <div className="section-title">
        <Camera size={20} />
        Live Face Detection
      </div>

      <div className="tester-content">
        <div className="webcam-wrapper">
          {isTesting ? (
            <Webcam
              audio={false}
              ref={webcamRef}
              screenshotFormat="image/jpeg"
              videoConstraints={{ width: 320, height: 240, facingMode: "user" }}
              className="webcam-preview"
            />
          ) : (
            <div className="webcam-placeholder">
              <Camera size={48} />
              <p>Camera is off</p>
            </div>
          )}

          {isTesting && (
            <div className={`detection-overlay ${isDetected ? 'detected' : 'not-detected'}`}>
              {isDetected ? <UserCheck size={32} /> : <UserX size={32} />}
            </div>
          )}
        </div>

        <div className="tester-controls">
          <button
            className={`btn-toggle ${isTesting ? 'active' : ''}`}
            onClick={() => setIsTesting(!isTesting)}
          >
            {isTesting ? 'Stop Camera' : 'Start Camera'}
          </button>

          <div className="tester-status">
            <div className={`status-pill ${isDetected ? 'success' : 'neutral'}`}>
              {isDetected ? 'Face Detected' : 'No Face'}
            </div>
            {lastCheck && <span className="last-check">Last check: {lastCheck}</span>}
          </div>

          {error && (
            <div className="tester-error">
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          {isTesting && !isDetected && !error && (
            <div className="tester-tip animate-fade-in" style={{
              marginTop: '0.5rem',
              fontSize: '0.8rem',
              color: 'var(--warning)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.5rem',
              background: 'rgba(245, 158, 11, 0.1)',
              borderRadius: '6px',
              border: '1px solid rgba(245, 158, 11, 0.2)'
            }}>
              <AlertCircle size={14} />
              <span>Face not detected? Try moving closer and ensure good lighting.</span>
            </div>
          )}
        </div>
      </div>

      <div className="tester-instruction">
        Use this to verify that the system can see you clearly before starting a real analysis.
      </div>
    </div>
  );
};

export default FaceDetectionTester;
