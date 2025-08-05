# Price Production Analysis Flask API

A comprehensive REST API service for analyzing electricity prices and solar production data with multi-currency support and advanced features.

## Features

- **Production Analysis**: Upload CSV files with solar production data and analyze against electricity prices
- **Multi-Currency Support**: Get results in SEK, EUR, USD, NOK, DKK, or GBP with automatic conversion
- **Database Integration**: Intelligent caching of ENTSO-E price data with SQLite backend
- **Negative Price Analysis**: Calculate costs during negative electricity price periods with detailed breakdown
- **Daily Summary Analysis**: Get day-by-day breakdown statistics
- **Export Value Calculation**: Determine total export value and costs
- **Database Management**: Clear, export, and manage price data via API
- **CSV Export**: Download merged analysis data as CSV files
- **AI-Powered CSV Detection**: Intelligent format detection with fallback parsing
- **API Documentation**: Built-in documentation endpoint

## Quick Start

1. **Set up environment (optional for graph endpoints):**
   ```bash
   # Create .env file for production analysis endpoints
   echo "ENTSOE_API_KEY=your_api_key_here" > .env
   # Get your API key from: https://transparency.entsoe.eu/usrm/user/createPublicApiKey
   ```

2. **Start the API server:**
   ```bash
   python flask_api.py
   ```

3. **View API documentation:**
   ```bash
   curl http://127.0.0.1:5000/docs
   # or visit http://127.0.0.1:5000/docs in your browser
   ```

4. **Test with the included client:**
   ```bash
   python test_api_client.py
   ```

## API Endpoints Summary

The API now includes **14 endpoints** covering all CLI functionality plus specialized graph data for frontend development:

- **GET /health** - Health check
- **GET /currencies** - List supported currencies
- **GET /database/info** - Database statistics
- **GET /database/areas** - List price areas
- **DELETE /database/clear** - Clear database data
- **GET /database/export** - Export database as CSV
- **POST /detect-csv-format** - AI CSV format detection
- **POST /analyze** - Full production analysis
- **POST /analyze/daily-summary** - Daily breakdown
- **POST /analyze/negative-prices** - Negative price focus
- **POST /analyze/export** - Export analysis as CSV
- **GET /docs** - API documentation
- **GET /graph/price-timeline** - Price timeline for charts (NEW)
- **GET /graph/price-distribution** - Price histogram data (NEW)
- **GET /graph/negative-price-periods** - Negative price visualization (NEW)

## Frontend Development Ready

✅ **Complete Feature Coverage**: All CLI features now available via REST API  
✅ **Database Management**: Full CRUD operations on price data  
✅ **Multiple Analysis Types**: Basic, daily summary, and negative price analysis  
✅ **Data Export**: Download analysis results as CSV files  
✅ **Built-in Documentation**: Interactive API docs at `/docs` endpoint  
✅ **Multi-Currency Support**: 6 currencies with automatic conversion  
✅ **File Upload**: Drag-and-drop ready CSV processing  
✅ **Error Handling**: Proper HTTP status codes and messages  
✅ **Graph Data Endpoints**: 3 specialized endpoints for chart visualization (NEW)

## 🚀 **Ready to Use NOW** (No Setup Required)

The following endpoints work immediately with existing database data:

- **All Graph Endpoints**: `/graph/price-timeline`, `/graph/price-distribution`, `/graph/negative-price-periods`
- **Database Endpoints**: `/database/info`, `/database/areas`, `/database/export`
- **Utility Endpoints**: `/health`, `/currencies`, `/docs`
- **CSV Detection**: `/detect-csv-format`

## ⚙️ **Requires ENTSO-E API Key**

These endpoints need an API key configured in the server's environment:
- `/analyze` - Production data analysis
- `/analyze/daily-summary` - Daily breakdown analysis  
- `/analyze/negative-prices` - Negative price analysis

**Server Configuration:**
```bash
# Add to .env file in project directory:
ENTSOE_API_KEY=your_api_key_here
```  

## New Enhanced Features

### Database Management
- **Clear Data**: Remove price data for specific areas or all data
- **Export Data**: Download raw price data as CSV  
- **Advanced Stats**: Per-area statistics and date ranges

### Advanced Analysis
- **Daily Summaries**: Day-by-day breakdown of production and prices
- **Negative Price Focus**: Dedicated analysis for negative pricing periods
- **Cost Breakdown**: Monthly and daily cost analysis
- **Top Expensive Hours**: Identify most costly periods

### Data Export & Integration  
- **CSV Export**: Download complete merged analysis data
- **Currency Conversion**: Export in any supported currency
- **API Documentation**: Built-in JSON docs via `/docs` endpoint

