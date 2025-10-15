import React, { useState } from 'react';
import './App.css';
import FileUpload from './components/FileUpload';
import KPIAnalysis from './components/KPIAnalysis';
import DataViewer from './components/DataViewer';

function App() {
  const [analysisData, setAnalysisData] = useState(null);
  const [csvData, setCsvData] = useState(null);
  const [fileName, setFileName] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const handleAnalysisComplete = (data) => {
    setAnalysisData(data);
    setIsAnalyzing(false);
  };

  const handleAnalysisStart = () => {
    setIsAnalyzing(true);
  };

  const handleFileRead = (data, name) => {
    setCsvData(data);
    setFileName(name);
  };

  return (
    <div className="App">
      <main className="main-content">
        <div className="container">
          <FileUpload 
            onAnalysisStart={handleAnalysisStart}
            onAnalysisComplete={handleAnalysisComplete}
            onFileRead={handleFileRead}
            isAnalyzing={isAnalyzing}
          />
          
          {csvData && (
            <DataViewer csvData={csvData} fileName={fileName} />
          )}
          
          {analysisData && (
            <KPIAnalysis data={analysisData} />
          )}
        </div>
      </main>
    </div>
  );
}

export default App;