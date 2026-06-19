import React, { useState } from 'react';
import { Upload, FileText, AlertCircle, CheckCircle, FolderOpen } from 'lucide-react';
import FastFileLoader from '../utils/FastFileLoader.js';

const BACKEND_URL = 'http://localhost:5001';

const FileUpload = ({ onAnalysisStart, onAnalysisComplete, onFileRead, isAnalyzing }) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [filePath, setFilePath] = useState('');
  const [uploadStatus, setUploadStatus] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [mode, setMode] = useState('path'); // 'path' | 'upload'

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (!file) { setSelectedFile(null); setUploadStatus(''); return; }
    const validExtensions = ['.csv', '.txt'];
    const ext = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    if (validExtensions.includes(ext)) {
      setSelectedFile(file);
      setUploadStatus(`File selected: ${file.name} (${(file.size / (1024 * 1024)).toFixed(2)} MB)`);
    } else {
      setUploadStatus('Please select a valid CSV or text file (.csv, .txt)');
      setSelectedFile(null);
    }
  };

  // Load via backend from a local file path (handles multi-GB files)
  const handleLoadFromPath = async () => {
    if (!filePath.trim()) { setUploadStatus('Please enter a file path'); return; }
    onAnalysisStart();
    setUploadStatus('Connecting to backend...');

    try {
      const res = await fetch(`${BACKEND_URL}/api/load_path`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filePath.trim() }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Backend error');
      }

      const result = await res.json();
      setUploadStatus(`Loaded ${result.total_rows.toLocaleString()} rows — displaying first 20, backend handles filtering`);

      const analysis = {
        totalCustomers: result.total_rows,
        activeCustomers: Math.floor(result.total_rows * 0.7),
        averageOrderValue: '1.00',
        activityRate: '70.0',
        topCompanies: [],
        exchanges: [],
        revenueMentions: Math.floor(result.total_rows * 0.3),
        customerMentions: Math.floor(result.total_rows * 0.2),
      };

      onAnalysisComplete(analysis);
      // Pass sample data + signal to use backend for filtering
      onFileRead(result.sample_data, result.file_info.filename, {
        backendMode: true,
        totalRows: result.total_rows,
        columns: result.columns,
      });
    } catch (err) {
      if (err.message.includes('fetch')) {
        setUploadStatus('Cannot reach backend on port 5001. Start it with: cd backend && ./start.sh');
      } else {
        setUploadStatus(`Error: ${err.message}`);
      }
      onAnalysisComplete(null);
    }
  };

  // Load small file entirely in-browser (original behaviour)
  const handleAnalyze = async () => {
    if (!selectedFile) { setUploadStatus('Please select a file first'); return; }
    onAnalysisStart();

    const loader = new FastFileLoader({
      chunkSize: 2 * 1024 * 1024,
      maxSampleRows: 100000,
      onProgress: (percent, message) => { setUploadStatus(message); setUploadProgress(percent); },
      onError: (error) => { setUploadStatus(`Error: ${error.message}`); onAnalysisComplete(null); },
    });

    try {
      const result = await loader.loadFile(selectedFile);
      if (result.success) {
        const cap = 100000;
        const statusMessage = result.summary.totalRows >= cap
          ? `Loaded first ${result.sampleData.length.toLocaleString()} of ${result.summary.totalRows.toLocaleString()} rows (capped at 100k)`
          : `Loaded all ${result.summary.totalRows.toLocaleString()} rows`;
        setUploadStatus(statusMessage);

        const analysis = {
          totalCustomers: result.summary.totalRows,
          activeCustomers: Math.floor(result.summary.totalRows * 0.7),
          averageOrderValue: '1.00',
          activityRate: '70.0',
          topCompanies: [], exchanges: [],
          revenueMentions: Math.floor(result.summary.totalRows * 0.3),
          customerMentions: Math.floor(result.summary.totalRows * 0.2),
        };
        onAnalysisComplete(analysis);
        onFileRead(result.sampleData, selectedFile.name, { backendMode: false });
      } else {
        throw new Error(result.error || 'File processing failed');
      }
    } catch (error) {
      setUploadStatus(`Error: ${error.message}`);
      onAnalysisComplete(null);
    }
  };

  return (
    <div className="card">
      <h2>Upload CSV File for Analysis</h2>

      {/* Mode toggle */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px' }}>
        <button
          className={`btn ${mode === 'path' ? '' : 'btn-warning'}`}
          style={{ opacity: mode === 'path' ? 1 : 0.5 }}
          onClick={() => setMode('path')}
          disabled={isAnalyzing}
        >
          <FolderOpen size={16} style={{ marginRight: 6 }} />
          Load from Path (large files)
        </button>
        <button
          className={`btn ${mode === 'upload' ? '' : 'btn-warning'}`}
          style={{ opacity: mode === 'upload' ? 1 : 0.5 }}
          onClick={() => setMode('upload')}
          disabled={isAnalyzing}
        >
          <Upload size={16} style={{ marginRight: 6 }} />
          Upload in Browser (small files)
        </button>
      </div>

      {mode === 'path' && (
        <div>
          <p style={{ color: '#555', marginBottom: '12px', fontSize: '0.9rem' }}>
            Enter the full path to your CSV. The backend (Python) reads it directly — no browser memory limit.
            <br />
            <strong>Requires the backend to be running:</strong> <code>cd backend && ./start.sh</code>
          </p>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <input
              type="text"
              placeholder="/Users/yourname/Downloads/sec_10k_latest.csv"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              disabled={isAnalyzing}
              style={{ flex: 1, padding: '12px 16px', border: '2px solid #e2e8f0', borderRadius: '8px', fontSize: '0.9rem' }}
            />
            <button className="btn btn-success" onClick={handleLoadFromPath} disabled={!filePath.trim() || isAnalyzing}>
              {isAnalyzing ? 'Loading...' : 'Load File'}
            </button>
          </div>
        </div>
      )}

      {mode === 'upload' && (
        <div>
          <div className="file-input">
            <input type="file" id="csv-file" accept=".csv,.txt" onChange={handleFileSelect} disabled={isAnalyzing} />
            <label htmlFor="csv-file" className="file-label">
              <Upload size={20} />
              {selectedFile ? selectedFile.name : 'Choose CSV or Text File'}
            </label>
          </div>
          {selectedFile && (
            <div className="file-info">
              <FileText size={16} />
              <span>File: {selectedFile.name}</span>
              <span>Size: {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</span>
            </div>
          )}
          <button className="btn btn-success" onClick={handleAnalyze} disabled={!selectedFile || isAnalyzing}>
            {isAnalyzing ? 'Processing...' : 'Analyze CSV File'}
          </button>
        </div>
      )}

      {uploadStatus && (
        <div className={`status ${uploadStatus.includes('Error') || uploadStatus.includes('Cannot') ? 'status-warning' : 'status-info'}`}
          style={{ marginTop: '16px' }}>
          {uploadStatus.includes('Error') || uploadStatus.includes('Cannot')
            ? <AlertCircle size={16} />
            : <CheckCircle size={16} />}
          <div>{uploadStatus}</div>
          {uploadProgress > 0 && uploadProgress < 100 && (
            <div style={{ marginTop: '8px' }}>
              <div style={{ width: '100%', backgroundColor: '#e0e0e0', borderRadius: '4px', height: '8px' }}>
                <div style={{ width: `${uploadProgress}%`, backgroundColor: '#2563eb', borderRadius: '4px', height: '8px', transition: 'width 0.3s ease' }} />
              </div>
              <div style={{ textAlign: 'center', fontSize: '0.8rem', marginTop: '4px' }}>{uploadProgress}%</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default FileUpload;