## Recommended Frontend Stack

- **Framework**: React, Vue.js, or Angular for interactive dashboards
- **Charts**: Chart.js or D3.js for price/production visualization  
- **HTTP Client**: Axios or Fetch API for backend communication
- **File Upload**: React-Dropzone or similar for CSV uploads
- **UI Components**: Material-UI, Ant Design, or Tailwind CSS

## Quick Frontend Example

```javascript
// Upload and analyze production data
const analyzeProduction = async (file, area, currency) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('area', area);
  formData.append('currency', currency);
  
  const response = await fetch('/analyze', {
    method: 'POST',
    body: formData
  });
  
  return await response.json();
};

// Get API documentation
const getApiDocs = async () => {
  const response = await fetch('/docs');
  return await response.json();
};
```

For complete API documentation, see the detailed endpoint descriptions below or visit `/docs` when the server is running.

## Quick Start

1. **Start the API server:**
   ```bash
   python flask_api.py
   ```

2. **Test with the included client:**
   ```bash
   python test_api_client.py
   ```

## API Endpoints

### GET /health
Health check endpoint.

**Response:**
```json
{
  "service": "Price Production Analysis API",
  "status": "healthy",
  "version": "1.0.0"
}
```

### GET /currencies
List supported currencies and exchange rates.

**Response:**
```json
{
  "default": "SEK",
  "supported_currencies": ["EUR", "SEK", "USD", "NOK", "DKK", "GBP"],
  "rates": {
    "EUR": 1.0,
    "SEK": 11.5,
    "USD": 1.1,
    "NOK": 12.0,
    "DKK": 7.4,
    "GBP": 0.85
  }
}
```

### GET /database/info
Get information about the price database.

**Response:**
```json
{
  "total_records": 5833,
  "areas_count": 2,
  "date_range": {
    "start": "2025-01-01T00:00:00",
    "end": "2025-08-03T00:00:00"
  },
  "areas": [
    {
      "area_code": "SE_4",
      "records": 5136,
      "date_range": {...},
      "price_range_eur_mwh": {...}
    }
  ]
}
```

### GET /database/areas
List available electricity price areas.

**Response:**
```json
{
  "areas": ["SE_1", "SE_4"]
}
```

### POST /analyze
Analyze production data against electricity prices.

**⚠️ Note**: This endpoint requires an ENTSO-E API key to be configured in the server's environment variables (`.env` file or `ENTSOE_API_KEY` environment variable). If you're only working with existing database data, use the graph endpoints instead.

**Parameters:**
- `file` (required): CSV file with production data
- `area` (required): Electricity area code (e.g., "SE_4")
- `currency` (optional): Target currency for results (default: "SEK")
- `start_date` (optional): Analysis start date (YYYY-MM-DD)
- `end_date` (optional): Analysis end date (YYYY-MM-DD)
- `db_path` (optional): Custom database path

**Server Setup (one-time):**
```bash
# Option 1: Create .env file in the project directory
echo "ENTSOE_API_KEY=your_api_key_here" > .env

# Option 2: Set environment variable
export ENTSOE_API_KEY="your_api_key_here"

# Get your API key from: https://transparency.entsoe.eu/usrm/user/createPublicApiKey
```

**Example Request:**
```bash
curl -X POST \
  -F "file=@production.csv" \
  -F "area=SE_4" \
  -F "currency=SEK" \
  -F "start_date=2025-06-01" \
  -F "end_date=2025-06-30" \
  http://127.0.0.1:5000/analyze
```

**Response:**
```json
{
  "analysis": {
    "period": {
      "days": 29,
      "hours": 697,
      "start": "2025-06-01T00:00:00",
      "end": "2025-06-30T00:00:00"
    },
    "prices": {
      "currency": "SEK",
      "min": {
        "value": -0.29095,
        "unit": "SEK/kWh",
        "display": "-0.2909 SEK/kWh",
        "reference": "-25.30 EUR/MWh"
      },
      "max": {
        "value": 2.43524,
        "unit": "SEK/kWh",
        "display": "2.4352 SEK/kWh",
        "reference": "211.76 EUR/MWh"
      },
      "mean": {...},
      "median": {...}
    },
    "production": {
      "total_kwh": 877.94,
      "average_hourly_kwh": 1.26,
      "max_hourly_kwh": 6.328,
      "hours_with_production": 482
    },
    "negative_prices": {
      "hours_count": 85,
      "production_kwh": 270.28,
      "average_production_kwh": 3.18,
      "total_cost": {
        "value": 17.62,
        "currency": "SEK"
      }
    },
    "export_value": {
      "total": {
        "value": 131.43,
        "currency": "SEK"
      },
      "positive_prices": {
        "value": 149.05,
        "currency": "SEK"
      }
    }
  },
  "metadata": {
    "area_code": "SE_4",
    "currency": "SEK",
    "exchange_rate_eur": 11.5,
    "file_processed": "production.csv",
    "database_records_used": 697
  }
}
```

