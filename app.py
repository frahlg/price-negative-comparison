#!/usr/bin/env python3
"""
Sourceful Energy - Price Production Analysis Web Application

A comprehensive web application for analyzing electricity prices and solar production data.
Built with Flask, Bootstrap, and modern web technologies.

Usage:
    python app.py

Web Interface:
    GET / - Main dashboard and upload interface
    POST /upload - Upload and analyze production data
    GET /results/<session_id> - View analysis results
    GET /status - Application status and health
"""

from flask import Flask, request, jsonify, make_response, render_template, Blueprint, session, flash, redirect
import pandas as pd
import tempfile
import os
import json
import numpy as np
import sqlite3
import pickle
import uuid
from datetime import datetime, date
from pathlib import Path
from utils.csv_format_detector_fallback import CSVFormatDetectorFallback
from utils.csv_format_module import CSVFormatDetector
from utils.ai_explainer import AIExplainer
from dotenv import load_dotenv
import logging
from werkzeug.utils import secure_filename
from core.price_fetcher import PriceFetcher
from core.production_loader import ProductionLoader
from core.price_analyzer import PriceAnalyzer
from core.db_manager import PriceDatabaseManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Security Configuration - Hardcode database path for production security
SECURE_DB_PATH = 'data/price_data.db'  # No user input allowed for database path

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

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production-MUST-BE-RANDOM')

# Internal API security configuration
import secrets
import hashlib
import time
from collections import defaultdict
from functools import wraps
from flask import session

# Generate a secure internal API token per session
INTERNAL_API_HEADER = 'X-Internal-API-Token'

# Rate limiting
request_counts = defaultdict(lambda: defaultdict(int))
REQUEST_LIMIT = 100  # requests per minute per IP
REQUEST_WINDOW = 60  # seconds

def generate_internal_token():
    """Generate a secure token for internal API access."""
    return secrets.token_urlsafe(32)

def check_rate_limit(ip):
    """Check if IP is within rate limits."""
    current_time = int(time.time())
    minute_window = current_time // REQUEST_WINDOW
    
    # Clean old entries
    for old_minute in list(request_counts[ip].keys()):
        if old_minute < minute_window - 1:
            del request_counts[ip][old_minute]
    
    # Check current requests
    current_requests = request_counts[ip][minute_window]
    if current_requests >= REQUEST_LIMIT:
        return False
    
    request_counts[ip][minute_window] += 1
    return True

def require_internal_access(f):
    """Decorator to protect internal API endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Rate limiting
        if not check_rate_limit(request.remote_addr):
            logger.warning(f"Rate limit exceeded for {request.remote_addr}")
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        # Check if request has valid internal token
        token = request.headers.get(INTERNAL_API_HEADER)
        session_token = session.get('internal_api_token')
        
        # Additional security: Check if request is from same origin
        origin = request.headers.get('Origin')
        referer = request.headers.get('Referer')
        host = request.headers.get('Host')
        
        # Allow requests from same origin or with valid referer
        valid_origin = (
            origin and origin.endswith(f"://{host}") or
            referer and f"://{host}" in referer or
            request.remote_addr in ['127.0.0.1', '::1']  # localhost
        )
        
        if not token or not session_token or token != session_token:
            logger.warning(f"Unauthorized internal API access attempt from {request.remote_addr}")
            return jsonify({'error': 'Unauthorized access to internal API'}), 403
            
        if not valid_origin:
            logger.warning(f"Invalid origin for internal API access from {request.remote_addr}: {origin}")
            return jsonify({'error': 'Invalid request origin'}), 403
            
        return f(*args, **kwargs)
    return decorated_function

# Create internal API Blueprint (protected)
internal_api = Blueprint('internal_api', __name__, url_prefix='/_api')

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

def cleanup_old_cache_files():
    """Clean up cache files older than 24 hours."""
    try:
        cache_dir = Path('data/cache')
        if not cache_dir.exists():
            return
            
        cutoff_time = datetime.now().timestamp() - (24 * 60 * 60)  # 24 hours ago
        
        for cache_file in cache_dir.glob('*.pkl'):
            if cache_file.stat().st_mtime < cutoff_time:
                try:
                    cache_file.unlink()
                    logger.info(f"Cleaned up old cache file: {cache_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to clean up cache file {cache_file.name}: {e}")
    except Exception as e:
        logger.warning(f"Cache cleanup failed: {e}")

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

def format_price_with_currency(price_eur_per_mwh, currency, rate):
    """Format price in the requested currency and appropriate units."""
    if currency == 'EUR':
        return f"{price_eur_per_mwh:.2f} EUR/MWh"
    else:
        # Convert to local currency per kWh for user-friendly display
        price_local_kwh = (price_eur_per_mwh * rate) / 1000
        return f"{price_local_kwh:.4f} {currency}/kWh"

@internal_api.route('/health', methods=['GET'])
@require_internal_access
def health_check():
    """Internal health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'Sourceful Energy Web Application',
        'version': '1.0.0'
    })

@require_internal_access
@internal_api.route('/currencies', methods=['GET'])
@require_internal_access
def get_supported_currencies():
    """Get list of supported currencies."""
    return jsonify({
        'supported_currencies': list(CURRENCY_RATES.keys()),
        'default': 'SEK',
        'rates': CURRENCY_RATES
    })

@require_internal_access
@internal_api.route('/database/info', methods=['GET'])
def database_info():
    """Get database information."""
    try:
        manager = PriceDatabaseManager(SECURE_DB_PATH)
        
        if not Path(SECURE_DB_PATH).exists():
            return jsonify({'error': 'Database does not exist'}), 404
        
        # Get basic database info
        import sqlite3
        with sqlite3.connect(SECURE_DB_PATH) as conn:
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

