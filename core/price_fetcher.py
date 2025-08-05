#!/usr/bin/env python3
"""
Price Data Fetcher

Handles ENTSO-E API integration and database caching for electricity price data.
"""

import pandas as pd
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from entsoe import EntsoePandasClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PriceDatabase:
    """Handles SQLite database operations for price data caching."""
    
    def __init__(self, db_path='price_data.db'):
        """Initialize the price database."""
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS price_data (
                    area_code TEXT NOT NULL,
                    datetime TEXT NOT NULL,
                    price_eur_per_mwh REAL NOT NULL,
                    PRIMARY KEY (area_code, datetime)
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_area_datetime ON price_data(area_code, datetime)')
    
    def get_data_range(self, area_code: str) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp], int]:
        """Get the available date range for an area."""
        with sqlite3.connect(self.db_path) as conn:
            query = '''
                SELECT MIN(datetime) as min_date, MAX(datetime) as max_date, COUNT(*) as count
                FROM price_data 
                WHERE area_code = ?
            '''
            result = conn.execute(query, (area_code,)).fetchone()
            if result[0] is None:
                return None, None, 0
            return pd.to_datetime(result[0]), pd.to_datetime(result[1]), result[2]
    
    def get_missing_periods(self, area_code: str, start_date: pd.Timestamp, end_date: pd.Timestamp) -> List[Tuple[pd.Timestamp, pd.Timestamp]]:
        """Identify periods that need to be downloaded."""
        min_date, max_date, count = self.get_data_range(area_code)
        
        requested_start = pd.to_datetime(start_date).tz_localize(None)
        requested_end = pd.to_datetime(end_date).tz_localize(None)
        
        missing_periods = []
        
        if min_date is None:
            # No data at all
            missing_periods.append((requested_start, requested_end))
        else:
            # Check if we need data before our earliest date
            if requested_start < min_date:
                missing_periods.append((requested_start, min(min_date - pd.Timedelta(hours=1), requested_end)))
            
            # Check if we need data after our latest date
            if requested_end > max_date:
                missing_periods.append((max(max_date + pd.Timedelta(hours=1), requested_start), requested_end))
        
        return missing_periods
    
    def store_data(self, area_code: str, price_data: pd.Series):
        """Store price data in the database."""
        logger.info(f"Storing {len(price_data)} price records for {area_code}")
        
        # Prepare data for insertion
        records = []
        for timestamp, price in price_data.items():
            # Ensure timezone-naive timestamp
            if hasattr(timestamp, 'tz') and timestamp.tz is not None:
                timestamp = timestamp.tz_localize(None)
            records.append((area_code, timestamp.isoformat(), float(price)))
        
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                'INSERT OR REPLACE INTO price_data (area_code, datetime, price_eur_per_mwh) VALUES (?, ?, ?)',
                records
            )
    
    def query_data(self, area_code: str, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
        """Query price data for a specific period."""
        start_str = pd.to_datetime(start_date).tz_localize(None).isoformat()
        end_str = pd.to_datetime(end_date).tz_localize(None).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            query = '''
                SELECT datetime, price_eur_per_mwh 
                FROM price_data 
                WHERE area_code = ? AND datetime >= ? AND datetime <= ?
                ORDER BY datetime
            '''
            df = pd.read_sql_query(query, conn, params=(area_code, start_str, end_str))
            
        if len(df) == 0:
            return pd.DataFrame(columns=['price_eur_per_mwh'])
        
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
        return df


class PriceFetcher:
    """Handles ENTSO-E API integration with database caching."""
    
    def __init__(self, api_key: Optional[str] = None, db_path: str = 'price_data.db'):
        """
        Initialize the price fetcher.
        
        Args:
            api_key (str, optional): ENTSO-E API key. If not provided, will try to get from ENTSOE_API_KEY environment variable.
            db_path (str): Path to the SQLite database file
        """
        # Get API key from parameter or environment
        if api_key is None:
            api_key = os.getenv('ENTSOE_API_KEY')
        
        self.api_key = api_key
        self.has_api_access = api_key is not None and api_key.strip() != ''
        
        if self.has_api_access:
            try:
                self.client = EntsoePandasClient(api_key=api_key)
                logger.info("ENTSO-E API client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize ENTSO-E client: {e}")
                self.has_api_access = False
                self.client = None
        else:
            self.client = None
            logger.info("No ENTSO-E API key provided - will use existing database data only")
        
        self.db = PriceDatabase(db_path)
    
    def get_price_data(self, area_code: str, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
        """
        Get electricity price data, using database cache and downloading missing data.
        
        Args:
            area_code (str): Electricity area code (e.g., 'SE_4')
            start_date (pd.Timestamp): Start date
            end_date (pd.Timestamp): End date
            
        Returns:
            pd.DataFrame: Price data with datetime index
        """
        logger.info(f"Getting price data for {area_code} from {start_date.date()} to {end_date.date()}")
        
        # Check what data we already have
        min_date, max_date, count = self.db.get_data_range(area_code)
        if min_date is not None:
            logger.info(f"Database contains {count} records for {area_code} from {min_date.date()} to {max_date.date()}")
        else:
            logger.info(f"No existing data found for {area_code} in database")
        
        # Find missing periods that need to be downloaded
        missing_periods = self.db.get_missing_periods(area_code, start_date, end_date)
        
        # Download missing data if we have API access
        if missing_periods and self.has_api_access:
            for period_start, period_end in missing_periods:
                if period_start <= period_end:  # Valid period
                    logger.info(f"Downloading missing data from {period_start.date()} to {period_end.date()}")
                    try:
                        # Convert to timezone-aware for API call
                        api_start = pd.Timestamp(period_start, tz='Europe/Stockholm')
                        api_end = pd.Timestamp(period_end, tz='Europe/Stockholm')
                        
                        new_data = self.client.query_day_ahead_prices(area_code, start=api_start, end=api_end)
                        
                        # Convert to timezone-naive for storage
                        if hasattr(new_data.index, 'tz') and new_data.index.tz is not None:
                            new_data.index = new_data.index.tz_convert('Europe/Stockholm').tz_localize(None)
                        
                        # Convert Series to proper format if needed
                        if isinstance(new_data, pd.Series):
                            price_series = new_data
                        else:
                            price_series = new_data.iloc[:, 0]
                        
                        # Store in database
                        self.db.store_data(area_code, price_series)
                        
                    except Exception as e:
                        logger.error(f"Failed to download price data for period {period_start.date()} to {period_end.date()}: {e}")
                        # Don't raise - continue with whatever data we have
                        
        elif missing_periods and not self.has_api_access:
            logger.warning(f"Missing data for {len(missing_periods)} periods, but no API key available to fetch it")
            logger.info("To enable automatic data fetching, set ENTSOE_API_KEY environment variable")
        
        # Now query the requested data from database
        prices_df = self.db.query_data(area_code, start_date, end_date)
        
        if len(prices_df) == 0:
            error_msg = f"No price data available for {area_code} in the requested period ({start_date.date()} to {end_date.date()})"
            if not self.has_api_access:
                error_msg += ". Set ENTSOE_API_KEY environment variable to enable automatic data fetching."
            raise ValueError(error_msg)
        
        logger.info(f"Retrieved {len(prices_df)} price records from database")
        return prices_df