## Production CSV Format

The API supports CSV files with production data in the following formats:

**European Format (semicolon separator):**
```csv
Datum;Produktion kWh
2025-06-01 00:00;0.0
2025-06-01 01:00;0.0
2025-06-01 02:00;0.0
```

**US Format (comma separator):**
```csv
Date,Production kWh
2025-06-01 00:00,0.0
2025-06-01 01:00,0.0
2025-06-01 02:00,0.0
```

The API automatically detects the format and column names.

## Graph Data Endpoints (Frontend Development)

The API provides specialized endpoints for frontend chart visualization:

### Price Timeline (`GET /graph/price-timeline`)

Get price data in timeline format optimized for charts:

```bash
curl "http://localhost:5000/graph/price-timeline?area=SE_4&start_date=2025-01-01&end_date=2025-01-07&currency=EUR&resolution=hourly"
```

**Parameters:**
- `area` (required): Electricity area code (e.g., SE_4)
- `start_date` (optional): Start date YYYY-MM-DD
- `end_date` (optional): End date YYYY-MM-DD  
- `currency` (optional): Target currency, default EUR
- `resolution` (optional): hourly/daily/weekly, default hourly

**Response:** Timeline array with timestamps, prices, and negative price indicators.

### Price Distribution (`GET /graph/price-distribution`)

Get histogram data for price distribution visualization:

```bash
curl "http://localhost:5000/graph/price-distribution?area=SE_4&start_date=2025-01-01&end_date=2025-01-31&currency=EUR&bins=20"
```

**Parameters:**
- `area` (required): Electricity area code
- `start_date` (optional): Start date YYYY-MM-DD
- `end_date` (optional): End date YYYY-MM-DD
- `currency` (optional): Target currency, default EUR
- `bins` (optional): Number of histogram bins, default 50

**Response:** Distribution array with bin ranges, counts, and percentages.

### Negative Price Periods (`GET /graph/negative-price-periods`)

Get detailed negative price periods for visualization:

```bash
curl "http://localhost:5000/graph/negative-price-periods?area=SE_1&start_date=2025-06-01&end_date=2025-06-30&currency=EUR"
```

**Parameters:**
- `area` (required): Electricity area code
- `start_date` (optional): Start date YYYY-MM-DD
- `end_date` (optional): End date YYYY-MM-DD
- `currency` (optional): Target currency, default EUR

**Response:** Array of negative price periods with duration, min/avg prices, and hourly breakdowns.

### JavaScript Example

```javascript
// Fetch price timeline for chart
const response = await fetch('/graph/price-timeline?area=SE_4&resolution=daily&currency=EUR');
const data = await response.json();

// Use with Chart.js or similar
const chartData = {
    labels: data.timeline.map(point => point.timestamp),
    datasets: [{
        label: 'Price (EUR/MWh)',
        data: data.timeline.map(point => point.price),
        backgroundColor: data.timeline.map(point => 
            point.is_negative ? 'rgba(255, 99, 132, 0.5)' : 'rgba(54, 162, 235, 0.5)'
        )
    }]
};
```

## Currency Conversion

All prices are stored in the database as EUR/MWh (ENTSO-E standard) and converted for display:

- **Database Storage**: EUR/MWh
- **User Interface**: Converted to local currency per kWh
- **Supported Currencies**: EUR, SEK, USD, NOK, DKK, GBP
- **Exchange Rates**: Configurable in the API code

## Error Handling

The API returns appropriate HTTP status codes and error messages:

- `400 Bad Request`: Invalid input parameters
- `404 Not Found`: Endpoint or resource not found
- `413 Request Entity Too Large`: File size exceeds 16MB limit
- `500 Internal Server Error`: Server processing error

## Dependencies

- Flask 3.1.1
- Werkzeug 3.1.3
- Pandas (for data processing)
- NumPy (for numerical operations)
- price_production_analyzer.py (core analysis logic)

## Development

The API runs in development mode by default. For production deployment, use a proper WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 flask_api:app
```

## Testing

Use the included test client to verify all endpoints:

```bash
python test_api_client.py
```

The test client will verify:
- Health check endpoint
- Currency listing
- Database information
- Production data analysis with multiple currencies

## License

This API is part of the price-negative-comparison project.
