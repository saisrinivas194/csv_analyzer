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

app = Flask(__name__)
CORS(app)

# Global variables to store data
csv_data = None
file_info = None

def analyze_csv_structure(file_path):
    """Analyze CSV structure and provide insights about the data"""
    try:
        # Read first few rows to understand structure (for analysis only)
        sample_df = pd.read_csv(file_path, nrows=1000, low_memory=False)
        
        analysis = {
            'total_rows': 0,
            'columns': list(sample_df.columns),
            'column_types': {},
            'sample_data': sample_df.head(5).to_dict('records'),
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
            analysis['unique_values'][col] = unique_vals[:20].tolist()
            
            # Generate insights based on column name and content
            insights = generate_column_insights(col, sample_df[col])
            analysis['data_insights'].extend(insights)
        
        # Get total row count efficiently
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                analysis['total_rows'] = sum(1 for line in f) - 1  # Subtract header
        except:
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
    if series.dtype == 'object' and series.nunique() < 50:
        top_values = series.value_counts().head(3)
        insights.append(f"Top values: {column_name} top values: {', '.join([f'{k}({v})' for k, v in top_values.items()])}")
    
    return insights

def filter_data(filters):
    """Apply filters to the CSV data"""
    global csv_data
    
    if csv_data is None:
        return None
    
    try:
        filtered_df = csv_data.copy()
        
        # Apply text search filter
        if filters.get('search'):
            search_term = filters['search'].lower()
            text_columns = filtered_df.select_dtypes(include=['object']).columns
            
            mask = pd.Series([False] * len(filtered_df))
            for col in text_columns:
                mask |= filtered_df[col].astype(str).str.lower().str.contains(search_term, na=False)
            
            filtered_df = filtered_df[mask]
        
        # Apply column-specific filters
        for column, value in filters.items():
            if column != 'search' and value and value != 'all':
                if column in filtered_df.columns:
                    if filtered_df[column].dtype == 'object':
                        filtered_df = filtered_df[filtered_df[column].astype(str).str.contains(str(value), case=False, na=False)]
                    else:
                        filtered_df = filtered_df[filtered_df[column] == value]
        
        return filtered_df
        
    except Exception as e:
        logger.error(f"Error filtering data: {str(e)}")
        return None

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
            
            # For display and initial analysis, use sampling for performance
            csv_data = pd.read_csv(file_path, low_memory=False)
            
            # For very large files, sample for display but keep full file path for search
            if len(csv_data) > 100000:
                csv_data_sample = csv_data.sample(n=100000, random_state=42)
                analysis['total_rows'] = len(csv_data)  # Show actual total
                analysis['sample_rows'] = len(csv_data_sample)  # Show sample size
                analysis['data_insights'].append(f"Display sample: {len(csv_data_sample):,} rows | Full dataset: {len(csv_data):,} rows")
                
                # Store both sample and full file path
                csv_data = csv_data_sample
                file_info['full_file_path'] = file_path
                file_info['is_sampled'] = True
            else:
                analysis['total_rows'] = len(csv_data)
                analysis['data_insights'].append(f"Full dataset loaded: {len(csv_data):,} rows")
                file_info['is_sampled'] = False
            
            logger.info(f"Successfully loaded {len(csv_data):,} rows for display")
            
        except Exception as e:
            logger.error(f"Error loading CSV: {str(e)}")
            return jsonify({'error': f'Error loading CSV: {str(e)}'}), 500
        
        file_info = {
            'filename': file.filename,
            'upload_time': datetime.now().isoformat(),
            'file_size': os.path.getsize(file_path)
        }
        
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
    """Apply filters to the data"""
    try:
        filters = request.json.get('filters', {})
        
        filtered_df = filter_data(filters)
        if filtered_df is None:
            return jsonify({'error': 'No data available'}), 400
        
        # Convert to records for JSON response
        result = {
            'filtered_data': filtered_df.head(1000).to_dict('records'),  # Limit to 1000 rows
            'total_filtered_rows': len(filtered_df),
            'columns': list(filtered_df.columns),
            'kpis': generate_kpis(filtered_df)
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Filter error: {str(e)}")
        return jsonify({'error': f'Filter failed: {str(e)}'}), 500

@app.route('/api/export', methods=['POST'])
def export_data():
    """Export filtered data as CSV"""
    try:
        filters = request.json.get('filters', {})
        
        filtered_df = filter_data(filters)
        if filtered_df is None:
            return jsonify({'error': 'No data available'}), 400
        
        # Create CSV in memory
        output = io.StringIO()
        filtered_df.to_csv(output, index=False)
        output.seek(0)
        
        # Create file response
        filename = f"filtered_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
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
            elif csv_data[col].dtype == 'object' and csv_data[col].nunique() < 50:
                insights['recommendations'].append(f"Filter by {col} to focus on specific categories")
                insights['filter_suggestions'].append({
                    'column': col,
                    'type': 'dropdown',
                    'options': csv_data[col].value_counts().head(10).index.tolist(),
                    'description': f'Filter {col} by category'
                })
            
            # Text column recommendations
            elif csv_data[col].dtype == 'object':
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
        text_columns = search_data.select_dtypes(include=['object']).columns
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
            'search_results': matching_rows.to_dict('records'),
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
        text_columns = search_data.select_dtypes(include=['object']).columns
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
        text_cols = analysis_data.select_dtypes(include=['object']).columns
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