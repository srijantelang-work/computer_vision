import { useState, useEffect, useRef, useCallback } from 'react';
import { Activity, Loader2, AlertCircle } from 'lucide-react';
import VideoUploader from './components/VideoUploader';
import ChunkResults from './components/ChunkResults';
import FinalSummary from './components/FinalSummary';
import BPMChart from './components/BPMChart';
import PerformanceStats from './components/PerformanceStats';
import './App.css';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

function App() {
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState('idle'); // idle, uploading, processing, complete, error
  const [metadata, setMetadata] = useState(null);
  const [chunks, setChunks] = useState([]);
  const [overall, setOverall] = useState(null);
  const [error, setError] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0); // 0 to 100
  const [logs, setLogs] = useState([]);

  const addLog = useCallback((msg) => {
    const time = new Date().toLocaleTimeString([], { hour12: false });
    setLogs((prev) => [`[${time}] ${msg}`, ...prev].slice(0, 50));
    console.log(`[Frontend Log] ${msg}`);
  }, []);
  
  const eventSourceRef = useRef(null);
  // Use a ref to track the real-time status so closures never go stale
  const statusRef = useRef('idle');

  // Keep statusRef in sync with status state
  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const startSSEStream = useCallback((id) => {
    setStatus('processing');
    statusRef.current = 'processing';
    setChunks([]);
    setOverall(null);
    setMetadata(null);
    setError(null);

    console.log(`[SSE] Opening EventSource to ${API_BASE}/stream/${id}`);
    const es = new EventSource(`${API_BASE}/stream/${id}`);
    eventSourceRef.current = es;

    es.onopen = () => {
      console.log('[SSE] Connection opened successfully');
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[SSE] Event received:', data.type, data);

        if (data.type === 'metadata') {
          setMetadata(data.video);
          addLog(`Metadata received: ${data.video.duration_s}s video at ${data.video.fps} FPS`);
        } else if (data.type === 'chunk') {
          setChunks((prev) => [...prev, data]);
          addLog(`Chunk ${data.chunk} processed: ${data.bpm} BPM (SQI: ${data.sqi.toFixed(3)})`);
        } else if (data.type === 'complete') {
          addLog(`Analysis complete! Final BPM: ${data.overall.bpm}`);
          setOverall(data.overall);
          setStatus('complete');
          statusRef.current = 'complete';
          es.close();
        } else if (data.type === 'error') {
          console.error('[SSE] Error event from server:', data.message);
          setError(data.message || 'Processing pipeline error');
          setStatus('error');
          statusRef.current = 'error';
          es.close();
        }
      } catch (err) {
        console.error('[SSE] Error parsing event data:', err, 'Raw:', event.data);
      }
    };

    es.onerror = (err) => {
      console.error('[SSE] Connection error event fired. ReadyState:', es.readyState);
      
      // readyState: 0=CONNECTING, 1=OPEN, 2=CLOSED
      // If CONNECTING, the browser is retrying automatically — don't kill it.
      // Only treat as fatal if the connection is fully CLOSED.
      if (es.readyState === EventSource.CLOSED) {
        console.error('[SSE] Connection is CLOSED.');
        // Use the ref (not the stale closure variable) to check current status
        if (statusRef.current !== 'complete' && statusRef.current !== 'error') {
          console.error('[SSE] Setting error state — stream died before completion');
          setError('Lost connection to processing server. Try re-uploading.');
          setStatus('error');
          statusRef.current = 'error';
        }
        es.close();
      } else {
        // Browser is auto-reconnecting. Log it but don't kill the stream.
        console.warn('[SSE] Transient error — browser will auto-reconnect.');
      }
    };
  }, []);

  const handleUploadStart = async (formData) => {
    try {
      const file = formData.get('file');
      if (!file) return;

      setStatus('uploading');
      statusRef.current = 'uploading';
      setError(null);
      setChunks([]);
      setOverall(null);
      setUploadProgress(0);

      const CHUNK_SIZE = 1024 * 1024 * 5; // 5MB chunks
      const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
      const localJobId = Math.random().toString(36).substring(2, 10);
      
      addLog(`Starting chunked upload for ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);
      addLog(`Slicing into ${totalChunks} chunks of 5MB each...`);

      for (let i = 0; i < totalChunks; i++) {
        const start = i * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, file.size);
        const chunk = file.slice(start, end);
        
        const chunkFormData = new FormData();
        chunkFormData.append('job_id', localJobId);
        chunkFormData.append('chunk_index', i);
        chunkFormData.append('total_chunks', totalChunks);
        chunkFormData.append('filename', file.name);
        chunkFormData.append('file', chunk);

        addLog(`Uploading part ${i + 1}/${totalChunks}...`);
        const response = await fetch(`${API_BASE}/upload/chunk`, {
          method: 'POST',
          body: chunkFormData,
        });

        if (!response.ok) {
          const errorData = await response.json();
          addLog(`❌ Part ${i + 1} failed: ${errorData.detail || 'Network error'}`);
          throw new Error(errorData.detail || `Upload failed at part ${i + 1}`);
        }
        
        const result = await response.json();
        const progress = Math.round(((i + 1) / totalChunks) * 100);
        setUploadProgress(progress);
        
        if (result.complete) {
          addLog(`✅ All parts uploaded. Server is reassembling file...`);
          setJobId(localJobId);
          startSSEStream(localJobId);
        }
      }
    } catch (err) {
      console.error('[Upload] Error:', err);
      setError(err.message);
      setStatus('error');
      statusRef.current = 'error';
    }
  };

  return (
    <div className="app-container">
      <header className="app-header animate-fade-in">
        <h1 className="app-title">rPPG Vital Signs</h1>
        <p className="app-subtitle">
          Near real-time remote photoplethysmography prototype. 
          Extracts heart rate and respiratory rate from facial video in 5-second chunks.
        </p>
      </header>

      <main className="main-content">
        <div className="sidebar">
          <VideoUploader 
            onUploadStart={handleUploadStart} 
            isProcessing={status === 'uploading' || status === 'processing'} 
          />
          
          {/* Status Indicator */}
          {status !== 'idle' && (
            <div className="glass-panel" style={{ padding: '1rem', marginTop: '1rem' }}>
              <div className="section-title" style={{ marginBottom: '0.5rem', fontSize: '1rem' }}>
                System Status
              </div>
              <div className={`status-badge ${status}`}>
                {status === 'uploading' && <><Loader2 size={16} className="spinner" /> Uploading ({uploadProgress}%)...</>}
                {status === 'processing' && <><Loader2 size={16} className="spinner" /> Processing Pipeline Running ({chunks.length} chunks)</>}
                {status === 'complete' && <><Activity size={16} /> Analysis Complete</>}
                {status === 'error' && <><AlertCircle size={16} /> Error Occurred</>}
              </div>
              
              {error && (
                <div style={{ color: 'var(--danger)', fontSize: '0.875rem', marginTop: '0.5rem' }}>
                  {error}
                </div>
              )}
            </div>
          )}

          {/* Log Console */}
          {logs.length > 0 && (
            <div className="glass-panel" style={{ padding: '1rem', marginTop: '1rem' }}>
              <div className="section-title" style={{ marginBottom: '0.5rem', fontSize: '1rem' }}>
                Event Log
              </div>
              <div className="log-container" style={{ 
                background: 'rgba(0,0,0,0.3)', 
                borderRadius: '8px', 
                padding: '0.75rem', 
                fontSize: '0.75rem', 
                fontFamily: 'monospace',
                maxHeight: '200px',
                overflowY: 'auto',
                color: 'var(--text-secondary)',
                lineHeight: '1.4'
              }}>
                {logs.map((log, i) => (
                  <div key={i} style={{ marginBottom: '4px', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '4px' }}>
                    {log}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="results-area">
          {/* Show Final Summary Hero and Charts if complete */}
          {status === 'complete' && overall && (
            <>
              <FinalSummary overall={overall} />
              <BPMChart chunks={chunks} />
              <PerformanceStats chunks={chunks} overall={overall} />
            </>
          )}

          {/* Show Live Chunks */}
          {(chunks.length > 0 || status === 'processing') && (
            <div className="glass-panel" style={{ padding: '1.5rem' }}>
              <h2 className="section-title">
                <Activity size={20} />
                Live Chunk Analysis
                {status === 'processing' && <Loader2 size={16} className="spinner" style={{ marginLeft: 'auto', color: 'var(--text-tertiary)' }} />}
              </h2>
              
              <ChunkResults chunks={chunks} />
              
              {chunks.length === 0 && status === 'processing' && (
                <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-tertiary)' }}>
                  Extracting frames and awaiting first 5-second chunk...
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
