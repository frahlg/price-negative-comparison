#!/usr/bin/env python3
"""
Price Production Analysis Flask API

A REST API service for analyzing electricity prices and solar production data.

Usage:
    python flask_api.py

Endpoints:
    POST /analyze - Analyze production data against electricity prices
    GET /health - Health check
    GET /database/info - Database information
    GET /database/areas - List available areas
"""

from flask import Flask, request, jsonify, make_response
import pandas as pd
import tempfile
import os
import json
import numpy as np
from datetime import datetime, date
from pathlib import Path
from csv_format_detector_fallback import CSVFormatDetectorFallback
from csv_format_module import CSVFormatDetector
from dotenv import load_dotenv
import logging
from werkzeug.utils import secure_filename
from price_fetcher import PriceFetcher
from production_loader import ProductionLoader
from price_analyzer import PriceAnalyzer
from db_manager import PriceDatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NumpyJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles NumPy and Pandas data types."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

app = Flask(__name__)

# Load environment variables
load_dotenv()

def safe_jsonify(data, status_code=200):
    """Custom jsonify function that handles NumPy/Pandas data types."""
    try:
        json_str = json.dumps(data, cls=NumpyJSONEncoder, ensure_ascii=False)
        response = make_response(json_str, status_code)
        response.headers['Content-Type'] = 'application/json'
        return response
    except TypeError as e:
        logger.error(f"JSON serialization error: {e}")
        error_response = make_response(json.dumps({'error': 'Data serialization error'}), 500)
        error_response.headers['Content-Type'] = 'application/json'
        return error_response
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Currency conversion rates (base: EUR)
CURRENCY_RATES = {
    'EUR': 1.0,
    'SEK': 11.5,
    'USD': 1.1,
    'NOK': 12.0,
    'DKK': 7.4,
    'GBP': 0.85
}

ALLOWED_EXTENSIONS = {'csv', 'txt'}

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_currency_rate(currency):
    """Get exchange rate for currency."""
    currency = currency.upper()
    if currency not in CURRENCY_RATES:
        raise ValueError(f"Unsupported currency: {currency}. Supported: {', '.join(CURRENCY_RATES.keys())}")
    return CURRENCY_RATES[currency]

def format_price_with_currency(price_eur_mwh, currency, rate):
    """Format price in the requested currency and appropriate units."""
    if currency == 'EUR':
        return f"{price_eur_mwh:.2f} EUR/MWh"
    else:
        # Convert to local currency per kWh for user-friendly display
        price_local_kwh = (price_eur_mwh * rate) / 1000
        return f"{price_local_kwh:.4f} {currency}/kWh"

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'Price Production Analysis API',
        'version': '1.0.0'
    })

@app.route('/currencies', methods=['GET'])
def get_supported_currencies():
    """Get list of supported currencies."""
    return jsonify({
        'supported_currencies': list(CURRENCY_RATES.keys()),
        'default': 'SEK',
        'rates': CURRENCY_RATES
    })

