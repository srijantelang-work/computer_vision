import { useState, useEffect, useRef } from 'react';
import { Activity, Loader2, AlertCircle } from 'lucide-react';
import VideoUploader from './components/VideoUploader';
import ChunkResults from './components/ChunkResults';
import FinalSummary from './components/FinalSummary';
import BPMChart from './components/BPMChart';
import PerformanceStats from './components/PerformanceStats';
import './App.css';

function App() {
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState('idle'); // idle, uploading, processing, complete, error
  const [metadata, setMetadata] = useState(null);
  const [chunks, setChunks] = useState([]);
  const [overall, setOverall] = useState(null);
  const [error, setError] = useState(null);
  
  const eventSourceRef = useRef(null);

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const startSSEStream = (id) => {
    setStatus('processing');
    setChunks([]);
    setOverall(null);
    setMetadata(null);
    setError(null);

    // If we have proxy enabled, we can use /api/stream... 
    // Wait, Vite proxy handles /api, but EventSource uses the browser directly.
    // If we run `npm run dev` (Vite port 5173), we MUST use the proxy route or absolute URL.
    // Let's use the proxy route.
    const es = new EventSource(`/api/stream/${id}`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('SSE Event:', data.type, data);

        if (data.type === 'metadata') {
          setMetadata(data.video);
        } else if (data.type === 'chunk') {
          setChunks((prev) => [...prev, data]);
        } else if (data.type === 'complete') {
          setOverall(data.overall);
          setStatus('complete');
          es.close();
        } else if (data.type === 'error') {
          setError(data.message || 'Processing pipeline error');
          setStatus('error');
          es.close();
        }
      } catch (err) {
        console.error('Error parsing SSE data:', err);
      }
    };

    es.onerror = (err) => {
      console.error('SSE connection error:', err);
      // Only set error if we aren't already complete
      if (status !== 'complete') {
        setError('Lost connection to processing server');
        setStatus('error');
      }
      es.close();
    };
  };

  const handleUploadStart = async (formData) => {
    try {
      setStatus('uploading');
      setError(null);
      setChunks([]);
      setOverall(null);

      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const data = await response.json();
      setJobId(data.job_id);
      
      // Start listening to the SSE stream
      startSSEStream(data.job_id);
      
    } catch (err) {
      console.error('Upload error:', err);
      setError(err.message);
      setStatus('error');
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
                {status === 'uploading' && <><Loader2 size={16} className="spinner" /> Uploading Video...</>}
                {status === 'processing' && <><Loader2 size={16} className="spinner" /> Processing Pipeline Running</>}
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
