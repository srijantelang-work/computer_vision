import { Activity, Wind, Clock, AlertTriangle, CheckCircle2 } from 'lucide-react';
import './ChunkResults.css';

export default function ChunkResults({ chunks }) {
  if (!chunks || chunks.length === 0) return null;

  return (
    <div className="chunks-grid">
      {chunks.map((chunk) => (
        <div 
          key={chunk.chunk} 
          className={`chunk-card glass-panel animate-fade-in ${
            chunk.sqi < 0.5 ? 'low-quality' : ''
          }`}
          style={{ animationDelay: `${(chunk.chunk % 10) * 0.1}s` }}
        >
          <div className="chunk-header">
            <span className="chunk-badge">Chunk {chunk.chunk}</span>
            <span className="chunk-time">
              <Clock size={12} /> {chunk.time_label}
            </span>
          </div>

          <div className="metrics-row">
            <div className="metric-box hr">
              <div className="metric-label">Heart Rate</div>
              <div className="metric-value">
                {chunk.bpm ? (
                  <>
                    <span className="value">{chunk.bpm}</span>
                    <span className="unit">BPM</span>
                  </>
                ) : (
                  <span className="value-none">--</span>
                )}
              </div>
              <Activity className="metric-icon hr-icon" size={24} />
            </div>

            <div className="metric-box rr">
              <div className="metric-label">Resp. Rate</div>
              <div className="metric-value">
                {chunk.rr ? (
                  <>
                    <span className="value">{chunk.rr}</span>
                    <span className="unit">B/M</span>
                  </>
                ) : (
                  <span className="value-none">--</span>
                )}
              </div>
              <Wind className="metric-icon rr-icon" size={24} />
            </div>
          </div>

          <div className="chunk-footer">
            <div className="quality-indicator">
              <div className="sqi-label">Signal Quality (SQI)</div>
              <div className="sqi-bar-container">
                <div 
                  className={`sqi-bar ${chunk.sqi >= 0.7 ? 'good' : chunk.sqi >= 0.4 ? 'fair' : 'poor'}`}
                  style={{ width: `${chunk.sqi * 100}%` }}
                />
              </div>
            </div>
            
            <div className="status-icons">
              {chunk.face_detected ? (
                <CheckCircle2 size={16} className="text-success" title="Face Detected" />
              ) : (
                <AlertTriangle size={16} className="text-danger" title="No Face Detected" />
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