@app.route('/database/info', methods=['GET'])
def database_info():
    """Get database information."""
    try:
        db_path = request.args.get('db_path', 'price_data.db')
        manager = PriceDatabaseManager(db_path)
        
        if not Path(db_path).exists():
            return jsonify({'error': 'Database does not exist'}), 404
        
        # Get basic database info
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            total_records = conn.execute('SELECT COUNT(*) FROM price_data').fetchone()[0]
            areas = conn.execute('SELECT DISTINCT area_code FROM price_data ORDER BY area_code').fetchall()
            date_range = conn.execute('SELECT MIN(datetime), MAX(datetime) FROM price_data').fetchone()
            
            # Per-area statistics
            area_stats = []
            for (area,) in areas:
                area_info = conn.execute('''
                    SELECT COUNT(*), MIN(datetime), MAX(datetime), 
                           MIN(price_eur_per_mwh), MAX(price_eur_per_mwh), AVG(price_eur_per_mwh)
                    FROM price_data 
                    WHERE area_code = ?
                ''', (area,)).fetchone()
                
                area_stats.append({
                    'area_code': area,
                    'records': area_info[0],
                    'date_range': {
                        'start': area_info[1],
                        'end': area_info[2]
                    },
                    'price_range_eur_mwh': {
                        'min': area_info[3],
                        'max': area_info[4],
                        'avg': area_info[5]
                    }
                })
        
        return jsonify({
            'database_path': db_path,
            'total_records': total_records,
            'areas_count': len(areas),
            'date_range': {
                'start': date_range[0],
                'end': date_range[1]
            } if date_range[0] else None,
            'areas': area_stats
        })
        
    except Exception as e:
        logger.error(f"Database info error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/database/areas', methods=['GET'])
def list_areas():
    """List available areas in the database."""
    try:
        db_path = request.args.get('db_path', 'price_data.db')
        
        if not Path(db_path).exists():
            return jsonify({'areas': []})
        
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            areas = conn.execute('SELECT DISTINCT area_code FROM price_data ORDER BY area_code').fetchall()
        
        return jsonify({
            'areas': [area[0] for area in areas]
        })
        
    except Exception as e:
        logger.error(f"List areas error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/detect-csv-format', methods=['POST'])
def detect_csv_format():
    """Detect CSV format for uploaded file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.csv'):
        return jsonify({'error': 'Invalid file type. Only CSV files allowed'}), 400
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(mode='w+b', suffix='.csv', delete=False) as temp_file:
        file.save(temp_file.name)
        temp_filename = temp_file.name
    
    try:
        # Try LLM-powered detection first
        use_llm = request.form.get('use_llm', 'true').lower() == 'true'
        
        if use_llm:
            try:
                logger.info("Attempting LLM-powered CSV format detection")
                llm_detector = CSVFormatDetector()
                params = llm_detector.detect_format(temp_filename)
                
                # Test load a few rows to validate
                df_sample = pd.read_csv(temp_filename, nrows=5, **params)
                
                response = {
                    'status': 'success',
                    'detection_method': 'llm',
                    'detected_format': params,
                    'pandas_params': params,
                    'sample_data': {
                        'columns': list(df_sample.columns),
                        'rows': df_sample.head().to_dict('records'),
                        'shape': {'rows': len(df_sample), 'columns': len(df_sample.columns)}
                    },
                    'recommendations': {
                        'pandas_params': params,
                        'notes': 'Format detected using AI analysis. Use these parameters with pd.read_csv() to load the file'
                    }
                }
                
                return safe_jsonify(response)
                
            except Exception as llm_error:
                logger.warning(f"LLM detection failed, falling back to traditional method: {llm_error}")
        
        # Fallback to traditional detection
        logger.info("Using traditional CSV format detection")
        detector = CSVFormatDetectorFallback()
        params = detector.detect_format(temp_filename)
        
        # Test load a few rows to validate
        df_sample = pd.read_csv(temp_filename, nrows=5, **params)
        
        response = {
            'status': 'success',
            'detection_method': 'traditional',
            'detected_format': params,
            'pandas_params': params,
            'sample_data': {
                'columns': list(df_sample.columns),
                'rows': df_sample.head().to_dict('records'),
                'shape': {'rows': len(df_sample), 'columns': len(df_sample.columns)}
            },
            'recommendations': {
                'pandas_params': params,
                'notes': 'Format detected using traditional parsing. Use these parameters with pd.read_csv() to load the file'
            }
        }
        
        return safe_jsonify(response)
        
    except Exception as e:
        logger.error(f"CSV format detection failed: {e}")
        return jsonify({'error': f'Format detection failed: {str(e)}'}), 500
    
    finally:
        # Clean up temporary file
        try:
            os.unlink(temp_filename)
        except:
            pass

@app.route('/analyze', methods=['POST'])
def analyze_production():
    """
    Analyze production data against electricity prices.
    
    Expected form data:
    - file: CSV file with production data
    - area: Electricity area code (e.g., SE_4)
    - currency: Currency for display (optional, default: SEK)
    - start_date: Start date YYYY-MM-DD (optional)
    - end_date: End date YYYY-MM-DD (optional)
    - db_path: Database path (optional, default: price_data.db)
    """
    try:
        # Validate request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only CSV files allowed'}), 400
        
        # Get parameters
        area = request.form.get('area')
        if not area:
            return jsonify({'error': 'Area code is required'}), 400
        
        currency = request.form.get('currency', 'SEK').upper()
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        db_path = request.form.get('db_path', 'price_data.db')
        
        # Validate currency
        try:
            currency_rate = get_currency_rate(currency)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.csv', delete=False) as temp_file:
            file.save(temp_file.name)
            temp_filename = temp_file.name
        
        try:
            # Create components and run analysis
            price_fetcher = PriceFetcher(db_path=db_path)
            production_loader = ProductionLoader()
            analyzer = PriceAnalyzer()
            
            # Load production data
            production_df = production_loader.load_production_data(temp_filename)
            
            # Determine date range
            production_start = pd.Timestamp(production_df.index.min(), tz='Europe/Stockholm')
            production_end = pd.Timestamp(production_df.index.max(), tz='Europe/Stockholm')
            
            if start_date:
                start_date = pd.Timestamp(start_date, tz='Europe/Stockholm')
                if start_date > production_start:
                    production_df = production_df[production_df.index >= start_date.tz_localize(None)]
            else:
                start_date = production_start
                
            if end_date:
                end_date = pd.Timestamp(end_date, tz='Europe/Stockholm')
                if end_date < production_end:
                    production_df = production_df[production_df.index <= end_date.tz_localize(None)]
            else:
                end_date = production_end
            
            # Get price data
            prices_df = price_fetcher.get_price_data(area, start_date, end_date)
            
            # Merge and analyze
            merged_df = analyzer.merge_data(prices_df, production_df, currency_rate)
            analysis = analyzer.analyze_data(merged_df)
            
            # Format response with appropriate currency
            def format_price_response(price_eur_mwh):
                if currency == 'EUR':
                    return {
                        'value': price_eur_mwh,
                        'unit': 'EUR/MWh',
                        'display': f"{price_eur_mwh:.2f} EUR/MWh"
                    }
                else:
                    price_local_kwh = (price_eur_mwh * currency_rate) / 1000
                    return {
                        'value': price_local_kwh,
                        'unit': f'{currency}/kWh',
                        'display': f"{price_local_kwh:.4f} {currency}/kWh",
                        'reference': f"{price_eur_mwh:.2f} EUR/MWh"
                    }
            
            # Build response with data type conversion
            response = {
                'analysis': {
                    'period': {
                        'days': int(analysis['period_days']),
                        'hours': int(analysis['total_hours']),
                        'start': merged_df.index.min().isoformat(),
                        'end': merged_df.index.max().isoformat()
                    },
                    'prices': {
                        'currency': currency,
                        'min': format_price_response(float(analysis['price_min_eur_mwh'])),
                        'max': format_price_response(float(analysis['price_max_eur_mwh'])),
                        'mean': format_price_response(float(analysis['price_mean_eur_mwh'])),
                        'median': format_price_response(float(analysis['price_median_eur_mwh']))
                    },
                    'production': {
                        'total_kwh': round(float(analysis['production_total']), 2),
                        'average_hourly_kwh': round(float(analysis['production_mean']), 3),
                        'max_hourly_kwh': round(float(analysis['production_max']), 3),
                        'hours_with_production': int(analysis['hours_with_production'])
                    },
                    'negative_prices': {
                        'hours_count': int(analysis['negative_price_hours']),
                        'production_kwh': round(float(analysis['production_during_negative_prices']), 2),
                        'average_production_kwh': round(float(analysis['avg_production_during_negative_prices']), 3),
                        'lowest_price': format_price_response(float(analysis['price_min_eur_mwh'])) if analysis['negative_price_hours'] > 0 else None,
                        'average_negative_price': format_price_response(float(analysis['price_mean_eur_mwh'])) if analysis['negative_price_hours'] > 0 else None,
                        'total_cost': {
                            'value': round(float(analysis['negative_export_cost_abs_sek']) * (currency_rate / 11.5), 2),  # Convert from SEK
                            'currency': currency
                        } if analysis['negative_price_hours'] > 0 else None
                    },
                    'export_value': {
                        'total': {
                            'value': round(float(analysis['total_export_value_sek']) * (currency_rate / 11.5), 2),  # Convert from SEK
                            'currency': currency
                        },
                        'positive_prices': {
                            'value': round(float(analysis['positive_export_value_sek']) * (currency_rate / 11.5), 2),  # Convert from SEK
                            'currency': currency
                        }
                    }
                },
                'metadata': {
                    'area_code': area,
                    'currency': currency,
                    'exchange_rate_eur': float(currency_rate),
                    'file_processed': secure_filename(file.filename),
                    'database_records_used': int(len(merged_df))
                }
            }
            
            return safe_jsonify(response)
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_filename)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(413)
def too_large(e):
    """Handle file too large error."""
    return jsonify({'error': 'File too large. Maximum size is 16MB'}), 413

@app.errorhandler(404)
def not_found(e):
    """Handle not found error."""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    """Handle internal server error."""
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Price Production Analysis Flask API')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to (default: 5000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    print(f"Starting Price Production Analysis API on {args.host}:{args.port}")
    print(f"Debug mode: {args.debug}")
    print("\nAvailable endpoints:")
    print("  GET  /health              - Health check")
    print("  GET  /currencies          - List supported currencies")
    print("  GET  /database/info       - Database information")
    print("  GET  /database/areas      - List available areas")
    print("  POST /detect-csv-format   - Detect CSV file format")
    print("  POST /analyze             - Analyze production data")
    
    app.run(host=args.host, port=args.port, debug=args.debug)
