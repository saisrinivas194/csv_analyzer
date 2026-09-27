import React, { useState, useMemo, useEffect } from 'react';
import { Download, Search } from 'lucide-react';

const BACKEND_URL = 'http://localhost:5001';
const PAGE_SIZE = 50;
const DEFAULT_TERMS = 'ARPU, average revenue per user';
const SIC_PRESETS = [
  { label: 'Software & internet', value: '7370-7379' },
  { label: 'Communications (telecom, cable, broadcast)', value: '48' },
  { label: 'Cable & streaming', value: '4841, 7841' },
  { label: 'Media & publishing', value: '27' },
];

const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Build a highlighter regex that mirrors the backend matching (case-insensitive, flexible whitespace, simple plurals)
const buildHighlightRegex = (terms) => {
  const parts = terms
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
    .map(t => t.split(/\s+/).map(escapeRegex).join('\\s+') + '(?:s|es)?');
  return parts.length ? new RegExp(`(${parts.join('|')})`, 'gi') : null;
};

const Highlighted = ({ text, regex }) => {
  if (!regex || !text) return <>{text}</>;
  const pieces = String(text).split(regex);
  return (
    <>
      {pieces.map((p, i) => (i % 2 === 1
        ? <mark key={i} style={{ background: '#fde68a', padding: '0 2px', borderRadius: '2px' }}>{p}</mark>
        : <React.Fragment key={i}>{p}</React.Fragment>))}
    </>
  );
};

const pickMeta = (row, metaColumns) => {
  const find = (keys) => metaColumns.find(c => keys.some(k => c.toLowerCase().includes(k)));
  const company = find(['company', 'registrant', 'entity', 'name']);
  const form = find(['form', 'filing_type', 'type']);
  const date = find(['date', 'period', 'year']);
  const used = new Set([company, form, date].filter(Boolean));
  const primary = [company, form, date].filter(Boolean).map(c => row[c]).filter(v => v !== null && v !== undefined && v !== '');
  const extra = metaColumns.filter(c => !used.has(c)).map(c => `${c}: ${row[c] ?? ''}`);
  return { primary, extra };
};

