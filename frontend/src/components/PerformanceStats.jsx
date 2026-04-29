import { Server, Clock, CheckCircle2, AlertTriangle } from 'lucide-react';
import './PerformanceStats.css';

export default function PerformanceStats({ chunks, overall }) {
  if (!chunks || chunks.length === 0 || !overall) return null;

  return (
    <div className="perf-stats-container glass-panel animate-fade-in" style={{ animationDelay: '0.3s' }}>
      <div className="perf-header">
        <Server size={20} className="text-warning" />
        <h3>Pipeline Telemetry</h3>
      </div>

      <div className="table-responsive">
        <table className="perf-table">
          <thead>
            <tr>
              <th>Chunk</th>
              <th>Time Range</th>
              <th>Method</th>
              <th>Face Det.</th>
              <th>Latency (ms)</th>
              <th>Frames</th>
            </tr>
          </thead>
          <tbody>
            {chunks.map((chunk) => (
              <tr key={chunk.chunk} className={chunk.sqi < 0.5 ? 'row-dim' : ''}>
                <td><span className="badge-outline">#{chunk.chunk}</span></td>
                <td className="text-secondary">{chunk.time_label}</td>
                <td>
                  <span className="method-pill">{chunk.method}</span>
                </td>
                <td>
                  {chunk.face_detected ? (
                    <CheckCircle2 size={16} className="text-accent inline-icon" />
                  ) : (
                    <AlertTriangle size={16} className="text-danger inline-icon" />
                  )}
                </td>
                <td className="font-mono">
                  <div className="latency-cell">
                    {chunk.latency_ms.toFixed(1)}
                    <div 
                      className={`latency-bar ${chunk.latency_ms > 1000 ? 'high' : chunk.latency_ms > 500 ? 'med' : 'low'}`}
                      style={{ width: `${Math.min((chunk.latency_ms / Math.max(overall.performance.max_chunk_latency_ms, 1)) * 100, 100)}%` }}
                    />
                  </div>
                </td>
                <td className="text-tertiary">{chunk.frames_processed}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan="4" className="text-right text-secondary">Total Processing Time:</td>
              <td colSpan="2" className="font-mono text-primary">
                <Clock size={14} className="inline-icon text-warning" />
                {(overall.performance.total_pipeline_ms / 1000).toFixed(2)}s
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
