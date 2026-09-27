from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import numpy as np
import os
import json
import tempfile
import io
from datetime import datetime
import re
from collections import Counter
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from flask.json.provider import DefaultJSONProvider


def _json_safe(obj):
    """Convert NaN/Inf to None and numpy/pandas values to plain types (NaN is invalid JSON)."""
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [_json_safe(v) for v in obj.tolist()]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    if obj is pd.NaT:
        return None
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    return obj


class SafeJSONProvider(DefaultJSONProvider):
    def dumps(self, obj, **kwargs):
        kwargs.setdefault('allow_nan', False)
        return super().dumps(_json_safe(obj), **kwargs)


app = Flask(__name__)
app.json = SafeJSONProvider(app)
CORS(app, expose_headers=['Content-Disposition'])

MAX_CELL_PREVIEW_CHARS = 400  # long text cells (e.g. whole filings) are cut to this in table/preview responses


def _preview_value(v):
    if isinstance(v, str) and len(v) > MAX_CELL_PREVIEW_CHARS:
        return f"{v[:MAX_CELL_PREVIEW_CHARS]}… [{len(v):,} chars, use Keyword Snippets or Export for full text]"
    return v


def _preview_records(df):
    """DataFrame -> records with long text truncated, so the browser never receives whole filings."""
    return [{k: _preview_value(v) for k, v in row.items()} for row in df.replace({np.nan: None}).to_dict('records')]


def _resolve_user_path(raw):
    """Accept paths the way people paste them: quoted, shell-escaped (My\ Files), ~/..., or file:// URLs."""
    from urllib.parse import unquote, urlparse
    p = str(raw or '').strip()
    if len(p) >= 2 and p[0] == p[-1] and p[0] in '"\'':
        p = p[1:-1].strip()
    if p.startswith('file://'):
        p = unquote(urlparse(p).path)
    if not os.path.exists(p):
        p = re.sub(r'\\(.)', r'\1', p)  # undo shell escaping from drag-and-drop into Terminal
    return os.path.expanduser(p)


def _path_not_found_message(path):
    msg = f'File not found: {path}'
    base = os.path.basename(path)
    hints = []
    if base:
        search_roots = [os.path.dirname(path), os.path.expanduser('~/Downloads'), os.path.expanduser('~/Desktop')]
        for root in search_roots:
            if not root or not os.path.isdir(root):
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                if dirpath.count(os.sep) - root.count(os.sep) >= 2:
                    dirnames[:] = []
                if base in filenames:
                    hints.append(os.path.join(dirpath, base))
            if hints:
                break
    if hints:
        msg += ' — did you mean: ' + ' or '.join(hints[:3])
    else:
        folder = os.path.dirname(path)
        if folder and os.path.isdir(folder):
            csvs = sorted(f for f in os.listdir(folder) if f.lower().endswith(('.csv', '.txt', '.zip')))[:8]
            if csvs:
                msg += f'. Files in that folder: {", ".join(csvs)}'
                if any(f.lower().endswith('.zip') for f in csvs):
                    msg += ' (unzip the .zip first)'
    return msg


def _estimate_records(total_lines, sample_df):
    """Rows of long text span many lines; estimate records from newlines per sampled record."""
    if sample_df is None or not len(sample_df):
        return total_lines, False
    text = sample_df.select_dtypes(include=['object', 'string'])
    newlines = sum(int(text[c].dropna().astype(str).str.count('\n').sum()) for c in text.columns)
    lines_per_record = 1 + newlines / len(sample_df)
    if lines_per_record <= 1.01:
        return total_lines, False
    return max(len(sample_df), int(round(total_lines / lines_per_record))), True


# Global variables to store data
csv_data = None
file_info = None

def analyze_csv_structure(file_path, total_rows=None, sample_df=None):
    """Analyze CSV structure and provide insights about the data"""
    try:
        # Read first few rows to understand structure (for analysis only)
        if sample_df is None:
            sample_df = pd.read_csv(file_path, nrows=1000, low_memory=False)
        
        analysis = {
            'total_rows': 0,
            'columns': list(sample_df.columns),
            'column_types': {},
            'sample_data': _preview_records(sample_df.head(5)),
            'missing_values': {},
            'unique_values': {},
            'data_insights': []
        }
        
        # Analyze each column
        for col in sample_df.columns:
            analysis['column_types'][col] = str(sample_df[col].dtype)
            analysis['missing_values'][col] = int(sample_df[col].isnull().sum())
            
            # Get unique values (limit to 20 for performance)
            unique_vals = sample_df[col].dropna().unique()
            analysis['unique_values'][col] = [_preview_value(v) for v in unique_vals[:20].tolist()]
            
            # Generate insights based on column name and content
            insights = generate_column_insights(col, sample_df[col])
            analysis['data_insights'].extend(insights)
        
        # Get total row count efficiently
        if total_rows is not None:
            analysis['total_rows'] = total_rows
        else:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    analysis['total_rows'] = sum(1 for line in f) - 1  # Subtract header
            except Exception:
                analysis['total_rows'] = len(sample_df)
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing CSV structure: {str(e)}")
        return None

