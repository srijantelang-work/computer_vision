import { Activity, Heart, Wind, Zap, CheckCircle2, ShieldCheck, AlertCircle } from 'lucide-react';
import './FinalSummary.css';

export default function FinalSummary({ overall }) {
  if (!overall) return null;

  const isGoodQuality = overall.avg_sqi >= 0.7;
  const isFairQuality = overall.avg_sqi >= 0.4 && overall.avg_sqi < 0.7;

  return (
    <div className="final-summary-container animate-fade-in">
      <div className="hero-metrics">
        {/* Heart Rate Hero */}
        <div className="hero-card hr-hero glass-panel">
          <div className="hero-icon-bg">
            <Heart size={80} />
          </div>
          <div className="hero-content">
            <h3>Overall Heart Rate</h3>
            <div className="hero-value-container">
              {overall.overall_bpm ? (
                <>
                  <span className="hero-value text-accent">{overall.overall_bpm}</span>
                  <span className="hero-unit">BPM</span>
                </>
              ) : (
                <span className="hero-value text-muted">Failed</span>
              )}
            </div>
            <div className="hero-footer">
              <Activity size={14} />
              <span>Weighted median across {overall.valid_chunks} chunks</span>
            </div>
          </div>
        </div>

        {/* Respiratory Rate Hero */}
        <div className="hero-card rr-hero glass-panel">
          <div className="hero-icon-bg">
            <Wind size={80} />
          </div>
          <div className="hero-content">
            <h3>Respiratory Rate</h3>
            <div className="hero-value-container">
              {overall.overall_rr ? (
                <>
                  <span className="hero-value text-info">{overall.overall_rr}</span>
                  <span className="hero-unit">Breaths/min</span>
                </>
              ) : (
                <span className="hero-value text-muted">--</span>
              )}
            </div>
            <div className="hero-footer">
              <Wind size={14} />
              <span>Extracted via low-frequency HRV</span>
            </div>
          </div>
        </div>
      </div>

      {/* Meta Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card glass-panel">
          <div className="stat-header">
            <ShieldCheck size={18} className={isGoodQuality ? 'text-accent' : isFairQuality ? 'text-warning' : 'text-danger'} />
            <h4>Signal Quality</h4>
          </div>
          <div className="stat-body">
            <div className="stat-main">
              <span className="stat-number">{overall.avg_sqi.toFixed(2)}</span>
              <span className={`quality-badge ${overall.signal_quality}`}>
                {overall.signal_quality.toUpperCase()}
              </span>
            </div>
          </div>
        </div>

        <div className="stat-card glass-panel">
          <div className="stat-header">
            <CheckCircle2 size={18} className="text-accent" />
            <h4>Face Detection</h4>
          </div>
          <div className="stat-body">
            <div className="stat-main">
              <span className="stat-number">{(overall.face_detection_rate * 100).toFixed(0)}%</span>
              <span className="stat-sub">success rate</span>
            </div>
          </div>
        </div>

        <div className="stat-card glass-panel">
          <div className="stat-header">
            <Zap size={18} className="text-warning" />
            <h4>Pipeline Latency</h4>
          </div>
          <div className="stat-body">
            <div className="stat-main">
              <span className="stat-number">{(overall.performance.total_pipeline_ms / 1000).toFixed(2)}</span>
              <span className="stat-sub">seconds total</span>
            </div>
            <div className="stat-footer">
              ~{overall.performance.avg_chunk_latency_ms.toFixed(0)}ms per chunk
            </div>
          </div>
        </div>

        <div className="stat-card glass-panel">
          <div className="stat-header">
            <AlertCircle size={18} className="text-info" />
            <h4>Methods Used</h4>
          </div>
          <div className="stat-body">
            <div className="method-tags">
              {overall.methods_used.map(m => (
                <span key={m} className="method-tag">{m}</span>
              ))}
            </div>
            <div className="stat-footer mt-auto">
              Processed {overall.performance.total_frames_processed} frames
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
