import React, { useState, useEffect } from 'react';
import { Download, Eye } from 'lucide-react';

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
  const [filterOptions, setFilterOptions] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getFilterOptions();
  }, []);

  useEffect(() => {
    if (csvData) {
      applyLocalFilter();
    }
  }, [csvData, filters]);

  const getFilterOptions = async () => {
    try {
      const response = await fetch('http://localhost:5001/api/get_filter_options');
      if (response.ok) {
        const options = await response.json();
        setFilterOptions(options);
      }
    } catch (error) {
      console.error('Failed to get filter options:', error);
    }
  };

  const applyBackendFilter = async (filterData) => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:5001/api/filter', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ filters: filterData })
      });

      if (response.ok) {
        const result = await response.json();
        setFilteredData(result.filtered_data || []);
      }
    } catch (error) {
      console.error('Filter error:', error);
    }
    setLoading(false);
  };

  useEffect(() => {
    if (csvData) {
      applyLocalFilter();
    }
  }, [csvData, filters]);

  const applyLocalFilter = () => {
    if (!csvData) return;
    
    let filtered = [...csvData];
    
    // Search filter
    if (filters.search) {
      filtered = filtered.filter(row => 
        Object.values(row).some(value => 
          String(value).toLowerCase().includes(filters.search.toLowerCase())
        )
      );
    }
    
    // Company filter
    if (filters.company) {
      filtered = filtered.filter(row => {
        const companyName = row.company || row.company_name || row.name || '';
        return String(companyName).toLowerCase().includes(filters.company.toLowerCase());
      });
    }
    
    // Filing type filter
    if (filters.filingType) {
      filtered = filtered.filter(row => {
        const filingType = row.filing_type || row.form_type || row.type || '';
        return String(filingType).toLowerCase().includes(filters.filingType.toLowerCase());
      });
    }
    
    // Exchange filter
    if (filters.exchange) {
      filtered = filtered.filter(row => {
        const exchange = row.exchange || row.market || '';
        return String(exchange).toLowerCase().includes(filters.exchange.toLowerCase());
      });
    }
    
    // Column filter
    if (filters.column !== 'all' && filters.value) {
      filtered = filtered.filter(row => 
        String(row[filters.column]).toLowerCase().includes(filters.value.toLowerCase())
      );
    }
    
    setFilteredData(filtered);
  };


  const calculateKPIs = () => {
    if (!filteredData || filteredData.length === 0) return null;
    
    const companies = new Set();
    const companyLastActivity = {};
    const currentDate = new Date();
    const thirtyDaysAgo = new Date(currentDate.getTime() - (30 * 24 * 60 * 60 * 1000));
    
    filteredData.forEach(row => {
      const companyName = row.company || row.company_name || row.name || row.entity_name || 
                         row.companyName || row.entityName || row.issuer || 'Unknown';
      companies.add(companyName);
      
      const dateField = row.date || row.filing_date || row.filingDate || row.reportDate || 
                       row.report_date || row.submissionDate || row.submission_date;
      if (dateField) {
        const filingDate = new Date(dateField);
        if (!companyLastActivity[companyName] || filingDate > companyLastActivity[companyName]) {
          companyLastActivity[companyName] = filingDate;
        }
      }
    });
    
    const totalCustomers = companies.size;
    let activeCustomers = 0;
    Object.values(companyLastActivity).forEach(lastActivity => {
      if (lastActivity >= thirtyDaysAgo) {
        activeCustomers++;
      }
    });
    
    if (activeCustomers === 0 && Object.keys(companyLastActivity).length === 0) {
      const companyFilings = {};
      filteredData.forEach(row => {
        const companyName = row.company || row.company_name || row.name || row.entity_name || 
                           row.companyName || row.entityName || row.issuer || 'Unknown';
        companyFilings[companyName] = (companyFilings[companyName] || 0) + 1;
      });
      const companiesWithMultipleFilings = Object.entries(companyFilings)
        .filter(([, filings]) => filings > 1).length;
      activeCustomers = Math.max(1, Math.floor(companiesWithMultipleFilings * 0.8));
    }
    
    const averageOrderValue = totalCustomers > 0 ? filteredData.length / totalCustomers : 0;
    const activityRate = totalCustomers > 0 ? (activeCustomers / totalCustomers) * 100 : 0;
    
    return {
      totalCustomers,
      activeCustomers,
      averageOrderValue: parseFloat(averageOrderValue.toFixed(2)),
      activityRate: parseFloat(activityRate.toFixed(1)),
      totalRows: filteredData.length
    };
  };


  const handleFilterChange = (filterType, value) => {
    setFilters(prev => ({
      ...prev,
      [filterType]: value
    }));
  };

  const handleSearch = () => {
    applyLocalFilter();
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
      
      // Add ALL filtered data rows (not just the displayed 100)
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
        alert(`Export successful!\n\nExported ${filteredData.length} rows of filtered data.\n\nNote: Display shows only first 100 rows, but export includes ALL ${filteredData.length} filtered results.`);
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

  const columns = Object.keys(filteredData[0] || {});

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
                  {filteredData.slice(0, 100).map((row, index) => (
                    <tr key={index}>
                      {columns.map(col => (
                        <td key={col}>{row[col]}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            {filteredData.length > 100 && (
              <p style={{ fontSize: '0.8rem', color: '#666', marginTop: '8px' }}>
                Display: Showing first 100 rows of {filteredData.length} total filtered results<br/>
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