def generate_column_insights(column_name, series):
    """Generate insights based on column name and data"""
    insights = []
    col_lower = column_name.lower()
    
    # Date-related insights
    if any(word in col_lower for word in ['date', 'time', 'created', 'updated', 'timestamp']):
        try:
            dates = pd.to_datetime(series.dropna(), errors='coerce')
            if not dates.isna().all():
                insights.append(f"Date range: {column_name} contains dates from {dates.min()} to {dates.max()}")
        except:
            pass
    
    # Text content insights
    if any(word in col_lower for word in ['text', 'content', 'description', 'comment']):
        avg_length = series.dropna().astype(str).str.len().mean()
        insights.append(f"Text content: {column_name} has average text length of {avg_length:.0f} characters")
    
    # Numeric insights
    if series.dtype in ['int64', 'float64']:
        insights.append(f"Numeric data: {column_name} is numeric with range {series.min()} to {series.max()}")
    
    # Categorical insights
    if (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)) and series.nunique() < 50:
        top_values = series.value_counts().head(3)
        insights.append(f"Top values: {column_name} top values: {', '.join([f'{k}({v})' for k, v in top_values.items()])}")
    
    return insights

def _apply_filters_to_chunk(chunk, filters):
    """Apply filters to a dataframe chunk. Returns filtered chunk."""
    search_term = filters.get('search', '').lower()
    if search_term:
        text_cols = chunk.select_dtypes(include=['object', 'string']).columns
        mask = pd.Series([False] * len(chunk), index=chunk.index)
        for col in text_cols:
            mask |= chunk[col].astype(str).str.lower().str.contains(search_term, na=False)
        chunk = chunk[mask]

    for column, value in filters.items():
        if column == 'search' or not value or value == 'all':
            continue
        if column in chunk.columns:
            if (pd.api.types.is_object_dtype(chunk[column]) or pd.api.types.is_string_dtype(chunk[column])):
                chunk = chunk[chunk[column].astype(str).str.contains(str(value), case=False, na=False)]
            else:
                chunk = chunk[chunk[column] == value]

    return chunk


def filter_data(filters, page=1, page_size=100):
    """Apply filters to the CSV data. Uses chunked reading for large files.
    Returns (page_rows_df, total_match_count)."""
    global csv_data, file_info

    if csv_data is None:
        return None, 0

    try:
        skip = (page - 1) * page_size
        collected = []
        collected_count = 0
        total_matches = 0

        no_filters = not any(v for k, v in (filters or {}).items() if v not in ('', 'all', None))
        path = (file_info or {}).get('full_file_path')
        if no_filters and path and os.path.exists(path):
            # Nothing filtered: read just the rows for this page instead of scanning a multi-GB file
            head = pd.read_csv(path, nrows=skip + page_size, low_memory=False)
            total = int(file_info.get('exact_rows') or file_info.get('total_rows') or len(head))
            return head.iloc[skip:skip + page_size].reset_index(drop=True), max(total, len(head))

        if file_info and file_info.get('full_file_path') and os.path.exists(file_info['full_file_path']):
            source = pd.read_csv(file_info['full_file_path'], chunksize=10000, low_memory=False)
        else:
            # Wrap small in-memory frame as a single-chunk iterable
            source = [csv_data.copy()]

        for chunk in source:
            filtered_chunk = _apply_filters_to_chunk(chunk, _normalize_filters(filters, chunk.columns))
            chunk_len = len(filtered_chunk)
            total_matches += chunk_len

            # Collect only the rows belonging to the requested page
            if collected_count < skip + page_size:
                chunk_start = max(0, skip - collected_count)
                chunk_end = skip + page_size - collected_count
                slice_ = filtered_chunk.iloc[chunk_start:chunk_end]
                if len(slice_) > 0:
                    collected.append(slice_)
                collected_count += chunk_len

        result = pd.concat(collected, ignore_index=True) if collected else pd.DataFrame(columns=csv_data.columns)
        return result, total_matches

    except Exception as e:
        logger.error(f"Error filtering data: {str(e)}")
        return None, 0

def generate_kpis(df):
    """Generate Key Performance Indicators from the data"""
    try:
        kpis = {}
        
        # Basic counts
        kpis['total_records'] = len(df)
        kpis['total_columns'] = len(df.columns)
        
        # Find company-related columns
        company_cols = [col for col in df.columns if 'company' in col.lower() or 'name' in col.lower()]
        if company_cols:
            company_col = company_cols[0]
            kpis['unique_companies'] = df[company_col].nunique()
            kpis['top_companies'] = df[company_col].value_counts().head(10).to_dict()
        
        # Find date-related columns
        date_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
        if date_cols:
            date_col = date_cols[0]
            try:
                dates = pd.to_datetime(df[date_col], errors='coerce')
                kpis['date_range'] = {
                    'earliest': dates.min().strftime('%Y-%m-%d') if not pd.isna(dates.min()) else None,
                    'latest': dates.max().strftime('%Y-%m-%d') if not pd.isna(dates.max()) else None
                }
            except:
                pass
        
        # Find filing type columns
        filing_cols = [col for col in df.columns if 'filing' in col.lower() or 'type' in col.lower()]
        if filing_cols:
            filing_col = filing_cols[0]
            kpis['filing_types'] = df[filing_col].value_counts().to_dict()
        
        # Find exchange columns
        exchange_cols = [col for col in df.columns if 'exchange' in col.lower()]
        if exchange_cols:
            exchange_col = exchange_cols[0]
            kpis['exchange_distribution'] = df[exchange_col].value_counts().to_dict()
        
        return kpis
        
    except Exception as e:
        logger.error(f"Error generating KPIs: {str(e)}")
        return {}

