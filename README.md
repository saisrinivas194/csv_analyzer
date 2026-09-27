# CSV Analyzer

A React + Python (Flask/pandas) tool for searching very large SEC filing CSVs (8-K, 10-K, 6-K…) without browser memory limits. It was built for pulling metrics such as **average revenue per user (ARPU)** out of filing text: find every mention, see just the words around it, narrow by industry, and jump to the original filing on EDGAR to read the table.

## Contents

- [Quick start](#quick-start)
- [Updating](#updating)
- [Loading a file](#loading-a-file)
- [Keyword Snippets](#keyword-snippets)
- [Industry filter (SEC SIC codes)](#industry-filter-sec-sic-codes)
- [View filing on EDGAR](#view-filing-on-edgar)
- [Data table, filters and export](#data-table-filters-and-export)
- [Using the Kaggle 8-K 2024 dataset](#using-the-kaggle-8-k-2024-dataset)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)
- [Backend API](#backend-api)
- [Project structure](#project-structure)

## Quick start

Requires Python 3 and Node.js. Use two Terminal windows.

**1. Backend** (Python API on `http://localhost:5001`, needed for large files):

```bash
cd backend
./start.sh
```

The first run creates a virtual environment and installs dependencies. It's ready when you see `Running on http://127.0.0.1:5001`.

**2. Frontend:**

```bash
npm install
npm run build
npx serve -s build -l 3000
```

Open **http://localhost:3000**. For development with hot reload, use `npm start` instead of build + serve.

## Updating

```bash
git pull
npm run build
```

Then restart both: `Ctrl+C` in the backend window and run `./start.sh` again, and `Ctrl+C` in the frontend window and run `npx serve -s build -l 3000` again. The backend loads new code and the SIC lookup only on startup.

## Loading a file

### Load from Path (large files, default)

Enter the full path to the CSV on the machine running the backend and click **Load**. The backend reads the file straight from disk; the browser never holds it.

Accepted path formats:

| You paste | Works |
|---|---|
| `/Users/you/Downloads/8k_filings_raw_text_2024.csv` | ✓ |
| `~/Downloads/8k_filings_raw_text_2024.csv` | ✓ |
| `"/Users/you/My Files/data.csv"` (quoted) | ✓ |
| `/Users/you/My\ Files/data.csv` (dragged into Terminal) | ✓ |
| `file:///Users/you/Downloads/data.csv` | ✓ |

Tip: in Finder, right-click the file, hold **Option**, and choose **Copy "…" as Pathname**.

If the file isn't found, the error says so and suggests where a file with that name actually is (for example inside a Kaggle `archive/` folder). Folders and `.zip` files are rejected with a clear message: unzip first.

### Upload in Browser (small files only, under 200 MB)

Parses the file inside the browser, with no backend needed, capped at 100,000 rows. Files over **200 MB** are refused, because holding them in the tab crashes it; the app switches to Load from Path and fills in `~/Downloads/<file name>`.

### What loading shows

- **Row count:** for files whose text spans many lines (like filings), the count is an estimate, shown with `≈`. The exact count is recorded after the first full snippet search.
- **Table previews:** long text cells are cut to 400 characters in the table, so whole filings are never sent to the browser. Full text is still used by Keyword Snippets and exports.

## Keyword Snippets

Filing text cells can hold an entire filing, so an ordinary search returns enormous rows. **Keyword Snippets** (shown after Load from Path) returns only the words around each hit.

1. Enter one or more comma-separated terms, e.g. `ARPU, average revenue per user, ARPPU, revenue per subscriber`.
2. Choose **Words each side** (default **50**, range 5–500).
3. Optionally narrow by **Company**, **Form type** (8-K, 10-K, 6-K…) or **Industry** (see below).
4. Click **Find Snippets**.

How matching works:

- Case-insensitive and whole-word: `ARPU` matches `ARPU` and `ARPUs`, not `SARPU`.
- Phrases still match across line breaks (`average\nrevenue per user`).
- Hits close together are merged into one snippet, so adjacent numbers aren't split; the card shows how many hits it contains.
- Long text columns are detected automatically and everything else is shown as metadata. If a column is clearly the full document (`raw_text`, `text`, `full_text`…), only that column is searched, so summary columns don't create duplicate hits.

Performance: the first search streams the whole file (about 1–2 minutes for a 3.5 GB file). Paging and export for the same search reuse the cached result and are instant.

**Export Snippets CSV** downloads every snippet for the current search with its metadata, `sec_cik`, `sec_sic_code`, `sec_sic_description`, `edgar_filing_url`, source row, text column and matched terms.

## Industry filter (SEC SIC codes)

Every snippet is tagged with the company's SEC Standard Industrial Classification code, and searches can be limited to industries.

- Enter codes, prefixes or ranges, comma-separated: `7370-7379` (software & internet), `48` (communications), `4841, 7841` (cable & streaming). Plain entries match as prefixes, so `737` covers 7370–7379.
- Presets: Software & internet, Communications (telecom, cable, broadcast), Cable & streaming, Media & publishing. The line under the field lists which codes your entry covers.

Where the codes come from: `backend/data/sec_sic_lookup.csv`, which lists **67,717 SEC filers across 448 SIC codes**, pulled from the SEC's EDGAR bulk submissions file on 2026-09-26. Filers without a code (individuals, most funds) and the placeholder code `0000` are excluded.

How rows are matched to a company, in order:

1. the file's own `sic` column, if it has one
2. a **CIK** column (exact)
3. a **ticker** column (`symbol`/`ticker`), then the **company name** (normalized, e.g. "Reddit, Inc." = "REDDIT INC")

A note under the results says which method was used and how many snippets had no match.

To refresh the lookup from the SEC (downloads ~1.5 GB; the SEC requires a contact in the User-Agent):

```bash
cd backend
python refresh_sic.py "Your Name you@email.com"
```

## View filing on EDGAR

When the file has an accession-number column (e.g. `sec_accession_number`), every snippet gets a **View filing on EDGAR ↗** link to the filing's index page on sec.gov, where tables and exhibits are properly formatted. Use it to read tables that appear flattened in the snippet text. Links use the company's CIK when known, otherwise the CIK inside the accession number, which also works for filings submitted by filing agents.

## Data table, filters and export

- The table and its filters (search, company, filing type, exchange, per-column value) run **server-side** over the whole file, 100 rows per page.
- Unfiltered pages read only the rows shown, so the first page appears in under a second even for multi-GB files. Filtered pages scan the file.
- **Export Filtered Data** downloads every matching row with full text (not the table previews). Without filters, that is the whole file.

## Using the Kaggle 8-K 2024 dataset

[SEC 8k Raw Text Filings 2024](https://www.kaggle.com/datasets/datavadar/sec-8k-raw-text-filings-2024): `8k_filings_raw_text_2024.csv`, about 58,000 8-K filings from 2024, 3.5 GB, CC0.

- Download it from Kaggle (free account needed) and unzip it. It usually ends up at `~/Downloads/archive/8k_filings_raw_text_2024.csv`.
- Load it with **Load from Path**, not Upload in Browser.
- Columns: `sec_accession_number, release_datetime, title, sec_filing_type, keywords, exchange, symbol, company_name, excerpt, raw_text`. There is no CIK column, so SIC codes are matched by `symbol`, then `company_name`.
- `title`, `keywords` and `excerpt` are LLM-generated, so snippet search reads only `raw_text`, and those columns are hidden on result cards.
- `raw_text` flattens tables (cells run together, e.g. `ARPA (1)$134.10 $128.02 4.7`), so use **View filing on EDGAR** to read tables.

Example: `ARPU, average revenue per user` finds 759 snippets in 292 filings; with the Communications (`48`) filter, 324 snippets in 125 filings.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Browser tab shows **"Aw, Snap!" / error code 5** | The file was opened with **Upload in Browser** and ran the tab out of memory. Use **Load from Path**. Current versions refuse browser uploads over 200 MB. |
| **"Address already in use"** when starting the backend | An older backend is still running. Run `lsof -ti:5001 \| xargs kill`, then `./start.sh`. |
| `serve` picks a random port instead of 3000 | Something is already on 3000. Open the address it prints, or run `lsof -ti:3000 \| xargs kill` first. |
| **"File not found"** / HTTP 400 on load | The path is wrong. Follow the "did you mean" suggestion in the error, or copy the path from Finder (see above). |
| **"Cannot reach backend on port 5001"** | Start the backend (`cd backend && ./start.sh`). |
| **"The string did not match the expected pattern"** (Safari) | Fixed: empty cells used to be sent as invalid JSON. Update and restart the backend. |
| Search or filters return nothing on a new install | Fixed: pandas 3 stores text as a `string` type the old code ignored. Update and restart the backend. |
| New features don't appear | Rebuild (`npm run build`), restart both servers, and hard-reload the browser. |

## Known limitations

- SIC codes are the SEC's **current** assignment and can be outdated or unexpected (Netflix is still 7841 "Video Tape Rental"). Check company lists, not only codes.
- Ticker/name matching can miss companies whose ticker or name changed; a CIK column gives exact matches.
- Row counts for multi-line text files are estimates until the first full snippet search.
- The first snippet search and filtered table pages scan the whole file each time a new query runs.
- The backend is a local development server (Flask debug mode) meant for one user on one machine.

## Backend API

| Endpoint | Method | Description |
|---|---|---|
| `/api/load_path` | POST | Load a CSV from a local path (`path`) |
| `/api/upload` | POST | Upload a CSV file directly |
| `/api/filter` | POST | Filtered, paginated rows (`filters`, `page`, `page_size`); long text previewed |
| `/api/export` | POST | Download all rows matching `filters` as CSV, full text |
| `/api/snippets` | POST | Keyword-in-context snippets (`terms`, `window`, `filters` incl. `sic`, `page`, `page_size`) |
| `/api/snippets/export` | POST | Download all snippets for a query as CSV |
| `/api/sic_codes` | GET | SEC SIC codes with descriptions and company counts |
| `/api/search_full_file` | POST | Keyword search across the full file |
| `/api/status` | GET | Backend status |

## Project structure

```
csv_analyzer/
├── src/                          # React frontend
│   ├── components/
│   │   ├── FileUpload.js         # Load from Path + Upload in Browser (<200 MB)
│   │   ├── SnippetSearch.js      # Keyword Snippets, industry filter, EDGAR links
│   │   ├── DataViewer.js         # Paginated table, server-side filters, export
│   │   ├── KPIAnalysis.js        # KPI metrics display
│   │   └── ComponentStyles.css
│   ├── utils/
│   │   └── FastFileLoader.js     # In-browser CSV parser (small files)
│   ├── App.js
│   └── App.css
└── backend/                      # Python Flask API
    ├── app.py                    # Load, filter, export, snippets, SIC matching
    ├── data/
    │   └── sec_sic_lookup.csv    # CIK → SIC code, description, name, tickers
    ├── refresh_sic.py            # Rebuilds the SIC lookup from the SEC
    ├── requirements.txt
    └── start.sh
```

**Tech stack:** React and Lucide React (frontend); Python, Flask, pandas and numpy (backend); `serve` for the production build.
