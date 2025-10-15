# Python CSV Backend - Smart Data Filtering & Analysis

A powerful Python backend that efficiently processes large CSV files and provides intelligent filtering capabilities for your CSV analyzer frontend.

##  Features

###  Smart Data Analysis
- **Automatic Structure Detection**: Analyzes CSV structure and data types
- **Intelligent Insights**: Generates business-relevant insights based on column names
- **Data Quality Assessment**: Identifies missing values, data types, and cardinality
- **Performance Optimization**: Handles large files with smart sampling

###  Advanced Filtering
- **Multi-Column Filtering**: Filter by any combination of columns
- **Text Search**: Full-text search across all text columns
- **Date Range Filtering**: Smart date filtering with range detection
- **Categorical Filtering**: Dropdown filters for low-cardinality columns
- **Numeric Range Filtering**: Min/max filtering for numeric data

###  Business Intelligence
- **KPI Generation**: Automatic calculation of key metrics
- **Trend Analysis**: Date-based trend detection
- **Company Analysis**: Top companies, filing types, exchange distribution
- **Data Export**: Export filtered results as CSV

## Installation & Setup

### 1. Start the Backend Server
```bash
cd backend
./start.sh
```

This will:
- Create a Python virtual environment
- Install all required dependencies
- Start the Flask server on port 5001

### 2. Test the Backend
```bash
# Check if server is running
curl http://localhost:5001/api/status
```

##  API Endpoints

### Upload & Analyze CSV
```http
POST /api/upload
Content-Type: multipart/form-data

Form data:
- file: CSV file to upload
```

**Response:**
```json
{
  "success": true,
  "analysis": {
    "total_rows": 1000000,
    "columns": ["company_name", "filing_date", "filing_type", ...],
    "column_types": {...},
    "data_insights": [...],
    "sample_data": [...]
  },
  "file_info": {
    "filename": "data.csv",
    "upload_time": "2024-01-01T12:00:00",
    "file_size": 3400000000
  }
}
```

### Filter Data
```http
POST /api/filter
Content-Type: application/json

{
  "filters": {
    "search": "Apple",
    "filing_type": "10-K",
    "exchange": "NASDAQ"
  }
}
```

**Response:**
```json
{
  "filtered_data": [...],
  "total_filtered_rows": 1500,
  "columns": [...],
  "kpis": {
    "total_records": 1500,
    "unique_companies": 25,
    "top_companies": {...},
    "filing_types": {...}
  }
}
```

### Export Filtered Data
```http
POST /api/export
Content-Type: application/json

{
  "filters": {
    "search": "Apple",
    "filing_type": "10-K"
  }
}
```

**Response:** CSV file download

### Get Data Insights
```http
GET /api/insights
```

**Response:**
```json
{
  "data_summary": {
    "total_rows": 1000000,
    "total_columns": 15,
    "memory_usage": "245.67 MB"
  },
  "recommendations": [
    " Filter by filing_date to analyze trends over time",
    " Filter by filing_type to focus on specific categories"
  ],
  "filter_suggestions": [
    {
      "column": "filing_type",
      "type": "dropdown",
      "options": ["10-K", "10-Q", "8-K", "DEF 14A"],
      "description": "Filter filing_type by category"
    }
  ]
}
```

## Standalone Analysis Tool

Use the standalone analyzer for detailed CSV analysis:

```bash
# Analyze a CSV file
python csv_analyzer.py your_file.csv

# Analyze with sampling for large files
python csv_analyzer.py your_file.csv --sample 100000

# Export analysis to JSON
python csv_analyzer.py your_file.csv --export analysis.json
```

### Example Output:
```
CSV DATA ANALYSIS SUMMARY
============================================================
File: 8k_filings_raw_text_2024.csv
Size: 3382.24 MB
Rows: 1,000,000
Columns: 10
Memory: 245.67 MB

INSIGHTS:
   SEC Filing Data Detected
   Top Companies: Apple Inc(1250), Microsoft Corp(1180), Amazon.com Inc(980)
   Filing Types: 10-K(45000), 10-Q(35000), 8-K(20000)
   Exchanges: NASDAQ(60000), NYSE(40000)

FILTER RECOMMENDATIONS:
   • Filter filing_date by date range (2024-01-01 to 2024-12-31)
   • Filter filing_type by category
   • Search within raw_text content
```

## Smart Filtering Recommendations

The backend automatically suggests optimal filters based on:

### Data Characteristics
- **High Impact Filters**: Low cardinality columns that significantly reduce dataset
- **Performance Filters**: Numeric columns for fast filtering
- **Business Filters**: Columns relevant to business analysis

### Business Logic Detection
- **SEC Filings**: Detects company names, filing types, exchanges
- **Financial Data**: Identifies revenue, profit, income columns
- **Customer Data**: Recognizes customer, client, user columns
- **Temporal Data**: Finds date/time columns for trend analysis

## Frontend Integration

Update your frontend to use the backend:

```javascript
// Upload file to backend
const formData = new FormData();
formData.append('file', csvFile);

const response = await fetch('http://localhost:5001/api/upload', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log('Analysis:', result.analysis);

// Apply filters
const filterResponse = await fetch('http://localhost:5001/api/filter', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ filters: { search: 'Apple', filing_type: '10-K' } })
});

const filteredData = await filterResponse.json();
console.log('Filtered data:', filteredData.filtered_data);
```

## Performance Features

### Large File Handling
- **Smart Sampling**: Automatically samples large files (>100K rows) for performance
- **Memory Optimization**: Efficient pandas operations
- **Chunked Processing**: Processes data in manageable chunks

### Fast Filtering
- **Indexed Operations**: Uses pandas' optimized filtering
- **Type-Aware Filtering**: Different strategies for different data types
- **Result Limiting**: Limits results to 1000 rows for API responses

## Configuration

### Environment Variables
```bash
export FLASK_ENV=development  # For development
export FLASK_ENV=production  # For production
```

### Customization
Modify `app.py` to:
- Adjust sampling size for large files
- Add custom business logic
- Modify KPI calculations
- Add new filter types

## Example Use Cases

### 1. SEC Filing Analysis
```python
# Filter for specific company filings
filters = {
    "company_name": "Apple Inc",
    "filing_type": "10-K",
    "date_range": "2024-01-01,2024-12-31"
}
```

### 2. Financial Data Mining
```python
# Search for revenue-related content
filters = {
    "search": "revenue growth",
    "filing_type": "10-K"
}
```

### 3. Exchange Analysis
```python
# Analyze specific exchange
filters = {
    "exchange": "NASDAQ",
    "filing_type": ["10-K", "10-Q"]
}
```

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Kill process on port 5001
   lsof -ti:5001 | xargs kill -9
   ```

2. **Memory Issues with Large Files**
   ```bash
   # Use sampling
   python csv_analyzer.py large_file.csv --sample 50000
   ```

3. **Dependencies Issues**
   ```bash
   # Reinstall dependencies
   pip install -r requirements.txt --force-reinstall
   ```

## Dependencies

- **Flask**: Web framework
- **Flask-CORS**: Cross-origin resource sharing
- **pandas**: Data manipulation and analysis
- **numpy**: Numerical computing
- **python-dateutil**: Date parsing utilities

## Ready to Use!

Your Python backend is now ready to handle large CSV files efficiently. It will:

1. **Analyze** your CSV structure automatically
2. **Suggest** optimal filters based on data characteristics  
3. **Process** large files with smart sampling
4. **Generate** business-relevant insights
5. **Export** filtered results for further analysis

Start the backend and upload your 3.4GB CSV file - it will provide intelligent filtering recommendations and fast data processing!