@app.route('/api/load_path', methods=['POST'])
def load_from_path():
    """Load a CSV directly from a local file path — avoids uploading large files."""
    global csv_data, file_info

    data = request.json or {}
    raw_path = (data.get('path') or '').strip()
    file_path = _resolve_user_path(raw_path)

    if not raw_path:
        return jsonify({'error': 'File path is required'}), 400
    if os.path.isdir(file_path):
        csvs = sorted(f for f in os.listdir(file_path) if f.lower().endswith('.csv'))[:8]
        hint = f' CSV files in it: {", ".join(csvs)}' if csvs else ''
        return jsonify({'error': f'That is a folder, not a file: {file_path}.{hint}'}), 400
    if not os.path.exists(file_path):
        return jsonify({'error': _path_not_found_message(file_path)}), 400
    if file_path.lower().endswith('.zip'):
        return jsonify({'error': 'That is a .zip file. Unzip it first (double-click it in Finder), then load the .csv inside.'}), 400

    try:
        sample_df = pd.read_csv(file_path, nrows=1000, low_memory=False)

        # Count lines without loading the full file; filings span many lines, so estimate records
        with open(file_path, 'rb') as f:
            total_lines = sum(1 for _ in f) - 1
        total_rows, rows_approximate = _estimate_records(total_lines, sample_df)

        csv_data = sample_df
        file_info = {
            'filename': os.path.basename(file_path),
            'full_file_path': file_path,
            'is_path_loaded': True,
            'total_rows': total_rows,
            'rows_approximate': rows_approximate,
            'upload_time': datetime.now().isoformat(),
            'file_size': os.path.getsize(file_path),
        }

        analysis = analyze_csv_structure(file_path, total_rows=total_rows, sample_df=sample_df)

        return jsonify({
            'success': True,
            'total_rows': total_rows,
            'columns': list(sample_df.columns),
            'rows_approximate': rows_approximate,
            'sample_data': _preview_records(sample_df.head(20)),
            'file_info': file_info,
            'analysis': analysis,
        })

    except Exception as e:
        logger.error(f"load_path error: {str(e)}")
        return jsonify({'error': f'Failed to load file: {str(e)}'}), 500


# ---------------------------------------------------------------------------
# Keyword-in-context snippets: return N words before/after each term hit
# instead of whole documents (filing text cells can be hundreds of KB each).
# ---------------------------------------------------------------------------
_WORD_RE = re.compile(r'\S+')
_snippet_cache = {'key': None, 'results': None, 'meta_columns': None}
LONG_TEXT_AVG_CHARS = 300  # object columns averaging more than this are treated as document text


def _parse_terms(raw):
    if isinstance(raw, list):
        terms = raw
    else:
        terms = re.split(r'[,\n;]', str(raw or ''))
    seen, out = set(), []
    for t in (t.strip() for t in terms):
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def _term_regex(terms):
    """Case-insensitive, whole-word match; tolerant of line breaks between words and simple plurals."""
    parts = []
    for t in sorted(terms, key=len, reverse=True):
        words = [re.escape(w) for w in t.split()]
        parts.append(r'\s+'.join(words))
    return re.compile(r'(?<![A-Za-z0-9])(?:' + '|'.join(parts) + r')(?:s|es)?(?![A-Za-z0-9])', re.IGNORECASE)


PREFERRED_TEXT_COLUMNS = ('raw_text', 'full_text', 'filing_text', 'document_text', 'text', 'content', 'body')


def _detect_text_columns(df):
    text_cols = []
    for col in df.select_dtypes(include=['object', 'string']).columns:
        lengths = df[col].dropna().astype(str).str.len()
        if len(lengths) and lengths.mean() > LONG_TEXT_AVG_CHARS:
            text_cols.append(col)
    # If the file has a column that is clearly the full document (e.g. raw_text), search only that,
    # so summaries such as an LLM-written 'excerpt' or 'title' don't produce duplicate hits.
    preferred = [c for c in text_cols if str(c).lower() in PREFERRED_TEXT_COLUMNS]
    return preferred or text_cols


def _word_window_start(text, pos, n_words):
    """Char offset where the n_words words before pos begin."""
    lo = max(0, pos - n_words * 40 - 200)
    starts = [m.start() for m in _WORD_RE.finditer(text, lo, pos)]
    # If the look-back slice was too short to hold n_words, widen it.
    while len(starts) < n_words and lo > 0:
        lo = max(0, lo - n_words * 80)
        starts = [m.start() for m in _WORD_RE.finditer(text, lo, pos)]
    return starts[-n_words] if len(starts) >= n_words else (starts[0] if starts else pos)


def _word_window_end(text, pos, n_words):
    """Char offset where the n_words words after pos end."""
    end = pos
    for i, m in enumerate(_WORD_RE.finditer(text, pos)):
        if i >= n_words:
            break
        end = m.end()
    return end


def extract_snippets(text, pattern, n_words):
    """Return [(snippet_text, [matched terms])]; overlapping windows are merged so no hit is lost."""
    if not isinstance(text, str) or not text:
        return []
    windows = []
    for m in pattern.finditer(text):
        ws = _word_window_start(text, m.start(), n_words)
        we = _word_window_end(text, m.end(), n_words)
        if windows and ws <= windows[-1][1]:
            windows[-1][1] = max(windows[-1][1], we)
            windows[-1][2].append(' '.join(m.group(0).split()))
        else:
            windows.append([ws, we, [' '.join(m.group(0).split())]])
    out = []
    for ws, we, hits in windows:
        snippet = ' '.join(text[ws:we].split())
        prefix = '… ' if ws > 0 else ''
        suffix = ' …' if we < len(text) else ''
        out.append((prefix + snippet + suffix, hits))
    return out


