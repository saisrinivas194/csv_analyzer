# CSV Analyzer Frontend

A React.js application for analyzing large CSV files and extracting key performance indicators (KPIs).

## Features

- **File Upload**: Upload CSV files for analysis
- **KPI Analysis**: Extract key metrics including:
  - Total Customers (Companies)
  - Active Customers (Companies filing recently)
  - Average Order Value (Average filings per company)
  - Activity Rate
  - Revenue Mentions
  - Customer Mentions

- **Data Visualization**: Interactive charts showing:
  - Exchange distribution (pie chart)
  - Top companies by filing count (bar chart)
  - KPI comparison (bar chart)

- **Responsive Design**: Works on desktop and mobile devices

## Technologies Used

- **React.js**: Frontend framework
- **Recharts**: Data visualization library
- **Lucide React**: Icon library
- **CSS3**: Styling with gradients and animations

## Getting Started

### Prerequisites

- Node.js (version 14 or higher)
- npm or yarn

### Installation

1. Navigate to the project directory:
```bash
cd csv-analyzer-frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm start
```

4. Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

## Project Structure

```
src/
├── components/
│   ├── Header.js              # Navigation header
│   ├── FileUpload.js          # File upload component
│   ├── KPIAnalysis.js         # KPI display component
│   ├── DataVisualization.js   # Charts and graphs
│   └── ComponentStyles.css    # Component-specific styles
├── App.js                     # Main application component
├── App.css                    # Global styles
└── index.js                   # Application entry point
```

## Usage

1. **Upload File**: Click "Choose CSV File" to select a CSV file
2. **Analyze**: Click "Analyze File" to process the data
3. **View Results**: Review the KPI metrics and visualizations
4. **Explore Data**: Use the interactive charts to explore patterns

## Key Metrics Explained

- **Total Customers**: Number of unique companies in the dataset
- **Active Customers**: Companies that have filed reports recently (last 30 days)
- **Average Order Value**: Average number of filings per company
- **Activity Rate**: Percentage of companies that are actively filing
- **Revenue Mentions**: Number of filings containing revenue-related terms
- **Customer Mentions**: Number of filings containing customer-related terms

## Customization

The application can be customized by:

- Modifying the color scheme in `App.css`
- Adding new chart types in `DataVisualization.js`
- Extending KPI calculations in `KPIAnalysis.js`
- Adding new file format support in `FileUpload.js`

## Future Enhancements

- Backend API integration for real-time analysis
- Export functionality for reports
- Advanced filtering options
- Real-time data updates
- User authentication and data persistence

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License.# csv_analyzer
