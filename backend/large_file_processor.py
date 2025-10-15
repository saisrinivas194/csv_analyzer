from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import os
import tempfile
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)

# Store uploaded files temporarily
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/api/upload-large-file', methods=['POST'])
def upload_large_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save uploaded file
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Process file in chunks for large files
        chunk_size = 10000
        total_rows = 0
        columns = []
        sample_data = []
        
        for chunk in pd.read_csv(filepath, chunksize=chunk_size, low_memory=False):
            total_rows += len(chunk)
            if not columns:
                columns = list(chunk.columns)
                sample_data = chunk.head(100).to_dict('records')
        
        return jsonify({
            'success': True,
            'filename': filename,
            'total_rows': total_rows,
            'columns': columns,
            'sample_data': sample_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/filter-large-data', methods=['POST'])
def filter_large_data():
    try:
        data = request.json
        filename = data.get('filename')
        filters = data.get('filters', {})
        
        if not filename:
            return jsonify({'error': 'No filename provided'}), 400
        
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        # Process filtering in chunks
        chunk_size = 10000
        filtered_count = 0
        sample_results = []
        
        for chunk in pd.read_csv(filepath, chunksize=chunk_size, low_memory=False):
            # Apply filters
            filtered_chunk = apply_filters(chunk, filters)
            filtered_count += len(filtered_chunk)
            
            if not sample_results and len(filtered_chunk) > 0:
                sample_results = filtered_chunk.head(100).to_dict('records')
        
        return jsonify({
            'success': True,
            'filtered_count': filtered_count,
            'sample_results': sample_results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-filtered-data', methods=['POST'])
def export_filtered_data():
    try:
        data = request.json
        filename = data.get('filename')
        filters = data.get('filters', {})
        
        if not filename:
            return jsonify({'error': 'No filename provided'}), 400
        
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        # Process export in chunks
        chunk_size = 10000
        export_filename = f"filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        export_path = os.path.join(UPLOAD_FOLDER, export_filename)
        
        first_chunk = True
        for chunk in pd.read_csv(filepath, chunksize=chunk_size, low_memory=False):
            filtered_chunk = apply_filters(chunk, filters)
            
            if len(filtered_chunk) > 0:
                if first_chunk:
                    filtered_chunk.to_csv(export_path, index=False)
                    first_chunk = False
                else:
                    filtered_chunk.to_csv(export_path, mode='a', header=False, index=False)
        
        return jsonify({
            'success': True,
            'download_url': f'/api/download/{export_filename}',
            'filename': export_filename
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def apply_filters(df, filters):
    """Apply filters to dataframe"""
    filtered_df = df.copy()
    
    if filters.get('search'):
        search_term = filters['search'].lower()
        mask = filtered_df.astype(str).apply(
            lambda x: x.str.lower().str.contains(search_term, na=False)
        ).any(axis=1)
        filtered_df = filtered_df[mask]
    
    if filters.get('company'):
        company_term = filters['company'].lower()
        company_cols = ['company', 'company_name', 'name', 'entity_name']
        mask = False
        for col in company_cols:
            if col in filtered_df.columns:
                mask |= filtered_df[col].astype(str).str.lower().str.contains(company_term, na=False)
        filtered_df = filtered_df[mask]
    
    return filtered_df

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