def _normalize_filters(filters, columns):
    """Map the UI's generic filter names (company, filingType, exchange, column/value) onto real columns."""
    def find(keywords):
        for kw in keywords:
            for c in columns:
                if kw in str(c).lower():
                    return c
        return None
    out = {}
    if filters.get('search'):
        out['search'] = filters['search']
    for key, kws in (('company', ['company', 'registrant', 'entity', 'name']),
                     ('filingType', ['form', 'filing_type', 'type']),
                     ('exchange', ['exchange', 'market'])):
        val = filters.get(key)
        col = find(kws) if val else None
        if col:
            out[col] = val
    col, val = filters.get('column'), filters.get('value')
    if col and col != 'all' and val and col in columns:
        out[col] = val
    for k, v in filters.items():  # already-real column names pass through
        if k in columns and v:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# SIC (industry) codes: SEC lookup keyed by CIK, see backend/refresh_sic.py
# ---------------------------------------------------------------------------
_SIC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'sec_sic_lookup.csv')
_sic_lookup = None
_NAME_SUFFIXES = {'INC', 'INCORPORATED', 'CORP', 'CORPORATION', 'CO', 'COMPANY', 'LTD', 'LIMITED',
                  'LLC', 'PLC', 'LP', 'LLP', 'SA', 'NV', 'AG', 'THE'}


def _norm_company_name(name):
    words = re.sub(r'[^A-Z0-9 ]+', ' ', str(name).upper().replace('&', ' AND ')).split()
    while words and words[-1] in _NAME_SUFFIXES:
        words.pop()
    if words and words[0] == 'THE':
        words = words[1:]
    return ' '.join(words)


def _load_sic_lookup():
    global _sic_lookup
    if _sic_lookup is not None:
        return _sic_lookup
    by_cik, by_name, by_ticker, codes = {}, {}, {}, []
    if os.path.exists(_SIC_PATH):
        df = pd.read_csv(_SIC_PATH, dtype=str, keep_default_na=False)
        for cik, sic, desc, name, tickers in zip(df['cik'], df['sic'], df['sic_description'], df['name'], df['tickers']):
            entry = (sic, desc, str(int(cik)))
            by_cik[int(cik)] = entry
            for t in filter(None, str(tickers).upper().split('|')):
                by_ticker[t] = entry if by_ticker.get(t, entry) == entry else None
            key = _norm_company_name(name)
            if key:
                # a name shared by companies in different industries is ambiguous -> no match
                by_name[key] = entry if by_name.get(key, entry) == entry else None
        grouped = df.groupby('sic').agg(description=('sic_description', 'first'), companies=('cik', 'size')).reset_index()
        codes = grouped.sort_values('sic').to_dict('records')
    else:
        logger.warning(f"SIC lookup not found at {_SIC_PATH}; industry filter disabled")
    _sic_lookup = {'by_cik': by_cik, 'by_name': by_name, 'by_ticker': by_ticker, 'codes': codes}
    return _sic_lookup


def _to_cik(value):
    digits = re.sub(r'\D', '', str(value).split('.')[0]) if value is not None else ''
    return int(digits) if digits else None


def _sic_source_column(columns):
    """How to assign SIC codes to rows, as an ordered list of (kind, column) strategies:
    the file's own SIC column, else CIK, else ticker then company name (first match per row wins)."""
    lower = {str(c).lower(): c for c in columns}
    for name in ('sic', 'sic_code', 'siccode', 'sic code'):
        if name in lower:
            return [('sic', lower[name])]
    for c in columns:
        if 'cik' in str(c).lower():
            return [('cik', c)]
    strategies = []
    for name in ('symbol', 'ticker', 'tickers', 'trading_symbol'):
        if name in lower:
            strategies.append(('ticker', lower[name]))
            break
    for kw in ('company', 'registrant', 'entity'):
        col = next((c for c in columns if kw in str(c).lower() and 'id' not in str(c).lower()), None)
        if col is not None:
            strategies.append(('name', col))
            break
    return strategies


def _sic_for_chunk(chunk, strategies):
    """Return a list of (sic, description, cik) per row (empty strings when unknown)."""
    lk = _load_sic_lookup()
    code_desc = {c['sic']: c['description'] for c in lk['codes']}

    def lookup(kind, v):
        if v is None or (isinstance(v, float) and np.isnan(v)) or str(v).strip() in ('', 'nan', '<NA>'):
            return None
        if kind == 'sic':
            code = str(v).split('.')[0].strip().zfill(4)
            return (code, code_desc.get(code, ''), '')
        if kind == 'cik':
            cik = _to_cik(v)
            if cik is None:
                return None
            return lk['by_cik'].get(cik) or ('', '', str(cik))  # keep the CIK for EDGAR links even without a SIC
        if kind == 'ticker':
            return lk['by_ticker'].get(str(v).strip().upper())
        if kind == 'name':
            return lk['by_name'].get(_norm_company_name(v))
        return None

    columns = [chunk[col].tolist() for _, col in strategies]
    out = []
    for i in range(len(chunk)):
        hit = None
        for (kind, _), values in zip(strategies, columns):
            hit = lookup(kind, values[i])
            if hit:
                break
        out.append(hit or ('', '', ''))
    return out


def _edgar_filing_url(accession, cik=''):
    """Link to the filing's index page on sec.gov (formatted tables, exhibits).
    Uses the company's CIK when known, else the CIK embedded in the accession number (works for filing agents too)."""
    acc = re.sub(r'[^0-9-]', '', str(accession or ''))
    digits = acc.replace('-', '')
    if len(digits) != 18:
        return ''
    acc = f"{digits[:10]}-{digits[10:12]}-{digits[12:]}"
    folder_cik = str(int(cik)) if str(cik or '').isdigit() else str(int(digits[:10]))
    return f"https://www.sec.gov/Archives/edgar/data/{folder_cik}/{digits}/{acc}-index.htm"


