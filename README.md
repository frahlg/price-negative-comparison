# Price Production Analysis System

A comprehensive system for analyzing electricity prices and solar production data with AI-powered CSV format detection.

## 🚀 Features

### Core Analysis
- **Multi-currency electricity price analysis** with automatic exchange rates
- **Solar production data processing** and correlation analysis
- **Negative price detection** and opportunity identification
- **Database management** for electricity prices across Nordic regions

### AI-Powered CSV Detection
- **LLM-powered format detection** using xAI's Grok model
- **Intelligent column recognition** for dates, production, and price data
- **European CSV format support** (semicolon separators, comma decimals)
- **Fallback to traditional parsing** for reliability

### REST API
- **Complete Flask REST API** with 15 endpoints
- **Frontend-ready graph data endpoints** for price visualization
- **File upload and analysis** capabilities  
- **Real-time format detection** with AI or traditional methods
- **Database integration** with price data management

## 📁 Project Structure

```
├── flask_api.py                     # REST API server
├── csv_format_module.py             # AI-powered CSV format detector
├── csv_format_detector_fallback.py # Traditional CSV format detector
├── price_fetcher.py                 # ENTSO-E API integration & database caching
├── production_loader.py             # Solar production data loading
├── price_analyzer.py                # Core analysis engine & statistics
├── cli_analyzer.py                  # Analysis pipeline orchestrator
├── db_manager.py                    # Database management utilities
├── negative_price_analysis.py       # Negative price analysis module
├── main.py                          # CLI interface
├── test_api_client.py               # API testing utilities
├── API_README.md                    # Detailed API documentation
├── pyproject.toml                   # Project dependencies (UV)
├── requirements.txt                 # Pip requirements
└── .env.example                     # Environment configuration template
```

## 🛠️ Installation

### Prerequisites
- Python 3.9+
- UV package manager (recommended) or pip
- **ENTSO-E API key** for electricity price data
- **xAI API key** for AI-powered CSV detection

### Quick Setup with UV
```bash
# Clone the repository
git clone <repository-url>
cd price-negative-comparison

# Install dependencies
uv sync

# Copy environment template
cp .env.example .env
# Edit .env and add your API keys:
# - ENTSOE_API_KEY (get from https://transparency.entsoe.eu/)
# - XAI_API_KEY (get from https://console.x.ai/)

# Run the API server
uv run python flask_api.py
```

### Setup with pip
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your API keys:
# - ENTSOE_API_KEY (get from https://transparency.entsoe.eu/)
# - XAI_API_KEY (get from https://console.x.ai/)
```

## 🔧 Configuration

Create a `.env` file with:
```env
# ENTSO-E API key for electricity price data
ENTSOE_API_KEY=your_entsoe_api_key_here

# xAI API key for AI-powered CSV detection  
XAI_API_KEY=your_xai_api_key_here
```

**Getting API Keys:**
- **ENTSO-E**: Register at [transparency.entsoe.eu](https://transparency.entsoe.eu/usrm/user/createPublicApiKey) 
- **xAI**: Get your key from [console.x.ai](https://console.x.ai/)

## 🚀 Usage

### REST API Server
```bash
# Start the server
python flask_api.py

# Server runs on http://127.0.0.1:5000
```

### API Endpoints
- `GET /health` - Service health check
- `GET /currencies` - List supported currencies
- `GET /database/info` - Database statistics
- `GET /database/areas` - Available price areas
- `POST /detect-csv-format` - AI-powered CSV format detection
- `POST /analyze` - Production data analysis

### CLI Analysis
```bash
# Analyze production data
python main.py --file "production_data.csv" --area SE4

# With specific date range
python main.py --file data.csv --start-date 2024-01-01 --end-date 2024-12-31

# Interactive mode
python main.py --interactive

# Database management
python db_manager.py --help

# Negative price analysis
python negative_price_analysis.py
```

### CSV Format Detection
```bash
# Using the standalone module
python csv_format_module.py --file "your_data.csv"

# Via API
curl -X POST -F "file=@your_data.csv" -F "use_llm=true" \
  http://127.0.0.1:5000/detect-csv-format
```

## 🧠 AI-Powered Features

### CSV Format Detection
The system uses xAI's Grok model to intelligently analyze CSV files and detect:
- Field separators (`,`, `;`, `\t`)
- Decimal separators (`.`, `,`)
- Header detection
- Quote characters
- Encoding format
- Date/time column identification
- Production data column recognition
- European locale support

### Smart Fallback
If AI detection fails, the system automatically falls back to traditional rule-based parsing.

## 📊 Data Sources

- **Electricity Prices**: Nord Pool spot prices via ENTSO-E API
- **Production Data**: Solar panel production logs
- **Exchange Rates**: ECB foreign exchange reference rates
- **Supported Areas**: SE1, SE2, SE3, SE4 (Sweden), NO1-NO5 (Norway), DK1-DK2 (Denmark), FI (Finland)

## 🔍 Analysis Features

### Price Analysis
- Hourly, daily, and monthly statistics
- Multi-currency conversion (EUR, SEK, NOK, DKK)
- Negative price identification
- Price volatility analysis

### Production Correlation
- Production vs. price correlation
- Optimal production timing
- Revenue optimization analysis
- Export opportunity identification

## 📋 API Documentation

See [API_README.md](./API_README.md) for detailed API documentation including:
- Request/response formats
- Authentication requirements
- Error handling
- Example usage

## 🧪 Testing

```bash
# Test API endpoints
python test_api_client.py

# Test CSV detection
python csv_format_module.py --file "test_data.csv"

# Run health check
curl http://127.0.0.1:5000/health
```

## 🛡️ Error Handling

- Comprehensive logging throughout the system
- Graceful fallback for AI services
- Robust file parsing with multiple format detection methods
- Database connection error handling
- API rate limiting and error responses

## 🔒 Security

- Environment-based configuration
- API key protection
- File upload validation
- SQL injection prevention
- Input sanitization

## 📈 Performance

- Efficient database querying with indexes
- Streaming file processing for large datasets
- Caching for exchange rates and price data
- Optimized pandas operations

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Update documentation
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the API documentation
2. Review the error logs
3. Ensure your .env file is properly configured with both API keys
4. Verify your ENTSO-E API key is valid (register at transparency.entsoe.eu)
5. Verify your xAI API key is valid (get from console.x.ai)

## 🔄 Updates

### Recent Features
- ✅ AI-powered CSV format detection with xAI Grok
- ✅ **Enhanced Flask API with 12 endpoints** - complete CLI feature coverage
- ✅ **Database management via API** - clear, export, and manage price data
- ✅ **Advanced analysis endpoints** - daily summaries and negative price focus
- ✅ **CSV export functionality** - download merged analysis data
- ✅ **Built-in API documentation** - interactive docs at `/docs` endpoint
- ✅ Smart fallback parsing system
- ✅ European CSV format support
- ✅ Multi-currency analysis (6 currencies)
- ✅ **Modular architecture** with separated concerns
- ✅ **Frontend-ready API** - complete REST interface for web development

### Roadmap
- [ ] **Web interface for analysis** (ready for development with enhanced API)
- [ ] Real-time price monitoring
- [ ] Advanced forecasting models
- [ ] Additional data source integrations
- [ ] Interactive charts and visualizations