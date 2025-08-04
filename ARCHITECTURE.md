# Architecture Documentation

## Overview

The Price Production Analysis System follows a modular architecture with clear separation of concerns. This design makes the codebase maintainable, testable, and easy to extend.

## Core Modules

### Data Layer
- **`price_fetcher.py`** - Handles ENTSO-E API integration and database caching
  - `PriceFetcher`: Main class for fetching price data
  - `PriceDatabase`: SQLite database operations
  - Smart caching to avoid redundant API calls

- **`production_loader.py`** - Loads and processes solar production CSV files
  - `ProductionLoader`: Auto-detects CSV format and columns
  - Supports European CSV formats (semicolon separators, comma decimals)

### Analysis Layer
- **`price_analyzer.py`** - Core analysis engine
  - `PriceAnalyzer`: Merges data and performs statistical analysis
  - Calculates correlations, negative price impacts, export values
  - Multi-currency support with exchange rate conversion

### Interface Layer
- **`cli_analyzer.py`** - Analysis pipeline orchestrator
  - `AnalysisPipeline`: Coordinates all components for complete analysis
  - Handles date range logic and data flow

- **`flask_api.py`** - REST API server
  - 6 endpoints for web-based analysis
  - File upload and real-time processing
  - JSON responses with comprehensive error handling

- **`main.py`** - Command-line interface
  - User-friendly CLI with interactive mode
  - Support for various analysis options

### AI & Detection
- **`csv_format_module.py`** - AI-powered CSV format detection
  - Uses xAI Grok for intelligent format analysis
  - European locale support

- **`csv_format_detector_fallback.py`** - Traditional CSV detection
  - Rule-based fallback system
  - Robust parsing for various formats

### Utilities
- **`db_manager.py`** - Database management utilities
- **`negative_price_analysis.py`** - Specialized negative price analysis

## Data Flow

```
┌─────────────────┐    ┌──────────────────┐    ┌────────────────┐
│   CSV File      │───▶│ ProductionLoader │───▶│  Production    │
└─────────────────┘    └──────────────────┘    │      Data      │
                                               └────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌────────────────┐
│  ENTSO-E API    │───▶│   PriceFetcher   │───▶│   Price Data   │
└─────────────────┘    └──────────────────┘    └────────────────┘
                              │                          │
                              ▼                          │
                    ┌──────────────────┐                 │
                    │ SQLite Database  │                 │
                    │    (Caching)     │                 │
                    └──────────────────┘                 │
                                                        │
                                                        ▼
                              ┌────────────────────────────────┐
                              │        PriceAnalyzer           │
                              │    (Merge & Analyze Data)      │
                              └────────────────────────────────┘
                                               │
                                               ▼
                              ┌────────────────────────────────┐
                              │      Analysis Results          │
                              │   (Statistics, Insights)      │
                              └────────────────────────────────┘
```

## Benefits of Modular Design

### 1. **Single Responsibility Principle**
- Each module has one clear purpose
- Easy to understand and maintain
- Reduced coupling between components

### 2. **Testability**
- Components can be tested in isolation
- Mock dependencies for unit testing
- Clear interfaces between modules

### 3. **Reusability**
- Components can be used independently
- Easy to create new analysis tools
- API and CLI share the same core logic

### 4. **Extensibility**
- Add new data sources by implementing similar fetchers
- New analysis types by extending PriceAnalyzer
- Additional interfaces (web UI) by using existing components

### 5. **Maintainability**
- Bugs are isolated to specific modules
- Updates to one component don't affect others
- Clear code organization

## Usage Patterns

### Programmatic Usage
```python
from price_fetcher import PriceFetcher
from production_loader import ProductionLoader
from price_analyzer import PriceAnalyzer

# Initialize components
fetcher = PriceFetcher()
loader = ProductionLoader()
analyzer = PriceAnalyzer()

# Load data
production_df = loader.load_production_data("data.csv")
prices_df = fetcher.get_price_data("SE_4", start_date, end_date)

# Analyze
merged_df = analyzer.merge_data(prices_df, production_df)
results = analyzer.analyze_data(merged_df)
```

### Pipeline Usage
```python
from cli_analyzer import AnalysisPipeline

pipeline = AnalysisPipeline()
merged_df, analysis = pipeline.run_analysis(
    production_file="data.csv",
    area_code="SE_4"
)
```

This architecture provides a solid foundation for future enhancements while maintaining simplicity and clarity.