def _parse_sic_filter(raw):
    """'7370-7379, 48, 4841' -> predicate on a 4-digit SIC string. Plain entries match as prefixes."""
    tests = []
    for tok in re.split(r'[,\s;]+', str(raw or '').strip()):
        if not tok:
            continue
        m = re.fullmatch(r'(\d{1,4})\s*-\s*(\d{1,4})', tok)
        if m:
            lo, hi = int(m.group(1).ljust(4, '0')), int(m.group(2).ljust(4, '9'))
            tests.append(lambda code, lo=lo, hi=hi: code.isdigit() and lo <= int(code) <= hi)
        elif tok.isdigit():
            tests.append(lambda code, p=tok: code.startswith(p))
    if not tests:
        return None
    return lambda code: bool(code) and any(t(code) for t in tests)


@app.route('/api/sic_codes', methods=['GET'])
def sic_codes_endpoint():
    lk = _load_sic_lookup()
    return jsonify({'codes': lk['codes'], 'companies': len(lk['by_cik'])})


def run_snippet_search(terms, n_words, filters):
    """Stream the whole file and collect every snippet (cached for the last query)."""
    source_path = file_info.get('full_file_path') if file_info else None
    key = (source_path, tuple(t.lower() for t in terms), n_words, json.dumps(filters, sort_keys=True))
    if _snippet_cache['key'] == key:
        return _snippet_cache['results'], _snippet_cache['meta_columns']

    pattern = _term_regex(terms)
    if source_path and os.path.exists(source_path):
        source = pd.read_csv(source_path, chunksize=5000, low_memory=False)
    else:
        source = [csv_data.copy()]

    sic_test = _parse_sic_filter(filters.get('sic'))
    other_filters = {k: v for k, v in filters.items() if k != 'sic'}
    results, text_cols, meta_cols, sic_source, records_seen, accession_col = [], None, None, [], 0, None
    for chunk in source:
        if text_cols is None:
            text_cols = _detect_text_columns(chunk) or list(chunk.select_dtypes(include=['object', 'string']).columns)
            meta_cols = [c for c in chunk.columns if c not in text_cols]
            sic_source = _sic_source_column(chunk.columns)
            accession_col = next((c for c in chunk.columns if 'accession' in str(c).lower()), None)
        records_seen += len(chunk)
        chunk = _apply_filters_to_chunk(chunk, {k: v for k, v in _normalize_filters(other_filters, chunk.columns).items() if k != 'search'})
        sics = _sic_for_chunk(chunk, sic_source)
        for (idx, row), (sic, sic_desc, cik) in zip(chunk.iterrows(), sics):
            if sic_test and not sic_test(sic):
                continue
            for col in text_cols:
                for snippet, hits in extract_snippets(row.get(col), pattern, n_words):
                    rec = {c: row[c] for c in meta_cols}
                    edgar = _edgar_filing_url(row[accession_col], cik) if accession_col is not None else ''
                    rec.update({'_row': int(idx) + 1, '_column': col, '_sic': sic, '_sic_description': sic_desc,
                                '_cik': cik, '_edgar_url': edgar,
                                '_matched': ', '.join(sorted({h.lower() for h in hits})),
                                '_hits': len(hits), '_snippet': snippet})
                    results.append(rec)

    if file_info is not None and source_path:
        file_info['exact_rows'] = records_seen
    info = {'meta_columns': meta_cols or [], 'total_records': records_seen,
            'sic_source': '+'.join(k for k, _ in sic_source) or None,
            'sic_source_column': ', '.join(str(c) for _, c in sic_source) or None}
    _snippet_cache.update(key=key, results=results, meta_columns=info)
    return results, info


def _snippet_params():
    body = request.json or {}
    terms = _parse_terms(body.get('terms'))
    n_words = max(5, min(int(body.get('window', 50) or 50), 500))
    return terms, n_words, body.get('filters', {}) or {}, body


