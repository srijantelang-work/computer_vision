import { useState, useRef } from 'react';
import { Upload, FileVideo, X, PlayCircle } from 'lucide-react';
import './VideoUploader.css';

export default function VideoUploader({ onUploadStart, isProcessing }) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const validateAndSetFile = (file) => {
    setError('');
    if (!file) return;

    if (!file.type.startsWith('video/')) {
      setError('Please upload a valid video file (.mp4, .avi, .webm)');
      return;
    }

    if (file.size > 200 * 1024 * 1024) {
      setError('File is too large (max 200MB)');
      return;
    }

    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile || isProcessing) return;
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    
    onUploadStart(formData);
  };

  const clearSelection = () => {
    setSelectedFile(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
    setError('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="uploader-container glass-panel animate-fade-in">
      <h2 className="section-title">
        <Upload size={20} />
        Video Input
      </h2>
      
      {!selectedFile ? (
        <div 
          className={`drop-zone ${dragActive ? 'active' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="video/mp4,video/x-m4v,video/*"
            onChange={handleChange}
            style={{ display: 'none' }}
          />
          <div className="drop-content">
            <div className="upload-icon-wrapper">
              <Upload className="upload-icon" size={32} />
            </div>
            <h3>Drag & Drop Video Here</h3>
            <p>or click to browse</p>
            <span className="file-hints">Max 200MB • .mp4, .avi, .mkv</span>
          </div>
        </div>
      ) : (
        <div className="preview-container">
          <div className="video-preview-wrapper">
            <video 
              src={previewUrl} 
              className="video-preview"
              controls
              muted
            />
            <button className="clear-btn" onClick={clearSelection} disabled={isProcessing}>
              <X size={16} />
            </button>
          </div>
          
          <div className="file-info">
            <FileVideo size={20} className="file-icon" />
            <div className="file-details">
              <span className="file-name">{selectedFile.name}</span>
              <span className="file-size">{(selectedFile.size / (1024 * 1024)).toFixed(1)} MB</span>
            </div>
          </div>
          
          <button 
            className={`upload-btn ${isProcessing ? 'processing' : ''}`}
            onClick={handleUpload}
            disabled={isProcessing}
          >
            {isProcessing ? (
              <>Processing Pipeline Active...</>
            ) : (
              <>
                <PlayCircle size={18} />
                Start rPPG Analysis
              </>
            )}
          </button>
        </div>
      )}
      
      {error && <div className="error-message">{error}</div>}
    </div>
  );
}