@require_internal_access
@internal_api.route('/database/areas', methods=['GET'])
def list_areas():
    """List available areas in the database."""
    try:
        if not Path(SECURE_DB_PATH).exists():
            return jsonify({'areas': []})
        
        import sqlite3
        with sqlite3.connect(SECURE_DB_PATH) as conn:
            areas = conn.execute('SELECT DISTINCT area_code FROM price_data ORDER BY area_code').fetchall()
        
        return jsonify({
            'areas': [area[0] for area in areas]
        })
        
    except Exception as e:
        logger.error(f"List areas error: {e}")
        return jsonify({'error': str(e)}), 500

@require_internal_access
@internal_api.route('/detect-csv-format', methods=['POST'])
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

@require_internal_access
@internal_api.route('/analyze/daily-summary', methods=['POST'])
def analyze_daily_summary():
    """
    Get daily summary analysis from production data.
    
    Expected form data:
    - file: CSV file with production data
    - area: Electricity area code (e.g., SE_4)
    - currency: Currency for display (optional, default: SEK)
    - start_date: Start date YYYY-MM-DD (optional)
    - end_date: End date YYYY-MM-DD (optional)
    """
    try:
        # Validate request (reuse logic from main analyze endpoint)
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
        # SECURITY: Database path hardcoded for security
        # db_path parameter removed from public API
        
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
            price_fetcher = PriceFetcher(db_path=SECURE_DB_PATH)
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
            
            # Merge and get daily summary
            merged_df = analyzer.merge_data(prices_df, production_df, currency_rate)
            daily_summary = analyzer.get_daily_summary(merged_df)
            
            # Convert to currency-appropriate format
            response = {
                'daily_summary': {
                    'period': {
                        'start': merged_df.index.min().isoformat(),
                        'end': merged_df.index.max().isoformat(),
                        'days': len(daily_summary)
                    },
                    'currency': currency,
                    'days': []
                }
            }
            
            # Process each day
            for date, row in daily_summary.iterrows():
                day_data = {
                    'date': date.isoformat(),
                    'production': {
                        'total_kwh': round(float(row['production_kwh_sum']), 2),
                        'average_kwh': round(float(row['production_kwh_mean']), 3),
                        'max_kwh': round(float(row['production_kwh_max']), 3)
                    },
                    'prices': {
                        'average': {
                            'value': round(float(row['price_sek_per_kwh_mean']) * (currency_rate / 11.5), 4) if currency != 'SEK' else round(float(row['price_sek_per_kwh_mean']), 4),
                            'unit': f'{currency}/kWh'
                        },
                        'min': {
                            'value': round(float(row['price_sek_per_kwh_min']) * (currency_rate / 11.5), 4) if currency != 'SEK' else round(float(row['price_sek_per_kwh_min']), 4),
                            'unit': f'{currency}/kWh'
                        },
                        'max': {
                            'value': round(float(row['price_sek_per_kwh_max']) * (currency_rate / 11.5), 4) if currency != 'SEK' else round(float(row['price_sek_per_kwh_max']), 4),
                            'unit': f'{currency}/kWh'
                        }
                    },
                    'export_value': {
                        'value': round(float(row['export_value_sek_sum']) * (currency_rate / 11.5), 2) if currency != 'SEK' else round(float(row['export_value_sek_sum']), 2),
                        'currency': currency
                    }
                }
                response['daily_summary']['days'].append(day_data)
            
            return safe_jsonify(response)
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_filename)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Daily summary analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@require_internal_access
@internal_api.route('/analyze/negative-prices', methods=['POST'])
def analyze_negative_prices_endpoint():
    """
    Dedicated negative price analysis endpoint.
    
    Expected form data:
    - file: CSV file with production data
    - area: Electricity area code (e.g., SE_4)
    - currency: Currency for display (optional, default: SEK)
    - start_date: Start date YYYY-MM-DD (optional)
    - end_date: End date YYYY-MM-DD (optional)
    """
    try:
        # Validate request (reuse logic from main analyze endpoint)
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
        # SECURITY: Database path hardcoded for security
        # db_path parameter removed from public API
        
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
            price_fetcher = PriceFetcher(db_path=SECURE_DB_PATH)
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
            
            # Get price data and merge
            prices_df = price_fetcher.get_price_data(area, start_date, end_date)
            merged_df = analyzer.merge_data(prices_df, production_df, currency_rate)
            
            # Filter for negative price periods
            negative_prices_df = merged_df[merged_df['price_eur_per_mwh'] < 0].copy()
            negative_with_production = negative_prices_df[negative_prices_df['production_kwh'] > 0].copy()
            
            if len(negative_with_production) == 0:
                return jsonify({
                    'negative_price_analysis': {
                        'has_negative_prices': False,
                        'message': 'No production during negative price periods in the dataset',
                        'period': {
                            'start': merged_df.index.min().isoformat(),
                            'end': merged_df.index.max().isoformat()
                        }
                    }
                })
            
            # Calculate monthly breakdown
            negative_prices_df['month'] = negative_prices_df.index.to_period('M')
            monthly_breakdown = negative_prices_df.groupby('month').agg({
                'production_kwh': 'sum',
                'export_value_sek': 'sum'
            })
            monthly_breakdown['cost_abs'] = abs(monthly_breakdown['export_value_sek'])
            monthly_breakdown = monthly_breakdown[monthly_breakdown['production_kwh'] > 0]
            
            # Calculate daily breakdown
            negative_prices_df['date'] = negative_prices_df.index.date
            daily_breakdown = negative_prices_df.groupby('date').agg({
                'production_kwh': 'sum',
                'export_value_sek': 'sum'
            })
            daily_breakdown['cost_abs'] = abs(daily_breakdown['export_value_sek'])
            daily_breakdown = daily_breakdown[daily_breakdown['production_kwh'] > 0]
            
            # Top 10 most expensive hours
            top_expensive = negative_with_production.nsmallest(10, 'export_value_sek')
            
            # Total costs and comparison
            total_cost = abs(negative_prices_df['export_value_sek'].sum())
            total_export_value = merged_df['export_value_sek'].sum()
            positive_export_value = merged_df[merged_df['price_eur_per_mwh'] > 0]['export_value_sek'].sum()
            
            # Convert currency if needed
            currency_conversion_factor = currency_rate / 11.5 if currency != 'SEK' else 1.0
            
            response = {
                'negative_price_analysis': {
                    'has_negative_prices': True,
                    'period': {
                        'start': merged_df.index.min().isoformat(),
                        'end': merged_df.index.max().isoformat(),
                        'total_hours': len(merged_df),
                        'negative_price_hours': len(negative_prices_df),
                        'negative_price_hours_with_production': len(negative_with_production)
                    },
                    'currency': currency,
                    'overview': {
                        'total_production_kwh': round(float(negative_prices_df['production_kwh'].sum()), 2),
                        'average_hourly_production_kwh': round(float(negative_with_production['production_kwh'].mean()), 3),
                        'max_hourly_production_kwh': round(float(negative_with_production['production_kwh'].max()), 3),
                        'total_cost': {
                            'value': round(total_cost * currency_conversion_factor, 2),
                            'currency': currency
                        }
                    },
                    'price_statistics': {
                        'lowest_price': {
                            'value': round(float(negative_prices_df['price_sek_per_kwh'].min()) * currency_conversion_factor, 4),
                            'unit': f'{currency}/kWh'
                        },
                        'average_negative_price': {
                            'value': round(float(negative_prices_df['price_sek_per_kwh'].mean()) * currency_conversion_factor, 4),
                            'unit': f'{currency}/kWh'
                        }
                    },
                    'monthly_breakdown': [
                        {
                            'month': str(month),
                            'production_kwh': round(float(row['production_kwh']), 1),
                            'cost': {
                                'value': round(float(row['cost_abs']) * currency_conversion_factor, 2),
                                'currency': currency
                            }
                        }
                        for month, row in monthly_breakdown.iterrows()
                    ],
                    'top_expensive_hours': [
                        {
                            'datetime': idx.isoformat(),
                            'production_kwh': round(float(row['production_kwh']), 3),
                            'price': {
                                'value': round(float(row['price_sek_per_kwh']) * currency_conversion_factor, 4),
                                'unit': f'{currency}/kWh'
                            },
                            'cost': {
                                'value': round(abs(float(row['export_value_sek'])) * currency_conversion_factor, 3),
                                'currency': currency
                            }
                        }
                        for idx, row in top_expensive.iterrows()
                    ],
                    'impact_analysis': {
                        'total_export_value': {
                            'value': round(total_export_value * currency_conversion_factor, 2),
                            'currency': currency
                        },
                        'positive_price_export_value': {
                            'value': round(positive_export_value * currency_conversion_factor, 2),
                            'currency': currency
                        },
                        'negative_price_cost': {
                            'value': round(total_cost * currency_conversion_factor, 2),
                            'currency': currency
                        },
                        'income_reduction_percentage': round((total_cost / positive_export_value) * 100, 2) if positive_export_value > 0 else 0
                    },
                    'daily_summary': {
                        'days_with_negative_costs': len(daily_breakdown),
                        'average_daily_cost': {
                            'value': round(daily_breakdown['cost_abs'].mean() * currency_conversion_factor, 2),
                            'currency': currency
                        },
                        'most_expensive_day': {
                            'date': str(daily_breakdown['cost_abs'].idxmax()),
                            'cost': {
                                'value': round(daily_breakdown['cost_abs'].max() * currency_conversion_factor, 2),
                                'currency': currency
                            }
                        }
                    }
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
        logger.error(f"Negative price analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@require_internal_access
@internal_api.route('/docs', methods=['GET'])
def api_documentation():
    """Get API documentation in JSON format."""
    docs = {
        'api_info': {
            'name': 'Price Production Analysis API',
            'version': '1.0.0',
            'description': 'REST API for analyzing electricity prices and solar production data',
            'base_url': request.host_url.rstrip('/')
        },
        'endpoints': {
            'GET /api/health': {
                'description': 'Health check endpoint',
                'parameters': None,
                'response': 'JSON with service status'
            },
            'GET /api/currencies': {
                'description': 'List supported currencies and exchange rates',
                'parameters': None,
                'response': 'JSON with currency list and rates'
            },
            'GET /api/database/info': {
                'description': 'Get database information and statistics',
                'parameters': None,
                'response': 'JSON with database statistics'
            },
            'GET /api/database/areas': {
                'description': 'List available electricity price areas',
                'parameters': None,
                'response': 'JSON with area list'
            },
            'POST /api/detect-csv-format': {
                'description': 'Detect CSV file format using AI or traditional methods',
                'parameters': {
                    'file': 'Required CSV file upload',
                    'use_llm': 'Optional boolean to use AI detection (default: true)'
                },
                'response': 'JSON with detected format and sample data'
            },
            'POST /api/analyze': {
                'description': 'Analyze production data against electricity prices',
                'parameters': {
                    'file': 'Required CSV file with production data',
                    'area': 'Required electricity area code (e.g., SE_4)',
                    'currency': 'Optional target currency (default: SEK)',
                    'start_date': 'Optional start date YYYY-MM-DD',
                    'end_date': 'Optional end date YYYY-MM-DD'
                },
                'response': 'JSON with comprehensive analysis results'
            },
            'POST /api/analyze/daily-summary': {
                'description': 'Get daily summary analysis from production data',
                'parameters': {
                    'file': 'Required CSV file with production data',
                    'area': 'Required electricity area code',
                    'currency': 'Optional target currency (default: SEK)',
                    'start_date': 'Optional start date YYYY-MM-DD',
                    'end_date': 'Optional end date YYYY-MM-DD'
                },
                'response': 'JSON with daily breakdown statistics'
            },
            'POST /api/analyze/negative-prices': {
                'description': 'Dedicated negative price analysis with detailed breakdown',
                'parameters': {
                    'file': 'Required CSV file with production data',
                    'area': 'Required electricity area code',
                    'currency': 'Optional target currency (default: SEK)',
                    'start_date': 'Optional start date YYYY-MM-DD',
                    'end_date': 'Optional end date YYYY-MM-DD'
                },
                'response': 'JSON with negative price analysis and cost breakdown'
            },
            'GET /api/docs': {
                'description': 'Get this API documentation',
                'parameters': None,
                'response': 'JSON with API documentation'
            },
            'GET /api/graph/price-timeline': {
                'description': 'Get price data in timeline format for graphing',
                'parameters': {
                    'area': 'Required electricity area code',
                    'start_date': 'Optional start date YYYY-MM-DD',
                    'end_date': 'Optional end date YYYY-MM-DD',
                    'currency': 'Optional target currency (default: EUR)',
                    'resolution': 'Optional resolution: hourly, daily, weekly (default: hourly)'
                },
                'response': 'JSON with timeline data for charts'
            },
            'GET /api/graph/price-distribution': {
                'description': 'Get price distribution data for histograms',
                'parameters': {
                    'area': 'Required electricity area code',
                    'start_date': 'Optional start date YYYY-MM-DD',
                    'end_date': 'Optional end date YYYY-MM-DD',
                    'currency': 'Optional target currency (default: EUR)',
                    'bins': 'Optional number of histogram bins (default: 50)'
                },
                'response': 'JSON with distribution data for histograms'
            },
            'GET /api/graph/negative-price-periods': {
                'description': 'Get negative price periods data for visualization',
                'parameters': {
                    'area': 'Required electricity area code',
                    'start_date': 'Optional start date YYYY-MM-DD',
                    'end_date': 'Optional end date YYYY-MM-DD',
                    'currency': 'Optional target currency (default: EUR)'
                },
                'response': 'JSON with negative price periods and detailed breakdown'
            }
        },
        'supported_currencies': list(CURRENCY_RATES.keys()),
        'supported_areas': [
            'SE_1', 'SE_2', 'SE_3', 'SE_4',  # Sweden
            'NO_1', 'NO_2', 'NO_3', 'NO_4', 'NO_5',  # Norway
            'DK_1', 'DK_2',  # Denmark
            'FI'  # Finland
        ],
        'file_formats': {
            'production_csv': {
                'description': 'CSV file with solar production data',
                'required_columns': ['datetime', 'production'],
                'supported_separators': [',', ';'],
                'supported_encodings': ['utf-8', 'iso-8859-1', 'cp1252'],
                'example_headers': [
                    'Datum;Produktion kWh',
                    'Date,Production kWh',
                    'DateTime,kWh'
                ]
            }
        },
        'examples': {
            'analyze_request': {
                'method': 'POST',
                'url': '/api/analyze',
                'form_data': {
                    'file': '@production.csv',
                    'area': 'SE_4',
                    'currency': 'SEK',
                    'start_date': '2025-06-01',
                    'end_date': '2025-06-30'
                }
            }
        }
    }
    
    return jsonify(docs)

@require_internal_access
@internal_api.route('/analyze/export', methods=['POST'])
def analyze_and_export():
    """
    Analyze production data and return merged CSV data.
    
    Expected form data (same as /analyze):
    - file: CSV file with production data
    - area: Electricity area code (e.g., SE_4)
    - currency: Currency for display (optional, default: SEK)
    - start_date: Start date YYYY-MM-DD (optional)
    - end_date: End date YYYY-MM-DD (optional)
    """
    try:
        # Validate request (reuse logic from main analyze endpoint)
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
        # SECURITY: Database path hardcoded for security
        # db_path parameter removed from public API
        
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
            price_fetcher = PriceFetcher(db_path=SECURE_DB_PATH)
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
            
            # Merge data
            merged_df = analyzer.merge_data(prices_df, production_df, currency_rate)
            
            # Convert currency columns if needed
            if currency != 'SEK':
                conversion_factor = currency_rate / 11.5
                # Create currency-specific columns
                merged_df[f'price_{currency.lower()}_per_kwh'] = merged_df['price_sek_per_kwh'] * conversion_factor
                merged_df[f'export_value_{currency.lower()}'] = merged_df['export_value_sek'] * conversion_factor
                merged_df[f'price_daily_avg_{currency.lower()}_per_kwh'] = merged_df['price_sek_per_kwh'] * conversion_factor
                merged_df[f'export_value_daily_{currency.lower()}'] = merged_df['export_value_sek'] * conversion_factor
            
            # Create CSV output
            import io
            output = io.StringIO()
            merged_df.to_csv(output)
            csv_content = output.getvalue()
            
            # Create filename
            safe_filename = secure_filename(file.filename)
            base_name = safe_filename.rsplit('.', 1)[0] if '.' in safe_filename else safe_filename
            export_filename = f'{base_name}_analysis_{area}_{currency}.csv'
            
            # Create response
            response = make_response(csv_content)
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = f'attachment; filename={export_filename}'
            
            return response
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_filename)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Export analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@require_internal_access
@internal_api.route('/analyze', methods=['POST'])
def analyze_production():
    """
    Analyze production data against electricity prices.
    
    Expected form data:
    - file: CSV file with production data
    - area: Electricity area code (e.g., SE_4)
    - currency: Currency for display (optional, default: SEK)
    - start_date: Start date YYYY-MM-DD (optional)
    - end_date: End date YYYY-MM-DD (optional)
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
        # SECURITY: Database path hardcoded for security
        # db_path parameter removed from public API
        
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
            price_fetcher = PriceFetcher(db_path=SECURE_DB_PATH)
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
            def format_price_response(price_eur_per_mwh):
                if currency == 'EUR':
                    return {
                        'value': price_eur_per_mwh,
                        'unit': 'EUR/MWh',
                        'display': f"{price_eur_per_mwh:.2f} EUR/MWh"
                    }
                else:
                    price_local_kwh = (price_eur_per_mwh * currency_rate) / 1000
                    return {
                        'value': price_local_kwh,
                        'unit': f'{currency}/kWh',
                        'display': f"{price_local_kwh:.4f} {currency}/kWh",
                        'reference': f"{price_eur_per_mwh:.2f} EUR/MWh"
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

# Graph Data Endpoints for Frontend

@require_internal_access
@internal_api.route('/graph/price-timeline', methods=['GET'])
def get_price_timeline():
    """Get price data in timeline format for graphing."""
    try:
        # Get parameters
        area = request.args.get('area')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        currency = request.args.get('currency', 'EUR')
        # SECURITY: Database path hardcoded for security
        resolution = request.args.get('resolution', 'hourly')  # hourly, daily, weekly
        
        if not area:
            return jsonify({'error': 'Area code is required'}), 400
            
        # Get data from database directly
        if not Path(SECURE_DB_PATH).exists():
            return jsonify({'error': f'Database not found'}), 404
            
        with sqlite3.connect(SECURE_DB_PATH) as conn:
            # Build query with optional date filtering
            if start_date and end_date:
                query = '''SELECT datetime, price_eur_per_mwh FROM price_data 
                          WHERE area_code = ? AND datetime BETWEEN ? AND ? 
                          ORDER BY datetime'''
                df = pd.read_sql_query(query, conn, params=[area, start_date, end_date])
            elif start_date:
                query = '''SELECT datetime, price_eur_per_mwh FROM price_data 
                          WHERE area_code = ? AND datetime >= ? 
                          ORDER BY datetime'''
                df = pd.read_sql_query(query, conn, params=[area, start_date])
            elif end_date:
                query = '''SELECT datetime, price_eur_per_mwh FROM price_data 
                          WHERE area_code = ? AND datetime <= ? 
                          ORDER BY datetime'''
                df = pd.read_sql_query(query, conn, params=[area, end_date])
            else:
                query = '''SELECT datetime, price_eur_per_mwh FROM price_data 
                          WHERE area_code = ? ORDER BY datetime'''
                df = pd.read_sql_query(query, conn, params=[area])
                
        if df.empty:
            return jsonify({'error': f'No data found for area {area}'}), 404
            
        # Convert datetime to pandas datetime index
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
            
        # Get exchange rate
        currency_rate = CURRENCY_RATES.get(currency, 1.0)
        
        # Process data based on resolution
        if resolution == 'daily':
            df_resampled = df.resample('D').agg({
                'price_eur_per_mwh': ['mean', 'min', 'max', 'std']
            }).round(2)
            df_resampled.columns = ['price_mean', 'price_min', 'price_max', 'price_std']
        elif resolution == 'weekly':
            df_resampled = df.resample('W').agg({
                'price_eur_per_mwh': ['mean', 'min', 'max', 'std']
            }).round(2)
            df_resampled.columns = ['price_mean', 'price_min', 'price_max', 'price_std']
        else:  # hourly (default)
            df_resampled = df.copy()
            df_resampled['price_mean'] = df_resampled['price_eur_per_mwh']
            df_resampled['price_min'] = df_resampled['price_eur_per_mwh'] 
            df_resampled['price_max'] = df_resampled['price_eur_per_mwh']
            df_resampled['price_std'] = 0
            
        # Convert to target currency
        for col in ['price_mean', 'price_min', 'price_max']:
            df_resampled[col] = df_resampled[col] * currency_rate
            
        # Build timeline data
        timeline_data = []
        for timestamp, row in df_resampled.iterrows():
            timeline_data.append({
                'timestamp': timestamp.isoformat(),
                'price': round(float(row['price_mean']), 2),
                'price_min': round(float(row['price_min']), 2) if resolution != 'hourly' else None,
                'price_max': round(float(row['price_max']), 2) if resolution != 'hourly' else None,
                'price_std': round(float(row['price_std']), 2) if resolution != 'hourly' else None,
                'is_negative': float(row['price_mean']) < 0
            })
            
        return jsonify({
            'area': area,
            'currency': currency,
            'resolution': resolution,
            'data_points': len(timeline_data),
            'date_range': {
                'start': df_resampled.index.min().isoformat(),
                'end': df_resampled.index.max().isoformat()
            },
            'timeline': timeline_data,
            'statistics': {
                'min_price': round(float(df_resampled['price_min'].min()), 2),
                'max_price': round(float(df_resampled['price_max'].max()), 2),
                'avg_price': round(float(df_resampled['price_mean'].mean()), 2),
                'negative_hours': int((df_resampled['price_mean'] < 0).sum())
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting price timeline: {str(e)}")
        return jsonify({'error': str(e)}), 500

@require_internal_access
@internal_api.route('/graph/price-distribution', methods=['GET'])
def get_price_distribution():
    """Get price distribution data for histograms."""
    try:
        # Get parameters
        area = request.args.get('area')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        currency = request.args.get('currency', 'EUR')
        # SECURITY: Database path hardcoded for security
        bins = int(request.args.get('bins', 50))
        
        if not area:
            return jsonify({'error': 'Area code is required'}), 400
            
        # Get data from database directly
        if not Path(SECURE_DB_PATH).exists():
            return jsonify({'error': f'Database not found'}), 404
            
        with sqlite3.connect(SECURE_DB_PATH) as conn:
            # Build query with optional date filtering
            if start_date and end_date:
                query = '''SELECT price_eur_per_mwh FROM price_data 
                          WHERE area_code = ? AND datetime BETWEEN ? AND ?'''
                df = pd.read_sql_query(query, conn, params=[area, start_date, end_date])
            elif start_date:
                query = '''SELECT price_eur_per_mwh FROM price_data 
                          WHERE area_code = ? AND datetime >= ?'''
                df = pd.read_sql_query(query, conn, params=[area, start_date])
            elif end_date:
                query = '''SELECT price_eur_per_mwh FROM price_data 
                          WHERE area_code = ? AND datetime <= ?'''
                df = pd.read_sql_query(query, conn, params=[area, end_date])
            else:
                query = '''SELECT price_eur_per_mwh FROM price_data 
                          WHERE area_code = ?'''
                df = pd.read_sql_query(query, conn, params=[area])
                
        if df.empty:
            return jsonify({'error': f'No data found for area {area}'}), 404
            
        # Get exchange rate and convert prices
        currency_rate = CURRENCY_RATES.get(currency, 1.0)
        prices = df['price_eur_per_mwh'] * currency_rate
        
        # Calculate histogram
        import numpy as np
        hist, bin_edges = np.histogram(prices, bins=bins)
        
        # Build distribution data
        distribution_data = []
        for i in range(len(hist)):
            distribution_data.append({
                'bin_start': round(float(bin_edges[i]), 2),
                'bin_end': round(float(bin_edges[i + 1]), 2),
                'bin_center': round(float((bin_edges[i] + bin_edges[i + 1]) / 2), 2),
                'count': int(hist[i]),
                'percentage': round(float(hist[i] / len(prices) * 100), 2)
            })
            
        # Get the date range for response
        with sqlite3.connect(SECURE_DB_PATH) as conn:
            date_query = '''SELECT MIN(datetime), MAX(datetime) FROM price_data 
                           WHERE area_code = ?'''
            if start_date and end_date:
                date_query += ' AND datetime BETWEEN ? AND ?'
                date_range = conn.execute(date_query, [area, start_date, end_date]).fetchone()
            elif start_date:
                date_query += ' AND datetime >= ?'
                date_range = conn.execute(date_query, [area, start_date]).fetchone()
            elif end_date:
                date_query += ' AND datetime <= ?'
                date_range = conn.execute(date_query, [area, end_date]).fetchone()
            else:
                date_range = conn.execute(date_query, [area]).fetchone()
                
        return jsonify({
            'area': area,
            'currency': currency,
            'total_hours': len(prices),
            'date_range': {
                'start': date_range[0] if date_range and date_range[0] else None,
                'end': date_range[1] if date_range and date_range[1] else None
            },
            'distribution': distribution_data,
            'statistics': {
                'min_price': round(float(prices.min()), 2),
                'max_price': round(float(prices.max()), 2),
                'mean_price': round(float(prices.mean()), 2),
                'median_price': round(float(prices.median()), 2),
                'std_price': round(float(prices.std()), 2),
                'negative_hours': int((prices < 0).sum()),
                'negative_percentage': round(float((prices < 0).sum() / len(prices) * 100), 2)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting price distribution: {str(e)}")
        return jsonify({'error': str(e)}), 500

@require_internal_access
@internal_api.route('/graph/negative-price-periods', methods=['GET'])
def get_negative_price_periods():
    """Get negative price periods data for visualization."""
    try:
        # Get parameters
        area = request.args.get('area')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        currency = request.args.get('currency', 'EUR')
        # SECURITY: Database path hardcoded for security
        
        if not area:
            return jsonify({'error': 'Area code is required'}), 400
            
        # Get data from database directly
        if not Path(SECURE_DB_PATH).exists():
            return jsonify({'error': f'Database not found'}), 404
            
        with sqlite3.connect(SECURE_DB_PATH) as conn:
            # Build query with optional date filtering
            if start_date and end_date:
                query = '''SELECT datetime, price_eur_per_mwh FROM price_data 
                          WHERE area_code = ? AND datetime BETWEEN ? AND ? 
                          ORDER BY datetime'''
                df = pd.read_sql_query(query, conn, params=[area, start_date, end_date])
            elif start_date:
                query = '''SELECT datetime, price_eur_per_mwh FROM price_data 
                          WHERE area_code = ? AND datetime >= ? 
                          ORDER BY datetime'''
                df = pd.read_sql_query(query, conn, params=[area, start_date])
            elif end_date:
                query = '''SELECT datetime, price_eur_per_mwh FROM price_data 
                          WHERE area_code = ? AND datetime <= ? 
                          ORDER BY datetime'''
                df = pd.read_sql_query(query, conn, params=[area, end_date])
            else:
                query = '''SELECT datetime, price_eur_per_mwh FROM price_data 
                          WHERE area_code = ? ORDER BY datetime'''
                df = pd.read_sql_query(query, conn, params=[area])
                
        if df.empty:
            return jsonify({'error': f'No data found for area {area}'}), 404
            
        # Convert datetime to pandas datetime index
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
            
        # Get exchange rate and convert prices
        currency_rate = CURRENCY_RATES.get(currency, 1.0)
        df['price_converted'] = df['price_eur_per_mwh'] * currency_rate
        
        # Find negative price periods
        negative_mask = df['price_converted'] < 0
        negative_periods = []
        
        if negative_mask.any():
            # Group consecutive negative hours
            changes = negative_mask.diff().fillna(False)
            period_starts = df[changes & negative_mask].index
            period_ends = df[changes & ~negative_mask].index
            
            # Handle case where negative period extends to end of data
            if len(period_starts) > len(period_ends):
                period_ends = period_ends.append(pd.Index([df.index[-1]]))
                
            # Handle case where data starts with negative period
            if len(period_ends) > len(period_starts):
                period_starts = pd.Index([df.index[0]]).append(period_starts)
                
            for start, end in zip(period_starts, period_ends):
                period_data = df.loc[start:end]
                if (period_data['price_converted'] < 0).any():
                    # Find actual start and end of negative period
                    neg_data = period_data[period_data['price_converted'] < 0]
                    if not neg_data.empty:
                        negative_periods.append({
                            'start': neg_data.index.min().isoformat(),
                            'end': neg_data.index.max().isoformat(),
                            'duration_hours': len(neg_data),
                            'min_price': round(float(neg_data['price_converted'].min()), 2),
                            'avg_price': round(float(neg_data['price_converted'].mean()), 2),
                            'hourly_prices': [
                                {
                                    'timestamp': ts.isoformat(),
                                    'price': round(float(price), 2)
                                }
                                for ts, price in neg_data['price_converted'].items()
                            ]
                        })
        
        return jsonify({
            'area': area,
            'currency': currency,
            'total_hours': len(df),
            'negative_hours': int((df['price_converted'] < 0).sum()),
            'date_range': {
                'start': df.index.min().isoformat() if not df.empty else None,
                'end': df.index.max().isoformat() if not df.empty else None
            },
            'negative_periods': negative_periods,
            'statistics': {
                'total_negative_periods': len(negative_periods),
                'total_negative_hours': sum(p['duration_hours'] for p in negative_periods),
                'longest_period_hours': max((p['duration_hours'] for p in negative_periods), default=0),
                'lowest_price': round(float(df['price_converted'].min()), 2) if not df.empty else None,
                'avg_negative_price': round(float(df[df['price_converted'] < 0]['price_converted'].mean()), 2) if (df['price_converted'] < 0).any() else None
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting negative price periods: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    """Handle not found error."""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    """Handle internal server error."""
    return jsonify({'error': 'Internal server error'}), 500

# Register internal API Blueprint with hidden prefix
app.register_blueprint(internal_api)

# Web Routes (Public Interface)
@app.route('/')
def index():
    """Main web interface with dashboard and upload functionality."""
    # Generate internal API token for this session
    if 'internal_api_token' not in session:
        session['internal_api_token'] = generate_internal_token()
    
    return render_template('index.html', 
                         message="Accelerating Energy Optimization",
                         page_title="Dashboard")

@app.route('/api-token')
def get_api_token():
    """Provide internal API token for authenticated frontend requests."""
    if 'internal_api_token' not in session:
        session['internal_api_token'] = generate_internal_token()
    
    return jsonify({
        'token': session['internal_api_token'],
        'header': INTERNAL_API_HEADER
    })

@app.route('/status')
def status():
    """Public status page showing application health and statistics."""
    try:
        # Get database info for status display
        if Path(SECURE_DB_PATH).exists():
            with sqlite3.connect(SECURE_DB_PATH) as conn:
                total_records = conn.execute('SELECT COUNT(*) FROM price_data').fetchone()[0]
                areas = conn.execute('SELECT DISTINCT area_code FROM price_data ORDER BY area_code').fetchall()
                date_range = conn.execute('SELECT MIN(datetime), MAX(datetime) FROM price_data').fetchone()
        else:
            total_records = 0
            areas = []
            date_range = (None, None)
            
        status_data = {
            'service': 'Sourceful Energy Web Application',
            'status': 'operational',
            'database': {
                'records': total_records,
                'areas': len(areas),
                'coverage': f"{date_range[0]} to {date_range[1]}" if date_range[0] else "No data"
            },
            'features': {
                'csv_analysis': True,
                'negative_price_detection': True,
                'multi_currency': True,
                'supported_currencies': list(CURRENCY_RATES.keys())
            }
        }
        
        return render_template('status.html', status=status_data)
    except Exception as e:
        logger.error(f"Status page error: {e}")
        return render_template('status.html', status={'service': 'Sourceful Energy', 'status': 'error'})

@app.route('/results')
def results_page():
    """Display analysis results."""
    if 'analysis_results' not in session:
        flash('No analysis results found. Please upload a file first.', 'error')
        return redirect('/')
    
    # Load full analysis data from cache
    session_id = session.get('session_id')
    if session_id:
        try:
            cache_file = Path('data/cache') / f"{session_id}.pkl"
            if cache_file.exists():
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                
                # Use cached data which includes chart time series
                results = {
                    'analysis': cached_data['analysis'],
                    'metadata': cached_data['metadata'],
                    'ai_explanation': cached_data.get('ai_explanation', 'AI explanation not available for this analysis.')
                }
                
                # Add session_id to metadata for download links
                results['metadata']['session_id'] = session_id
                
                logger.info(f"Loaded full analysis from cache for session {session_id}")
            else:
                # Cache file not found
                flash('Analysis data expired. Please upload your file again.', 'error')
                return redirect('/')
        except Exception as e:
            logger.error(f"Error loading cached analysis: {e}")
            flash('Error loading analysis data. Please upload your file again.', 'error')
            return redirect('/')
    else:
        # No session ID
        flash('Session expired. Please upload your file again.', 'error')
        return redirect('/')
    
    return render_template('results.html', 
                         results=results, 
                         page_title="Analysis Results")

@app.route('/upload', methods=['GET', 'POST'])
def upload_page():
    """Upload page for production data analysis."""
    if request.method == 'GET':
        return render_template('upload.html', page_title="Upload & Analyze")
    
    # Handle POST - File upload and analysis
    try:
        # Validate file upload
        if 'file' not in request.files:
            flash('No file provided', 'error')
            return render_template('upload.html', page_title="Upload & Analyze")
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return render_template('upload.html', page_title="Upload & Analyze")
        
        if not allowed_file(file.filename):
            flash('Invalid file type. Only CSV files are allowed.', 'error')
            return render_template('upload.html', page_title="Upload & Analyze")
        
        # Get form parameters
        area = request.form.get('area')
        if not area:
            flash('Please select an electricity area.', 'error')
            return render_template('upload.html', page_title="Upload & Analyze")
        
        currency = request.form.get('currency', 'SEK').upper()
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        # Validate currency
        try:
            currency_rate = get_currency_rate(currency)
        except ValueError as e:
            flash(f'Currency error: {str(e)}', 'error')
            return render_template('upload.html', page_title="Upload & Analyze")
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.csv', delete=False) as temp_file:
            file.save(temp_file.name)
            temp_filename = temp_file.name
        
        try:
            # Create analysis components
            price_fetcher = PriceFetcher(db_path=SECURE_DB_PATH)
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
            
            # Get price data with automatic fetching of missing data
            prices_df = price_fetcher.get_price_data(area, start_date, end_date)
            
            # Merge and analyze
            merged_df = analyzer.merge_data(prices_df, production_df, currency_rate)
            analysis = analyzer.analyze_data(merged_df)
            
            # Convert analysis results to JSON-serializable format using our custom encoder
            analysis_json = json.loads(json.dumps(analysis, cls=NumpyJSONEncoder))
            
            # Prepare metadata with native types
            metadata = {
                'area_code': area,
                'currency': currency,
                'currency_rate': float(currency_rate),
                'file_name': secure_filename(file.filename),
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'data_points': int(len(merged_df))
            }
            
            # Generate AI explanation of the analysis
            ai_explanation = None
            try:
                logger.info("Generating AI explanation of analysis results")
                explainer = AIExplainer()
                ai_explanation = explainer.explain_analysis(analysis_json, metadata)
                logger.info(f"Generated AI explanation: {len(ai_explanation)} characters")
            except Exception as e:
                logger.warning(f"Failed to generate AI explanation: {e}")
                # Continue without AI explanation - it's not critical for the analysis
                ai_explanation = "AI explanation temporarily unavailable. The analysis data and charts below provide detailed insights into your solar production and electricity market performance."
            
            # Store the full analysis (including chart data) using a unique session ID
            session_id = session.get('session_id', None)
            if not session_id:
                session_id = str(uuid.uuid4())
                session['session_id'] = session_id
            
            # Create a session-safe version of analysis (without large time series data)
            session_analysis = {k: v for k, v in analysis_json.items() if k not in ['time_series', 'daily_series', 'negative_price_timeline']}
            
            # Store only essential metadata in session
            session['analysis_results'] = {
                'metadata': metadata,
                'has_cache': True,
                'session_id': session_id
            }
            
            # Store full analysis data temporarily (you could use Redis, file cache, or database)
            # For now, we'll use a simple file-based cache
            cache_dir = Path('data/cache')
            cache_dir.mkdir(exist_ok=True)
            cache_file = cache_dir / f"{session_id}.pkl"
            
            # Clean up old cache files periodically
            cleanup_old_cache_files()
            
            with open(cache_file, 'wb') as f:
                pickle.dump({
                    'analysis': analysis_json,
                    'metadata': metadata,
                    'ai_explanation': ai_explanation,
                    'timestamp': datetime.now().isoformat()
                }, f)
            
            logger.info(f"Analysis cached for session {session_id}, size: {len(str(analysis_json))} chars")
            
            flash('Analysis completed successfully!', 'success')
            return redirect('/results')
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_filename)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Upload processing error: {e}")
        flash(f'Analysis failed: {str(e)}', 'error')
        return render_template('upload.html', page_title="Upload & Analyze")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Price Production Analysis Flask API')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to (default: 5000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    print(f"Starting Sourceful Energy Web Application on {args.host}:{args.port}")
    print(f"Debug mode: {args.debug}")
    print("\nWeb Interface:")
    print(f"  http://{args.host}:{args.port}/                - Main dashboard with upload form")
    print(f"  http://{args.host}:{args.port}/status          - System status")
    print(f"  http://{args.host}:{args.port}/upload          - Upload data")
    print(f"  http://{args.host}:{args.port}/results         - Analysis results")
    print("\nInternal API endpoints available for frontend integration.")
    print(f"ENTSO-E API: {'Connected' if os.getenv('ENTSOE_API_KEY') else 'No API key - using existing data only'}")
    print(f"\nApplication Dashboard: http://{args.host}:{args.port}/")
    
    app.run(host=args.host, port=args.port, debug=args.debug)
