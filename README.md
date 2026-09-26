# CSV Analyzer

A React + Python tool for analyzing large SEC filing CSV files (8-K, 10-K, and others) without browser memory limits.

## Architecture

```
csv_analyzer/
├── src/                  # React frontend
│   ├── components/
│   │   ├── FileUpload.js     # Path-based loader (large files) + browser upload (small files)
│   │   ├── DataViewer.js     # Paginated table with server-side filtering
│   │   ├── KPIAnalysis.js    # KPI metrics display
│   │   └── ComponentStyles.css
│   ├── utils/
│   │   └── FastFileLoader.js # In-browser CSV parser (small files only)
│   ├── App.js
│   └── App.css
└── backend/              # Python Flask API
    ├── app.py            # REST API — load, filter, export, search
    ├── requirements.txt
    └── start.sh
```

## Getting Started

### 1. Start the Python backend

```bash
cd backend
./start.sh
```

Runs on `http://localhost:5001`. Required for large files.

### 2. Start the frontend

```bash
npm install
npm run build
npx serve -s build -l 3000
```

Open `http://localhost:3000`.

> For development with hot reload use `npm start` instead of build+serve.

## Loading Files

### Large files (hundreds of MB to several GB)

Use **Load from Path** mode (default). Enter the full path to your CSV:

```
/Users/yourname/Downloads/8k_filings_raw_text_2024.csv
```

The Python backend reads the file directly from disk — the browser never loads it into memory. Filtering streams the file in 10,000-row chunks via pandas.

### Small files (under ~200 MB)

Switch to **Upload in Browser** mode. The file is parsed locally in-browser (no backend needed), capped at 100,000 rows.

## Keyword Snippets (keyword in context)

Filing text columns can hold an entire 10-K per cell, so a normal search returns huge rows. **Keyword Snippets** (shown after loading a file with *Load from Path*) returns only the words around each hit:

- Enter one or more comma-separated terms, e.g. `ARPU, average revenue per user, ARPPU, revenue per subscriber`
- Choose how many words to keep on each side (default **50**)
- Optionally narrow by company or form type (10-K, 8-K, 6-K…)
- Matching is case-insensitive, whole-word (`ARPU` does not match `SARPU`), tolerates line breaks inside phrases, and includes simple plurals (`ARPUs`)
- Hits that are close together are merged into one snippet, so numbers next to each other aren't split
- Long text columns (e.g. `section_7`, `text`) are detected automatically; every other column is kept as metadata
- **Export Snippets CSV** downloads every snippet with its metadata, source row and text column

The first search streams the whole file; paging and export of the same query reuse the cached result.

### Industry filter (SEC SIC codes)

Each snippet is tagged with the company's SEC Standard Industrial Classification code, and you can restrict a search to industries:

- Enter codes or prefixes, comma-separated: `7370-7379` (software & internet), `48` (communications), `4841, 7841` (cable & streaming). Plain entries match as prefixes, so `737` covers 7370–7379.
- Codes come from `backend/data/sec_sic_lookup.csv` (67,717 SEC filers, pulled from EDGAR on 2026-09-26) and are matched on the file's **CIK** column. If the file has no CIK column, they're matched by normalized company name; if it already has a `sic` column, that is used as-is.
- SIC codes are the SEC's current assignment and can be dated (Netflix is still 7841 "Video Tape Rental"), so check company lists, not just codes.
- Refresh the lookup any time: `cd backend && python refresh_sic.py "Your Name you@email.com"` (downloads ~1.5 GB from the SEC).


## Filtering & Search

- Filters run **server-side** in backend mode — all rows are searched regardless of file size
- Results are paginated at **100 rows per page** with prev/next controls
- Supports: keyword search, company name, filing type (8-K, 10-K…), exchange, and per-column value filtering

## Export

Click **Export Filtered Data** to download the current filtered result set as a CSV.

## Backend API

| Endpoint | Method | Description |
|---|---|---|
| `/api/load_path` | POST | Load CSV from a local file path |
| `/api/upload` | POST | Upload a CSV file directly |
| `/api/filter` | POST | Filter data with pagination |
| `/api/snippets` | POST | Keyword-in-context snippets (`terms`, `window`, `filters`, `page`) |
| `/api/snippets/export` | POST | Download all snippets for a query as CSV |
| `/api/sic_codes` | GET | SEC SIC codes with descriptions and company counts |
| `/api/export` | POST | Download filtered rows as CSV |
| `/api/search_full_file` | POST | Keyword search across full file |
| `/api/status` | GET | Check backend status |

## Tech Stack

- **Frontend**: React, Lucide React
- **Backend**: Python, Flask, pandas, numpy
- **Serving**: `serve` (production build) or `react-scripts start` (dev)