@app.route('/api/snippets', methods=['POST'])
def snippets_endpoint():
    if csv_data is None:
        return jsonify({'error': 'Load a file first'}), 400
    terms, n_words, filters, body = _snippet_params()
    if not terms:
        return jsonify({'error': 'Enter at least one search term'}), 400
    try:
        results, info = run_snippet_search(terms, n_words, filters)
        page = max(1, int(body.get('page', 1)))
        page_size = max(1, min(int(body.get('page_size', 50)), 500))
        start = (page - 1) * page_size
        return jsonify({
            'snippets': results[start:start + page_size],
            'total_snippets': len(results),
            'total_documents': len({r['_row'] for r in results}),
            'records_scanned': info.get('total_records'),
            'total_pages': max(1, -(-len(results) // page_size)),
            'page': page,
            'meta_columns': info['meta_columns'],
            'sic_source': info['sic_source'],
            'sic_source_column': info['sic_source_column'],
            'snippets_without_sic': sum(1 for r in results if not r['_sic']),
            'terms': terms,
            'window': n_words,
        })
    except Exception as e:
        logger.error(f"Snippet search error: {str(e)}")
        return jsonify({'error': f'Snippet search failed: {str(e)}'}), 500


@app.route('/api/snippets/export', methods=['POST'])
def snippets_export():
    if csv_data is None:
        return jsonify({'error': 'Load a file first'}), 400
    terms, n_words, filters, _ = _snippet_params()
    if not terms:
        return jsonify({'error': 'Enter at least one search term'}), 400
    try:
        results, info = run_snippet_search(terms, n_words, filters)
        meta_cols = info['meta_columns']
        df = pd.DataFrame(results, columns=meta_cols + ['_cik', '_sic', '_sic_description', '_edgar_url', '_row', '_column', '_matched', '_hits', '_snippet'])
        df = df.rename(columns={'_cik': 'sec_cik', '_sic': 'sec_sic_code', '_sic_description': 'sec_sic_description', '_edgar_url': 'edgar_filing_url',
                                '_row': 'source_row', '_column': 'text_column', '_matched': 'matched_terms',
                                '_hits': 'hits_in_snippet', '_snippet': f'snippet_{n_words}_words_each_side'})
        output = io.StringIO()
        df.to_csv(output, index=False)
        slug = '_'.join(re.sub(r'\W+', '', t) for t in terms)[:60]
        filename = f"snippets_{slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv',
                          as_attachment=True, download_name=filename)
    except Exception as e:
        logger.error(f"Snippet export error: {str(e)}")
        return jsonify({'error': f'Export failed: {str(e)}'}), 500


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload and analyze CSV file"""
    global csv_data, file_info
    
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save uploaded file temporarily
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, file.filename)
        file.save(file_path)
        
        logger.info(f"File uploaded: {file.filename}")
        
        # Analyze file structure
        analysis = analyze_csv_structure(file_path)
        if not analysis:
            return jsonify({'error': 'Failed to analyze file structure'}), 500
        
        # Load data for filtering - HYBRID APPROACH
        try:
            logger.info(f"Loading CSV file with hybrid approach: {file_path}")

            file_info = {
                'filename': file.filename,
                'upload_time': datetime.now().isoformat(),
                'file_size': os.path.getsize(file_path),
                'full_file_path': file_path,
                'is_sampled': False,
            }

            # For display and initial analysis, use sampling for performance
            csv_data = pd.read_csv(file_path, low_memory=False)

            # For very large files, sample for display but keep full file path for search
            if len(csv_data) > 100000:
                csv_data_sample = csv_data.sample(n=100000, random_state=42)
                analysis['total_rows'] = len(csv_data)
                analysis['sample_rows'] = len(csv_data_sample)
                analysis['data_insights'].append(f"Display sample: {len(csv_data_sample):,} rows | Full dataset: {len(csv_data):,} rows")
                csv_data = csv_data_sample
                file_info['is_sampled'] = True
            else:
                analysis['total_rows'] = len(csv_data)
                analysis['data_insights'].append(f"Full dataset loaded: {len(csv_data):,} rows")

            logger.info(f"Successfully loaded {len(csv_data):,} rows for display")
            
        except Exception as e:
            logger.error(f"Error loading CSV: {str(e)}")
            return jsonify({'error': f'Error loading CSV: {str(e)}'}), 500
        
        # Clean up temp file
        os.remove(file_path)
        os.rmdir(temp_dir)
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'file_info': file_info
        })
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/filter', methods=['POST'])
def filter_data_endpoint():
    """Apply filters to the data with pagination."""
    try:
        body = request.json or {}
        filters = body.get('filters', {})
        page = int(body.get('page', 1))
        page_size = int(body.get('page_size', 100))

        page_df, total_matches = filter_data(filters, page=page, page_size=page_size)
        if page_df is None:
            return jsonify({'error': 'No data available'}), 400

        result = {
            'filtered_data': _preview_records(page_df),
            'total_filtered_rows': total_matches,
            'page': page,
            'page_size': page_size,
            'total_pages': max(1, -(-total_matches // page_size)),
            'columns': list(page_df.columns),
        }

        return jsonify(result)

    except Exception as e:
        logger.error(f"Filter error: {str(e)}")
        return jsonify({'error': f'Filter failed: {str(e)}'}), 500

@app.route('/api/export', methods=['POST'])
def export_data():
    """Export every row matching the filters (full text, not previews) as CSV, streamed to a temp file."""
    try:
        filters = (request.json or {}).get('filters', {}) or {}
        if csv_data is None:
            return jsonify({'error': 'No data available'}), 400
        path = (file_info or {}).get('full_file_path')
        source = pd.read_csv(path, chunksize=5000, low_memory=False) if path and os.path.exists(path) else [csv_data.copy()]
        out = tempfile.NamedTemporaryFile(prefix='export_', suffix='.csv', delete=False)
        out.close()
        wrote_header = False
        for chunk in source:
            chunk = _apply_filters_to_chunk(chunk, _normalize_filters(filters, chunk.columns))
            if len(chunk) or not wrote_header:
                chunk.to_csv(out.name, mode='a', index=False, header=not wrote_header)
                wrote_header = True
        base = os.path.splitext((file_info or {}).get('filename') or 'data')[0]
        filename = f"{base}_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return send_file(out.name, mimetype='text/csv', as_attachment=True, download_name=filename)
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return jsonify({'error': f'Export failed: {str(e)}'}), 500

@app.route('/api/insights', methods=['GET'])
def get_insights():
    """Get data insights and recommendations"""
    global csv_data
    
    if csv_data is None:
        return jsonify({'error': 'No data loaded'}), 400
    
    try:
        insights = {
            'data_summary': {
                'total_rows': len(csv_data),
                'total_columns': len(csv_data.columns),
                'memory_usage': f"{csv_data.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB"
            },
            'recommendations': [],
            'filter_suggestions': []
        }
        
        # Generate recommendations based on data
        for col in csv_data.columns:
            col_lower = col.lower()
            
            # Date column recommendations
            if 'date' in col_lower:
                insights['recommendations'].append(f"Filter by {col} to analyze trends over time")
                insights['filter_suggestions'].append({
                    'column': col,
                    'type': 'date_range',
                    'description': f'Filter {col} by date range'
                })
            
            # Categorical column recommendations
            elif (pd.api.types.is_object_dtype(csv_data[col]) or pd.api.types.is_string_dtype(csv_data[col])) and csv_data[col].nunique() < 50:
                insights['recommendations'].append(f"Filter by {col} to focus on specific categories")
                insights['filter_suggestions'].append({
                    'column': col,
                    'type': 'dropdown',
                    'options': csv_data[col].value_counts().head(10).index.tolist(),
                    'description': f'Filter {col} by category'
                })
            
            # Text column recommendations
            elif (pd.api.types.is_object_dtype(csv_data[col]) or pd.api.types.is_string_dtype(csv_data[col])):
                insights['recommendations'].append(f"Search within {col} for specific content")
                insights['filter_suggestions'].append({
                    'column': col,
                    'type': 'text_search',
                    'description': f'Search within {col}'
                })
        
        return jsonify(insights)
        
    except Exception as e:
        logger.error(f"Insights error: {str(e)}")
        return jsonify({'error': f'Insights failed: {str(e)}'}), 500

@app.route('/api/search_full_file', methods=['POST'])
def search_full_file():
    """Search the entire file for keywords and return results"""
    global csv_data, file_info
    
    if csv_data is None:
        return jsonify({'error': 'No data loaded'}), 400
    
    try:
        request_data = request.json
        keyword = request_data.get('keyword', '').lower()
        limit = request_data.get('limit', 10000)  # Default limit to prevent huge responses
        
        if not keyword:
            return jsonify({'error': 'Keyword is required'}), 400
        
        logger.info(f"Searching for keyword: {keyword}")
        
        # Check if we have the full file path (for large files)
        if file_info.get('is_sampled') and 'full_file_path' in file_info:
            logger.info(f"Searching full file: {file_info['full_file_path']}")
            # Load full file for search
            full_data = pd.read_csv(file_info['full_file_path'], low_memory=False)
            search_data = full_data
            total_rows = len(full_data)
        else:
            # Use loaded data (for smaller files)
            search_data = csv_data
            total_rows = len(csv_data)
        
        # Search across all text columns
        text_columns = search_data.select_dtypes(include=['object', 'string']).columns
        mask = pd.Series([False] * len(search_data))
        
        for col in text_columns:
            mask |= search_data[col].astype(str).str.lower().str.contains(keyword, na=False)
        
        # Get matching rows
        matching_rows = search_data[mask]
        total_matches = len(matching_rows)
        
        # Limit results for API response
        if len(matching_rows) > limit:
            matching_rows = matching_rows.head(limit)
            limited = True
        else:
            limited = False
        
        result = {
            'keyword': keyword,
            'total_matches': total_matches,
            'returned_rows': len(matching_rows),
            'limited': limited,
            'total_file_rows': total_rows,
            'searched_full_file': file_info.get('is_sampled', False),
            'search_results': _preview_records(matching_rows),
            'columns': list(search_data.columns)
        }
        
        logger.info(f"Found {total_matches:,} matches for '{keyword}' in {total_rows:,} total rows")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return jsonify({'error': f'Search failed: {str(e)}'}), 500

@app.route('/api/download_full_search', methods=['POST'])
def download_full_search():
    """Download all matching rows from full file search"""
    global csv_data, file_info
    
    if csv_data is None:
        return jsonify({'error': 'No data loaded'}), 400
    
    try:
        request_data = request.json
        keyword = request_data.get('keyword', '').lower()
        
        if not keyword:
            return jsonify({'error': 'Keyword is required'}), 400
        
        logger.info(f"Preparing download for keyword: {keyword}")
        
        # Check if we have the full file path (for large files)
        if file_info.get('is_sampled') and 'full_file_path' in file_info:
            logger.info(f"Searching full file for download: {file_info['full_file_path']}")
            # Load full file for search
            full_data = pd.read_csv(file_info['full_file_path'], low_memory=False)
            search_data = full_data
        else:
            # Use loaded data (for smaller files)
            search_data = csv_data
        
        # Search across all text columns
        text_columns = search_data.select_dtypes(include=['object', 'string']).columns
        mask = pd.Series([False] * len(search_data))
        
        for col in text_columns:
            mask |= search_data[col].astype(str).str.lower().str.contains(keyword, na=False)
        
        # Get all matching rows (no limit for download)
        matching_rows = search_data[mask]
        
        # Create CSV in memory
        output = io.StringIO()
        matching_rows.to_csv(output, index=False)
        output.seek(0)
        
        # Create file response
        filename = f"search_results_{keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        logger.info(f"Downloading {len(matching_rows):,} rows matching '{keyword}' from {len(search_data):,} total rows")
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

@app.route('/api/get_filter_options', methods=['GET'])
def get_filter_options():
    """Get predefined filter options based on data analysis"""
    global csv_data, file_info
    
    if csv_data is None:
        return jsonify({'error': 'No data loaded'}), 400
    
    try:
        logger.info("Generating filter options from data")
        
        # Check if we have the full file path (for large files)
        if file_info.get('is_sampled') and 'full_file_path' in file_info:
            # Use full file for accurate filter options
            full_data = pd.read_csv(file_info['full_file_path'], low_memory=False)
            analysis_data = full_data
        else:
            analysis_data = csv_data
        
        filter_options = {
            'company_filters': {},
            'filing_type_filters': {},
            'exchange_filters': {},
            'date_filters': {},
            'keyword_suggestions': [],
            'revenue_filters': {}
        }
        
        # Company filters (Top companies)
        company_cols = [col for col in analysis_data.columns if 'company' in col.lower()]
        if company_cols:
            company_col = company_cols[0]
            top_companies = analysis_data[company_col].value_counts().head(20)
            filter_options['company_filters'] = {
                'column': company_col,
                'label': 'Top Companies',
                'options': [{'value': company, 'label': f'{company} ({count} filings)', 'count': count} 
                           for company, count in top_companies.items()]
            }
        
        # Filing type filters
        filing_cols = [col for col in analysis_data.columns if 'filing' in col.lower() or 'type' in col.lower()]
        if filing_cols:
            filing_col = filing_cols[0]
            filing_types = analysis_data[filing_col].value_counts()
            filter_options['filing_type_filters'] = {
                'column': filing_col,
                'label': 'Filing Types',
                'options': [{'value': ftype, 'label': f'{ftype} ({count} filings)', 'count': count} 
                           for ftype, count in filing_types.items()]
            }
        
        # Exchange filters
        exchange_cols = [col for col in analysis_data.columns if 'exchange' in col.lower()]
        if exchange_cols:
            exchange_col = exchange_cols[0]
            exchanges = analysis_data[exchange_col].value_counts()
            filter_options['exchange_filters'] = {
                'column': exchange_col,
                'label': 'Stock Exchanges',
                'options': [{'value': exchange, 'label': f'{exchange} ({count} companies)', 'count': count} 
                           for exchange, count in exchanges.items()]
            }
        
        # Date filters
        date_cols = [col for col in analysis_data.columns if 'date' in col.lower()]
        if date_cols:
            date_col = date_cols[0]
            try:
                dates = pd.to_datetime(analysis_data[date_col], errors='coerce')
                if not dates.isna().all():
                    filter_options['date_filters'] = {
                        'column': date_col,
                        'label': 'Filing Dates',
                        'earliest': dates.min().strftime('%Y-%m-%d'),
                        'latest': dates.max().strftime('%Y-%m-%d'),
                        'year_options': [{'value': year, 'label': f'{year}', 'count': count} 
                                        for year, count in dates.dt.year.value_counts().head(10).items()]
                    }
            except:
                pass
        
        # Revenue filters (if numeric)
        revenue_cols = [col for col in analysis_data.columns if 'revenue' in col.lower()]
        if revenue_cols:
            revenue_col = revenue_cols[0]
            if analysis_data[revenue_col].dtype in ['int64', 'float64']:
                revenue_data = analysis_data[revenue_col].dropna()
                if len(revenue_data) > 0:
                    filter_options['revenue_filters'] = {
                        'column': revenue_col,
                        'label': 'Revenue Range',
                        'min': float(revenue_data.min()),
                        'max': float(revenue_data.max()),
                        'avg': float(revenue_data.mean()),
                        'ranges': [
                            {'label': 'High Revenue (>$1B)', 'min': 1000000000, 'max': float('inf')},
                            {'label': 'Medium Revenue ($100M-$1B)', 'min': 100000000, 'max': 1000000000},
                            {'label': 'Low Revenue (<$100M)', 'min': 0, 'max': 100000000}
                        ]
                    }
        
        # Keyword suggestions based on common terms
        text_cols = analysis_data.select_dtypes(include=['object', 'string']).columns
        common_terms = []
        
        for col in text_cols[:3]:  # Analyze first 3 text columns
            text_data = analysis_data[col].dropna().astype(str)
            # Extract common business terms
            words = ' '.join(text_data).lower().split()
            word_counts = pd.Series(words).value_counts()
            
            # Filter for business-relevant terms
            business_terms = ['revenue', 'profit', 'growth', 'merger', 'acquisition', 'earnings', 
                            'financial', 'quarterly', 'annual', 'report', 'filing', 'sec', 
                            'company', 'business', 'market', 'sales', 'income', 'assets']
            
            for term in business_terms:
                if term in word_counts.index and word_counts[term] > 10:
                    common_terms.append({'term': term, 'count': word_counts[term]})
        
        # Remove duplicates and sort by count
        seen = set()
        unique_terms = []
        for term in common_terms:
            if term['term'] not in seen:
                seen.add(term['term'])
                unique_terms.append(term)
        
        filter_options['keyword_suggestions'] = sorted(unique_terms, key=lambda x: x['count'], reverse=True)[:20]
        
        logger.info(f"Generated filter options: {len(filter_options)} categories")
        return jsonify(filter_options)
        
    except Exception as e:
        logger.error(f"Filter options error: {str(e)}")
        return jsonify({'error': f'Filter options failed: {str(e)}'}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current status of the backend"""
    global csv_data, file_info
    
    status = {
        'data_loaded': csv_data is not None,
        'file_info': file_info,
        'data_shape': csv_data.shape if csv_data is not None else None
    }
    
    # Add hybrid approach information
    if file_info:
        status['loading_mode'] = 'hybrid'
        status['is_sampled'] = file_info.get('is_sampled', False)
        if file_info.get('is_sampled'):
            status['display_rows'] = csv_data.shape[0] if csv_data is not None else 0
            status['total_file_rows'] = file_info.get('total_rows', 0)
            status['note'] = 'Display uses sample, search uses full file'
        else:
            status['note'] = 'Full file loaded'
    
    return jsonify(status)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)