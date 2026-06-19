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
| `/api/export` | POST | Download filtered rows as CSV |
| `/api/search_full_file` | POST | Keyword search across full file |
| `/api/status` | GET | Check backend status |

## Tech Stack

- **Frontend**: React, Lucide React
- **Backend**: Python, Flask, pandas, numpy
- **Serving**: `serve` (production build) or `react-scripts start` (dev)