const SnippetSearch = ({ backendMode }) => {
  const [terms, setTerms] = useState(DEFAULT_TERMS);
  const [windowSize, setWindowSize] = useState(50);
  const [company, setCompany] = useState('');
  const [filingType, setFilingType] = useState('');
  const [sic, setSic] = useState('');
  const [sicCodes, setSicCodes] = useState([]);

  useEffect(() => {
    if (!backendMode) return;
    fetch(`${BACKEND_URL}/api/sic_codes`)
      .then(r => (r.ok ? r.json() : { codes: [] }))
      .then(d => setSicCodes(d.codes || []))
      .catch(() => setSicCodes([]));
  }, [backendMode]);

  const sicHint = useMemo(() => {
    const tokens = sic.split(/[,;\s]+/).filter(Boolean);
    if (!tokens.length || !sicCodes.length) return '';
    const test = (code) => tokens.some(t => {
      const m = t.match(/^(\d{1,4})-(\d{1,4})$/);
      if (m) { const n = +code; return n >= +m[1].padEnd(4, '0') && n <= +m[2].padEnd(4, '9'); }
      return /^\d+$/.test(t) && code.startsWith(t);
    });
    const hits = sicCodes.filter(c => test(c.sic));
    if (!hits.length) return 'No SEC SIC codes match';
    const shown = hits.slice(0, 4).map(c => `${c.sic} ${c.description}`).join('; ');
    return `${hits.length} code${hits.length > 1 ? 's' : ''}: ${shown}${hits.length > 4 ? '; …' : ''}`;
  }, [sic, sicCodes]);
  const [result, setResult] = useState(null);
  const [activeQuery, setActiveQuery] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');

  const highlightRegex = useMemo(
    () => buildHighlightRegex(result?.terms || []),
    [result]
  );

  const buildBody = (query, page) => ({
    terms: query.terms,
    window: query.window,
    filters: { company: query.company, filingType: query.filingType, sic: query.sic },
    page,
    page_size: PAGE_SIZE,
  });

  const parseResponse = async (res) => {
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch {
      throw new Error(`Backend returned an invalid response (HTTP ${res.status})`);
    }
    if (!res.ok) throw new Error(data.error || `Backend error (HTTP ${res.status})`);
    return data;
  };

  const runSearch = async (query, page = 1) => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${BACKEND_URL}/api/snippets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildBody(query, page)),
      });
      setResult(await parseResponse(res));
      setActiveQuery(query);
    } catch (e) {
      setError(e.message.includes('fetch') ? 'Cannot reach backend on port 5001.' : e.message);
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    runSearch({ terms, window: Number(windowSize) || 50, company, filingType, sic }, 1);
  };

  const exportCsv = async () => {
    if (!activeQuery) return;
    setExporting(true);
    setError('');
    try {
      const res = await fetch(`${BACKEND_URL}/api/snippets/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildBody(activeQuery, 1)),
      });
      if (!res.ok) await parseResponse(res);
      const blob = await res.blob();
      const disposition = res.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^";]+)"?/);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = match ? match[1] : 'snippets.csv';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    } finally {
      setExporting(false);
    }
  };

  if (!backendMode) {
    return (
      <div className="card">
        <h2>Keyword Snippets</h2>
        <p style={{ color: '#666' }}>
          Snippet search runs on the Python backend. Load your file with <strong>Load from Path</strong> to use it.
        </p>
      </div>
    );
  }

  const page = result?.page || 1;
  const totalPages = result?.total_pages || 1;
  const metaColumns = result?.meta_columns || [];

  return (
    <div className="card">
      <h2>Keyword Snippets</h2>
      <p style={{ color: '#666', fontSize: '0.9rem', marginTop: '4px' }}>
        Returns only the words around each hit instead of whole documents. Separate multiple terms with commas.
        Hits close together are merged into one snippet.
      </p>

      <form className="filter-section" onSubmit={onSubmit}>
        <div className="filter-row">
          <div className="filter-group" style={{ flex: 3 }}>
            <label>Search terms</label>
            <input type="text" value={terms} onChange={(e) => setTerms(e.target.value)}
              placeholder="ARPU, average revenue per user, ARPPU, revenue per subscriber" />
          </div>
          <div className="filter-group" style={{ flex: 1 }}>
            <label>Words each side</label>
            <input type="number" min="5" max="500" value={windowSize}
              onChange={(e) => setWindowSize(e.target.value)} />
          </div>
        </div>
        <div className="filter-row">
          <div className="filter-group">
            <label>Company (optional)</label>
            <input type="text" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Company name..." />
          </div>
          <div className="filter-group">
            <label>Form type (optional)</label>
            <input type="text" value={filingType} onChange={(e) => setFilingType(e.target.value)} placeholder="10-K, 8-K, 6-K..." />
          </div>
          <div className="filter-group" style={{ flex: 1.4 }}>
            <label>Industry, SIC code (optional)</label>
            <input type="text" list="sic-code-options" value={sic} onChange={(e) => setSic(e.target.value)}
              placeholder="e.g. 7370-7379, 48, 4841" />
            <datalist id="sic-code-options">
              {sicCodes.map(c => <option key={c.sic} value={c.sic}>{`${c.sic} ${c.description}`}</option>)}
            </datalist>
          </div>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center', fontSize: '0.8rem', color: '#555' }}>
          <span>Industry presets:</span>
          {SIC_PRESETS.map(p => (
            <button key={p.label} type="button" onClick={() => setSic(p.value)}
              style={{ border: '1px solid #cbd5e1', background: sic === p.value ? '#dbeafe' : '#fff', borderRadius: '999px', padding: '2px 10px', cursor: 'pointer', fontSize: '0.8rem' }}>
              {p.label} ({p.value})
            </button>
          ))}
          {sic && <button type="button" onClick={() => setSic('')}
            style={{ border: 'none', background: 'none', color: '#2563eb', cursor: 'pointer', fontSize: '0.8rem' }}>clear</button>}
        </div>
        {sicHint && <div style={{ fontSize: '0.78rem', color: '#6b7280' }}>{sicHint}. Codes match as prefixes; ranges like 7370-7379 work.</div>}
        <div className="filter-row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button type="submit" className="btn btn-primary" disabled={loading || !terms.trim()}>
              <Search size={16} /> {loading ? 'Scanning file…' : 'Find Snippets'}
            </button>
            <button type="button" className="btn btn-success" onClick={exportCsv}
              disabled={!result || !result.total_snippets || exporting}>
              <Download size={16} /> {exporting ? 'Exporting…' : 'Export Snippets CSV'}
            </button>
          </div>
          {result && (
            <div style={{ fontSize: '0.85rem', color: '#444' }}>
              {result.total_snippets.toLocaleString()} snippet{result.total_snippets === 1 ? '' : 's'} in {result.total_documents.toLocaleString()} document{result.total_documents === 1 ? '' : 's'}
            </div>
          )}
        </div>
        {loading && (
          <div style={{ fontSize: '0.8rem', color: '#666' }}>
            The first search scans the whole file and can take a while on multi-GB files; paging after that is instant.
          </div>
        )}
      </form>

      {error && (
        <div style={{ background: '#fee2e2', border: '1px solid #ef4444', borderRadius: '6px', padding: '10px 14px', margin: '12px 0', color: '#991b1b' }}>
          {error}
        </div>
      )}

      {result && !result.sic_source && (
        <div style={{ background: '#fef3c7', border: '1px solid #d97706', borderRadius: '6px', padding: '8px 12px', margin: '12px 0', fontSize: '0.85rem', color: '#92400e' }}>
          This file has no CIK or company-name column, so SEC industry codes can't be matched{activeQuery?.sic ? ' and the SIC filter excluded every row' : ''}.
        </div>
      )}
      {result && result.sic_source === 'name' && (
        <div style={{ fontSize: '0.8rem', color: '#6b7280', margin: '8px 0' }}>
          SIC codes matched by company name (column “{result.sic_source_column}”) because the file has no CIK column. A CIK column gives exact matches.
        </div>
      )}
      {result && result.total_snippets === 0 && (
        <p style={{ color: '#666' }}>No matches for {result.terms.join(', ')}.</p>
      )}

      {result && result.snippets.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '12px' }}>
          {result.snippets.map((s, i) => {
            const { primary, extra } = pickMeta(s, metaColumns);
            return (
              <div key={`${s._row}-${i}`} style={{ border: '1px solid #e5e7eb', borderRadius: '8px', padding: '12px 14px', background: '#fff' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '6px' }}>
                  <strong style={{ fontSize: '0.9rem' }}>{primary.join(' · ') || `Row ${s._row}`}</strong>
                  <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                    {s._sic && <span title={s._sic_description} style={{ background: '#eef2ff', color: '#3730a3', borderRadius: '4px', padding: '1px 6px', marginRight: '6px' }}>SIC {s._sic} · {s._sic_description}</span>}
                    row {s._row} · column {s._column} · {s._matched}{s._hits > 1 ? ` (${s._hits} hits)` : ''}
                  </span>
                </div>
                {extra.length > 0 && (
                  <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '6px' }}>{extra.join(' · ')}</div>
                )}
                <div style={{ fontSize: '0.9rem', lineHeight: 1.55, color: '#1f2937' }}>
                  <Highlighted text={s._snippet} regex={highlightRegex} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {result && totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px', justifyContent: 'center' }}>
          <button className="btn" onClick={() => runSearch(activeQuery, 1)} disabled={page === 1 || loading}>«</button>
          <button className="btn" onClick={() => runSearch(activeQuery, page - 1)} disabled={page === 1 || loading}>‹</button>
          <span style={{ fontSize: '0.9rem', color: '#444' }}>Page {page} of {totalPages.toLocaleString()}</span>
          <button className="btn" onClick={() => runSearch(activeQuery, page + 1)} disabled={page === totalPages || loading}>›</button>
          <button className="btn" onClick={() => runSearch(activeQuery, totalPages)} disabled={page === totalPages || loading}>»</button>
        </div>
      )}
    </div>
  );
};

export default SnippetSearch;
