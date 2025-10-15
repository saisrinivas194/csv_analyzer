/**
 * FastFileLoader - Memory Efficient Large File Processing
 * 
 * USAGE:
 * const loader = new FastFileLoader({
 *   onProgress: (percent, message) => console.log(`${percent}% - ${message}`),
 *   onError: (error) => console.error(error.message)
 * });
 * 
 * const result = await loader.loadFile(yourFile);
 * console.log('Summary:', loader.getDataSummary());
 */

class FastFileLoader {
  constructor(options = {}) {
    this.chunkSize = options.chunkSize || 1024 * 1024; // 1MB chunks
    this.maxSampleRows = options.maxSampleRows || 10000;
    this.loadAllRows = options.maxSampleRows === Infinity; // Check if we should load all rows
    this.onProgress = options.onProgress || (() => {});
    this.onError = options.onError || (() => {});
    
    this.processedBytes = 0;
    this.totalBytes = 0;
    this.sampleData = [];
    this.allData = []; // Store all data when loading everything
    this.summary = {
      totalRows: 0,
      columns: [],
      fileType: null,
      errors: []
    };
  }

  async loadFile(file) {
    try {
      this.totalBytes = file.size;
      this.processedBytes = 0;
      this.sampleData = [];
      this.summary = {
        totalRows: 0,
        columns: [],
        fileType: this.detectFileType(file.name),
        errors: []
      };

      this.onProgress(0, 'Starting file processing...');

      if (this.summary.fileType === 'csv') {
        await this.processCSVFile(file);
      } else if (this.summary.fileType === 'json') {
        await this.processJSONFile(file);
      } else {
        throw new Error('Unsupported file format. Use CSV or JSON.');
      }

      this.onProgress(100, 'File processing completed');
      
      return {
        success: true,
        summary: this.summary,
        sampleData: this.loadAllRows ? this.allData : this.sampleData,
        totalRows: this.summary.totalRows,
        loadedAllRows: this.loadAllRows
      };

    } catch (error) {
      this.onError(error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  detectFileType(filename) {
    const ext = filename.toLowerCase().split('.').pop();
    if (ext === 'csv') return 'csv';
    if (ext === 'json') return 'json';
    return 'unknown';
  }

  async processCSVFile(file) {
    const reader = new FileReader();
    let buffer = '';
    let headers = null;
    let isFirstChunk = true;

    return new Promise((resolve, reject) => {
      const processChunk = () => {
        const chunk = file.slice(this.processedBytes, this.processedBytes + this.chunkSize);
        
        if (chunk.size === 0) {
          resolve();
          return;
        }

        reader.onload = (e) => {
          try {
            buffer += e.target.result;
            const lines = buffer.split('\n');
            
            // Keep the last incomplete line in buffer
            buffer = lines.pop() || '';

            if (isFirstChunk && lines.length > 0) {
              // Extract headers from first line
              headers = this.parseCSVLine(lines[0]);
              this.summary.columns = headers;
              lines.shift(); // Remove header line
              isFirstChunk = false;
            }

            // Process complete lines
            for (const line of lines) {
              if (line.trim()) {
                this.summary.totalRows++;
                
                const row = this.parseCSVLine(line);
                if (row.length === headers.length) {
                  const rowObj = {};
                  headers.forEach((header, index) => {
                    rowObj[header] = row[index] || '';
                  });
                  
                  if (this.loadAllRows) {
                    // Store ALL rows when loading everything
                    this.allData.push(rowObj);
                  } else {
                    // Add to sample if we haven't reached the limit
                    if (this.sampleData.length < this.maxSampleRows) {
                      this.sampleData.push(rowObj);
                    }
                  }
                }
              }
            }

            this.processedBytes += chunk.size;
            const progress = Math.round((this.processedBytes / this.totalBytes) * 90);
            this.onProgress(progress, `Processing CSV... ${this.summary.totalRows.toLocaleString()} rows`);

            // Continue with next chunk
            setTimeout(processChunk, 10); // Small delay to prevent blocking

          } catch (error) {
            reject(error);
          }
        };

        reader.onerror = () => reject(new Error('Error reading file chunk'));
        reader.readAsText(chunk);
      };

      processChunk();
    });
  }

  async processJSONFile(file) {
    const reader = new FileReader();
    let buffer = '';
    let braceCount = 0;
    let inString = false;
    let escapeNext = false;

    return new Promise((resolve, reject) => {
      const processChunk = () => {
        const chunk = file.slice(this.processedBytes, this.processedBytes + this.chunkSize);
        
        if (chunk.size === 0) {
          resolve();
          return;
        }

        reader.onload = (e) => {
          try {
            buffer += e.target.result;
            
            // Process complete JSON objects
            let i = 0;
            while (i < buffer.length) {
              const char = buffer[i];
              
              if (escapeNext) {
                escapeNext = false;
                i++;
                continue;
              }

              if (char === '\\') {
                escapeNext = true;
                i++;
                continue;
              }

              if (char === '"') {
                inString = !inString;
              } else if (!inString) {
                if (char === '{') {
                  braceCount++;
                } else if (char === '}') {
                  braceCount--;
                  
                  if (braceCount === 0) {
                    // Complete JSON object found
                    const jsonStr = buffer.substring(0, i + 1);
                    buffer = buffer.substring(i + 1);
                    i = 0;
                    
                    try {
                      const obj = JSON.parse(jsonStr);
                      this.summary.totalRows++;
                      
                      // Extract columns from first object
                      if (this.summary.columns.length === 0) {
                        this.summary.columns = Object.keys(obj);
                      }
                      
                      // Add to sample
                      if (this.sampleData.length < this.maxSampleRows) {
                        this.sampleData.push(obj);
                      }
                    } catch (parseError) {
                      this.summary.errors.push(`JSON parse error: ${parseError.message}`);
                    }
                    continue;
                  }
                }
              }
              
              i++;
            }

            this.processedBytes += chunk.size;
            const progress = Math.round((this.processedBytes / this.totalBytes) * 90);
            this.onProgress(progress, `Processing JSON... ${this.summary.totalRows.toLocaleString()} objects`);

            // Continue with next chunk
            setTimeout(processChunk, 10);

          } catch (error) {
            reject(error);
          }
        };

        reader.onerror = () => reject(new Error('Error reading file chunk'));
        reader.readAsText(chunk);
      };

      processChunk();
    });
  }

  parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;
    
    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      
      if (char === '"') {
        if (inQuotes && line[i + 1] === '"') {
          current += '"';
          i++; // Skip next quote
        } else {
          inQuotes = !inQuotes;
        }
      } else if (char === ',' && !inQuotes) {
        result.push(current.trim());
        current = '';
      } else {
        current += char;
      }
    }
    
    result.push(current.trim());
    return result;
  }

  getDataSummary() {
    return {
      fileType: this.summary.fileType,
      totalRows: this.summary.totalRows,
      columns: this.summary.columns,
      sampleSize: this.sampleData.length,
      memoryUsage: this.estimateMemoryUsage(),
      errors: this.summary.errors
    };
  }

  estimateMemoryUsage() {
    const sampleSize = JSON.stringify(this.sampleData).length;
    const estimatedTotal = (sampleSize / this.sampleData.length) * this.summary.totalRows;
    return {
      sampleMB: (sampleSize / 1024 / 1024).toFixed(2),
      estimatedTotalMB: (estimatedTotal / 1024 / 1024).toFixed(2)
    };
  }
}

export default FastFileLoader;