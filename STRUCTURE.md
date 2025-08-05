# Project Structure

```
price-negative-comparison/
├── README.md                   # Main project documentation
├── LICENSE                     # Project license
├── requirements.txt            # Python dependencies
├── pyproject.toml             # Project configuration
├── app.py                     # Main Flask web application
│
├── core/                      # Core business logic
│   ├── __init__.py
│   ├── price_analyzer.py      # Price analysis algorithms
│   ├── price_fetcher.py       # ENTSO-E API integration
│   ├── production_loader.py   # Production data loading
│   ├── db_manager.py          # Database operations
│   ├── negative_price_analysis.py
│   └── price_production_analyzer.py
│
├── utils/                     # Utility functions
│   ├── __init__.py
│   ├── csv_format_detector_fallback.py  # Traditional CSV detection
│   └── csv_format_module.py             # AI-powered CSV detection
│
├── cli/                       # Command line tools
│   ├── __init__.py
│   ├── cli_analyzer.py        # CLI analysis tool
│   └── main.py               # Legacy main script
│
├── data/                      # Data storage
│   ├── price_data.db         # SQLite database (price data)
│   └── samples/              # Sample data files
│       └── Produktion - Solvägen 33a.csv
│
├── templates/                 # Web interface templates
│   └── index.html            # Main web page
│
├── static/                    # Static web assets
│   ├── css/
│   │   └── custom.css        # Custom styles
│   └── js/
│       └── main.js           # Frontend JavaScript
│
├── docs/                      # Documentation
│   ├── API_README.md         # API documentation
│   └── ARCHITECTURE.md       # Architecture documentation
│
└── tests/                     # Test files
    └── test_api_client.py     # API testing client
```

## Key Directories

- **`core/`** - Contains the main business logic and analysis algorithms
- **`utils/`** - Helper utilities and support functions
- **`cli/`** - Command-line interface tools
- **`data/`** - All data files including database and samples
- **`templates/`** - Flask/Jinja2 HTML templates
- **`static/`** - CSS, JavaScript, and other static web assets
- **`docs/`** - Project documentation
- **`tests/`** - Test files and utilities

## Security Note

The database path is hardcoded to `data/price_data.db` for security. No user input can specify alternative database locations.
