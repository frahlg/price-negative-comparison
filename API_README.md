# Price Production Analysis Flask API

A REST API service for analyzing electricity prices and solar production data with multi-currency support.

## Features

- **Production Analysis**: Upload CSV files with solar production data and analyze against electricity prices
- **Multi-Currency Support**: Get results in SEK, EUR, USD, NOK, DKK, or GBP with automatic conversion
- **Database Integration**: Intelligent caching of ENTSO-E price data with SQLite backend
- **Negative Price Analysis**: Calculate costs during negative electricity price periods
- **Export Value Calculation**: Determine total export value and costs

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

**Parameters:**
- `file` (required): CSV file with production data
- `area` (required): Electricity area code (e.g., "SE_4")
- `currency` (optional): Target currency for results (default: "SEK")
- `start_date` (optional): Analysis start date (YYYY-MM-DD)
- `end_date` (optional): Analysis end date (YYYY-MM-DD)
- `db_path` (optional): Custom database path

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
