import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Download, Eye } from 'lucide-react';

const PAGE_SIZE = 100;
const ROW_CAP = 100000;
const BACKEND_URL = 'http://localhost:5001';

const DataViewer = ({ csvData, fileName, backendMode = false, totalRows }) => {
  const [filters, setFilters] = useState({
    search: '', column: 'all', value: '', company: '', filingType: '', exchange: ''
  });
  const [filteredData, setFilteredData] = useState([]);
  const [filteredTotal, setFilteredTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [debouncedFilters, setDebouncedFilters] = useState(filters);
  const [loading, setLoading] = useState(false);
  const filterJobIdRef = useRef(0);

  // Debounce filter changes
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedFilters(filters), 300);
    return () => clearTimeout(timer);
  }, [filters]);

  // Backend filter call
  const applyBackendFilter = useCallback(async (activeFilters, targetPage = 1) => {
    setLoading(true);
    const jobId = ++filterJobIdRef.current;
    try {
      const res = await fetch(`${BACKEND_URL}/api/filter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filters: activeFilters, page: targetPage, page_size: PAGE_SIZE }),
      });
      if (!res.ok) throw new Error('Filter request failed');
      const data = await res.json();
      if (filterJobIdRef.current !== jobId) return;
      setFilteredData(data.filtered_data || []);
      setFilteredTotal(data.total_filtered_rows || 0);
      setTotalPages(data.total_pages || 1);
      setPage(targetPage);
    } catch (e) {
      console.error('Backend filter error:', e);
    } finally {
      if (filterJobIdRef.current === jobId) setLoading(false);
    }
  }, []);

  // Local filter (for browser-loaded small files)
  const applyLocalFilter = useCallback((activeFilters) => {
    if (!csvData) return;

    const currentJobId = ++filterJobIdRef.current;
    const chunkSize = csvData.length > 100000 ? 500 : 1000;
    const filtered = [];
    let index = 0;

    const searchTerm = activeFilters.search.toLowerCase();
    const companyTerm = activeFilters.company.toLowerCase();
    const filingTypeTerm = activeFilters.filingType.toLowerCase();
    const exchangeTerm = activeFilters.exchange.toLowerCase();
    const columnValueTerm = activeFilters.value.toLowerCase();

    const rowMatches = (row) => {
      if (searchTerm) {
        let hasMatch = false;
        for (const key in row) {
          const v = row[key];
          if (v == null) continue;
          const s = typeof v === 'string' ? v : String(v);
          if (s.toLowerCase().includes(searchTerm)) { hasMatch = true; break; }
        }
        if (!hasMatch) return false;
      }
      if (companyTerm) {
        const c = row.company || row.company_name || row.name || '';
        if (!String(c).toLowerCase().includes(companyTerm)) return false;
      }
      if (filingTypeTerm) {
        const ft = row.filing_type || row.form_type || row.type || '';
        if (!String(ft).toLowerCase().includes(filingTypeTerm)) return false;
      }
      if (exchangeTerm) {
        const ex = row.exchange || row.market || '';
        if (!String(ex).toLowerCase().includes(exchangeTerm)) return false;
      }
      if (activeFilters.column !== 'all' && columnValueTerm) {
        if (!String(row[activeFilters.column] || '').toLowerCase().includes(columnValueTerm)) return false;
      }
      return true;
    };

    setLoading(true);

    const processChunk = () => {
      if (filterJobIdRef.current !== currentJobId) return;
      const end = Math.min(index + chunkSize, csvData.length);
      for (; index < end; index++) {
        if (rowMatches(csvData[index])) filtered.push(csvData[index]);
      }
      if (index < csvData.length) {
        setTimeout(processChunk, 0);
      } else {
        setFilteredData(filtered);
        setFilteredTotal(filtered.length);
        setTotalPages(Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)));
        setLoading(false);
      }
    };

    setTimeout(processChunk, 0);
  }, [csvData]);

  // Reset to page 1 when filters change
  useEffect(() => {
    if (!csvData) return;
    if (backendMode) {
      applyBackendFilter(debouncedFilters, 1);
    } else {
      setPage(1);
      applyLocalFilter(debouncedFilters);
    }
  }, [csvData, debouncedFilters, backendMode, applyBackendFilter, applyLocalFilter]);

  // Seed display with initial sample when data first loads
  useEffect(() => {
    if (csvData && csvData.length > 0) {
      setFilteredData(csvData.slice(0, PAGE_SIZE));
      setFilteredTotal(totalRows || csvData.length);
      setTotalPages(Math.max(1, Math.ceil((totalRows || csvData.length) / PAGE_SIZE)));
    }
  }, [csvData, totalRows]);

  const handleFilterChange = (filterType, value) => {
    setFilters(prev => ({ ...prev, [filterType]: value }));
  };

  const clearFilters = () => {
    setPage(1);
    setFilters({ search: '', column: 'all', value: '', company: '', filingType: '', exchange: '' });
  };

  const goToPage = (p) => {
    if (p < 1 || p > totalPages) return;
    if (backendMode) {
      applyBackendFilter(filters, p);
    } else {
      setPage(p);
    }
  };

  const exportData = () => {
    if (!filteredData || filteredData.length === 0) { alert('No data to export'); return; }
    const headers = Object.keys(filteredData[0]);
    const csvRows = [headers.join(',')];
    filteredData.forEach(row => {
      const values = headers.map(h => {
        const v = row[h] || '';
        if (typeof v === 'string' && (v.includes(',') || v.includes('"'))) {
          return `"${v.replace(/"/g, '""')}"`;
        }
        return v;
      });
      csvRows.push(values.join(','));
    });
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `${fileName.replace('.csv', '')}_filtered_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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
  // For local mode, slice the filteredData array for the current page
  const displayRows = backendMode
    ? filteredData
    : filteredData.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className="card">
      {backendMode && (
        <div style={{ background: '#dbeafe', border: '1px solid #3b82f6', borderRadius: '6px', padding: '10px 14px', marginBottom: '12px', fontSize: '0.85rem', color: '#1e3a5f' }}>
          Backend mode: Python/pandas is handling this {(totalRows || 0).toLocaleString()}-row file. Filters run server-side — no browser memory limit.
        </div>
      )}
      {!backendMode && csvData.length >= ROW_CAP && (
        <div style={{ background: '#fef3c7', border: '1px solid #d97706', borderRadius: '6px', padding: '10px 14px', marginBottom: '12px', fontSize: '0.85rem', color: '#92400e' }}>
          Large file: displaying first {ROW_CAP.toLocaleString()} rows. Filters and export operate on this loaded subset.
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h2>Data Viewer — {fileName}</h2>
          <div style={{ fontSize: '0.9rem', color: '#666', marginTop: '4px' }}>
            Total rows: {(totalRows || csvData.length).toLocaleString()} |
            Filtered results: {filteredTotal.toLocaleString()} |
            Columns: {columns.length}
          </div>
        </div>
        <button className="btn btn-success" onClick={exportData}>
          <Download size={16} />
          Export Filtered Data
        </button>
      </div>

      {/* Filters */}
      <div className="filter-section">
        <h3>Search &amp; Filters {backendMode && <span style={{ fontSize: '0.75rem', fontWeight: 'normal', color: '#555' }}>(server-side)</span>}</h3>
        <div className="filter-row">
          <div className="filter-group">
            <label>Search</label>
            <input type="text" placeholder="Search all data..." value={filters.search}
              onChange={(e) => handleFilterChange('search', e.target.value)} />
          </div>
          <div className="filter-group">
            <label>Company</label>
            <input type="text" placeholder="Company name..." value={filters.company}
              onChange={(e) => handleFilterChange('company', e.target.value)} />
          </div>
          <div className="filter-group">
            <label>Filing Type</label>
            <input type="text" placeholder="8-K, 10-K, etc..." value={filters.filingType}
              onChange={(e) => handleFilterChange('filingType', e.target.value)} />
          </div>
        </div>
        <div className="filter-row">
          <div className="filter-group">
            <label>Exchange</label>
            <input type="text" placeholder="NASDAQ, NYSE, etc..." value={filters.exchange}
              onChange={(e) => handleFilterChange('exchange', e.target.value)} />
          </div>
          <div className="filter-group">
            <label>Column</label>
            <select value={filters.column} onChange={(e) => handleFilterChange('column', e.target.value)}>
              <option value="all">All Columns</option>
              {columns.map(col => <option key={col} value={col}>{col}</option>)}
            </select>
          </div>
          {filters.column !== 'all' && (
            <div className="filter-group">
              <label>Value</label>
              <input type="text" placeholder="Filter value" value={filters.value}
                onChange={(e) => handleFilterChange('value', e.target.value)} />
            </div>
          )}
        </div>
        <div className="filter-row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <button className="btn btn-danger" onClick={clearFilters}>Clear Filters</button>
          <div style={{ fontSize: '0.8rem', color: '#666' }}>
            {loading ? 'Filtering…' : `${filteredTotal.toLocaleString()} matching rows`}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="data-sections">
        <div className="section-tabs">
          <div className="section-tab active"><Eye size={16} /> Overview</div>
        </div>
        <div className="section-content">
          <div className="stats-summary">
            <div className="stat-item">
              <div className="stat-value">{(totalRows || csvData.length).toLocaleString()}</div>
              <div className="stat-label">Total Rows</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{filteredTotal.toLocaleString()}</div>
              <div className="stat-label">Filtered Results</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{columns.length}</div>
              <div className="stat-label">Columns</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">
                {filteredTotal > 0 ? ((filteredTotal / (totalRows || csvData.length)) * 100).toFixed(1) : 0}%
              </div>
              <div className="stat-label">Match Rate</div>
            </div>
          </div>

          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>{columns.map(col => <th key={col}>{col}</th>)}</tr>
              </thead>
              <tbody>
                {displayRows.map((row, i) => (
                  <tr key={i}>{columns.map(col => <td key={col}>{row[col]}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px', justifyContent: 'center' }}>
              <button className="btn" onClick={() => goToPage(1)} disabled={page === 1 || loading}>«</button>
              <button className="btn" onClick={() => goToPage(page - 1)} disabled={page === 1 || loading}>‹</button>
              <span style={{ fontSize: '0.9rem', color: '#444' }}>
                Page {page} of {totalPages.toLocaleString()} &nbsp;·&nbsp; {filteredTotal.toLocaleString()} rows
              </span>
              <button className="btn" onClick={() => goToPage(page + 1)} disabled={page === totalPages || loading}>›</button>
              <button className="btn" onClick={() => goToPage(totalPages)} disabled={page === totalPages || loading}>»</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DataViewer;
