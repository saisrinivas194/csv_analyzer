import React, { useState, useEffect, useRef } from 'react';
import { Download, Eye } from 'lucide-react';

const MAX_DISPLAY_ROWS = 20;

const DataViewer = ({ csvData, fileName }) => {
  const [filters, setFilters] = useState({
    search: '',
    column: 'all',
    value: '',
    dateRange: 'all',
    company: '',
    filingType: '',
    exchange: ''
  });
  const [filteredData, setFilteredData] = useState([]);
  const [debouncedFilters, setDebouncedFilters] = useState(filters);
  const [loading, setLoading] = useState(false);
  const filterJobIdRef = useRef(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedFilters(filters);
    }, 200);
    return () => clearTimeout(timer);
  }, [filters]);

  useEffect(() => {
    if (csvData) {
      applyLocalFilter(debouncedFilters);
    }
  }, [csvData, debouncedFilters]);

  useEffect(() => {
    return () => {
      filterJobIdRef.current += 1;
    };
  }, []);

  const applyLocalFilter = (activeFilters) => {
    if (!csvData) return;

    const currentJobId = ++filterJobIdRef.current;
    const sourceData = csvData;
    const filtered = [];
    const chunkSize = 1000;
    let index = 0;

    const searchTerm = activeFilters.search.toLowerCase();
    const companyTerm = activeFilters.company.toLowerCase();
    const filingTypeTerm = activeFilters.filingType.toLowerCase();
    const exchangeTerm = activeFilters.exchange.toLowerCase();
    const columnValueTerm = activeFilters.value.toLowerCase();

    const rowMatches = (row) => {
      if (searchTerm) {
        const hasMatch = Object.values(row).some((value) =>
          String(value).toLowerCase().includes(searchTerm)
        );
        if (!hasMatch) return false;
      }

      if (companyTerm) {
        const companyName = row.company || row.company_name || row.name || '';
        if (!String(companyName).toLowerCase().includes(companyTerm)) return false;
      }

      if (filingTypeTerm) {
        const filingType = row.filing_type || row.form_type || row.type || '';
        if (!String(filingType).toLowerCase().includes(filingTypeTerm)) return false;
      }

      if (exchangeTerm) {
        const exchange = row.exchange || row.market || '';
        if (!String(exchange).toLowerCase().includes(exchangeTerm)) return false;
      }

      if (activeFilters.column !== 'all' && columnValueTerm) {
        if (!String(row[activeFilters.column] || '').toLowerCase().includes(columnValueTerm)) return false;
      }

      return true;
    };

    setLoading(true);

    const processChunk = () => {
      if (filterJobIdRef.current !== currentJobId) return;

      const end = Math.min(index + chunkSize, sourceData.length);
      for (; index < end; index++) {
        const row = sourceData[index];
        if (rowMatches(row)) {
          filtered.push(row);
        }
      }

      if (index < sourceData.length) {
        setTimeout(processChunk, 0);
      } else {
        setFilteredData(filtered);
        setLoading(false);
      }
    };

    setTimeout(processChunk, 0);
  };


  const handleFilterChange = (filterType, value) => {
    setFilters(prev => ({
      ...prev,
      [filterType]: value
    }));
  };

  const handleSearch = () => {
    applyLocalFilter(filters);
  };

  const clearFilters = () => {
    setFilters({
      search: '',
      column: 'all',
      value: '',
      dateRange: 'all',
      company: '',
      filingType: '',
      exchange: ''
    });
  };


  const exportData = () => {
    try {
      if (!filteredData || filteredData.length === 0) {
        alert('No data to export');
        return;
      }

      const headers = Object.keys(filteredData[0]);
      const csvRows = [];
      
      // Add header row
      csvRows.push(headers.join(','));
      
      // Add ALL filtered data rows (not just the displayed preview rows)
      filteredData.forEach(row => {
        const values = headers.map(header => {
          const value = row[header] || '';
          // Escape commas and quotes in values
          if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
            return `"${value.replace(/"/g, '""')}"`;
          }
          return value;
        });
        csvRows.push(values.join(','));
      });
      
      const csvContent = csvRows.join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      
      if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `${fileName.replace('.csv', '')}_filtered_${new Date().toISOString().split('T')[0]}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Show confirmation with actual count
        alert(`Export successful!\n\nExported ${filteredData.length} rows of filtered data.\n\nNote: Display shows only first ${MAX_DISPLAY_ROWS} rows, but export includes ALL ${filteredData.length} filtered results.`);
      }
    } catch (error) {
      console.error('Export error:', error);
      alert('Export failed. Please try again.');
    }
  };

  if (!csvData || csvData.length === 0) {
    return (
      <div className="card">
        <h2>No Data Available</h2>
        <p>Please upload and analyze a CSV file first.</p>
      </div>
    );
  }

  const columns = Object.keys(csvData[0] || {});

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h2>Data Viewer - {fileName}</h2>
          <div style={{ fontSize: '0.9rem', color: '#666', marginTop: '4px' }}>
            Total rows in file: {csvData.length.toLocaleString()} | 
            Filtered results: {filteredData.length.toLocaleString()} | 
            Columns: {columns.length}
            {csvData.length > 100000 && (
              <span style={{ color: '#16a34a', fontWeight: 'bold', marginLeft: '8px' }}>
                Complete dataset loaded
              </span>
            )}
          </div>
        </div>
        <button className="btn btn-success" onClick={exportData}>
          <Download size={16} />
          Export Filtered Data
        </button>
      </div>

      {/* Filter Section */}
      <div className="filter-section">
        <h3>Search & Filters</h3>
        
        <div className="filter-row">
          <div className="filter-group">
            <label>Search</label>
            <input
              type="text"
              placeholder="Search all data..."
              value={filters.search}
              onChange={(e) => handleFilterChange('search', e.target.value)}
            />
          </div>
          <div className="filter-group">
            <label>Company</label>
            <input
              type="text"
              placeholder="Company name..."
              value={filters.company}
              onChange={(e) => handleFilterChange('company', e.target.value)}
            />
          </div>
          <div className="filter-group">
            <label>Filing Type</label>
            <input
              type="text"
              placeholder="8-K, 10-K, etc..."
              value={filters.filingType}
              onChange={(e) => handleFilterChange('filingType', e.target.value)}
            />
          </div>
        </div>
        
        <div className="filter-row">
          <div className="filter-group">
            <label>Exchange</label>
            <input
              type="text"
              placeholder="NASDAQ, NYSE, etc..."
              value={filters.exchange}
              onChange={(e) => handleFilterChange('exchange', e.target.value)}
            />
          </div>
          <div className="filter-group">
            <label>Column</label>
            <select
              value={filters.column}
              onChange={(e) => handleFilterChange('column', e.target.value)}
            >
              <option value="all">All Columns</option>
              {columns.map(col => (
                <option key={col} value={col}>{col}</option>
              ))}
            </select>
          </div>
          {filters.column !== 'all' && (
            <div className="filter-group">
              <label>Value</label>
              <input
                type="text"
                placeholder="Filter value"
                value={filters.value}
                onChange={(e) => handleFilterChange('value', e.target.value)}
              />
            </div>
          )}
        </div>
        
        <div className="filter-row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button className="btn btn-success" onClick={handleSearch}>
              Search
            </button>
            <button className="btn btn-danger" onClick={clearFilters}>
              Clear Filters
            </button>
          </div>
          <div style={{ fontSize: '0.8rem', color: '#666' }}>
            {loading ? 'Loading...' : (
              <>
                Showing {filteredData.length.toLocaleString()} of {csvData.length.toLocaleString()} total rows
                {csvData.length > 100000 && (
                  <div style={{ color: '#16a34a', fontWeight: 'bold', marginTop: '2px' }}>
                    Search & filters work on ALL {csvData.length.toLocaleString()} rows
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Section Tabs */}
      <div className="data-sections">
        <div className="section-tabs">
          <div className="section-tab active">
            <Eye size={16} />
            Overview
          </div>
        </div>

        <div className="section-content">
          <div>
            <h3>Overview</h3>
            <div className="stats-summary">
              <div className="stat-item">
                <div className="stat-value">{csvData.length.toLocaleString()}</div>
                <div className="stat-label">Total Rows</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">{filteredData.length.toLocaleString()}</div>
                <div className="stat-label">Filtered Results</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">{columns.length}</div>
                <div className="stat-label">Columns</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">{filteredData.length > 0 ? ((filteredData.length / csvData.length) * 100).toFixed(1) : 0}%</div>
                <div className="stat-label">Match Rate</div>
              </div>
            </div>
            
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    {columns.map(col => (
                      <th key={col}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredData.slice(0, MAX_DISPLAY_ROWS).map((row, index) => (
                    <tr key={index}>
                      {columns.map(col => (
                        <td key={col}>{row[col]}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            {filteredData.length > MAX_DISPLAY_ROWS && (
              <p style={{ fontSize: '0.8rem', color: '#666', marginTop: '8px' }}>
                Display: Showing first {MAX_DISPLAY_ROWS} rows of {filteredData.length} total filtered results<br/>
                Export: Will include ALL {filteredData.length} filtered rows
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataViewer;
