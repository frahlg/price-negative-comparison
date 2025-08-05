#!/usr/bin/env python3
"""
Production Data Loader

Handles loading and processing solar production data from CSV files.
"""

import pandas as pd
import logging
from typing import Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ProductionLoader:
    """Handles loading solar production data from CSV files."""
    
    @staticmethod
    def load_production_data(production_file: str) -> pd.DataFrame:
        """
        Load solar production data from CSV file with auto-detection of format.
        
        Args:
            production_file (str): Path to production CSV file
            
        Returns:
            pd.DataFrame: Production data with datetime index
        """
        logger.info(f"Loading production data from {production_file}")
        
        # Auto-detect separator and decimal
        try:
            # Try semicolon separator first (common in European CSV)
            production_df = pd.read_csv(production_file, sep=';', decimal=',', nrows=5)
            if len(production_df.columns) > 1:
                # Semicolon worked, load full file
                production_df = pd.read_csv(production_file, sep=';', decimal=',')
            else:
                # Try comma separator
                production_df = pd.read_csv(production_file, sep=',', decimal='.')
        except:
            # Fallback to comma separator
            production_df = pd.read_csv(production_file, sep=',', decimal='.')
        
        # Find datetime and production columns
        datetime_cols = [col for col in production_df.columns if any(word in col.lower() for word in ['datum', 'date', 'time', 'tid'])]
        production_cols = [col for col in production_df.columns if any(word in col.lower() for word in ['produktion', 'production', 'kwh', 'mwh', 'power'])]
        
        if not datetime_cols:
            raise ValueError("Could not find datetime column in production file")
        if not production_cols:
            raise ValueError("Could not find production column in production file")
        
        datetime_col = datetime_cols[0]
        production_col = production_cols[0]
        
        logger.info(f"Using datetime column: '{datetime_col}' and production column: '{production_col}'")
        
        # Parse datetime and set as index
        production_df[datetime_col] = pd.to_datetime(production_df[datetime_col])
        production_df = production_df.set_index(datetime_col)
        
        # Keep only production column and rename it
        production_df = production_df[[production_col]].copy()
        production_df.columns = ['production_kwh']
        
        # Convert to numeric
        production_df['production_kwh'] = pd.to_numeric(production_df['production_kwh'], errors='coerce')
        
        logger.info(f"Loaded production data: {len(production_df)} rows from {production_df.index.min()} to {production_df.index.max()}")
        
        return production_df
    
    @staticmethod
    def detect_columns(df: pd.DataFrame) -> Tuple[str, str]:
        """
        Detect datetime and production columns in a DataFrame.
        
        Args:
            df (pd.DataFrame): DataFrame to analyze
            
        Returns:
            Tuple[str, str]: (datetime_column, production_column)
        """
        # Find datetime columns
        datetime_cols = [col for col in df.columns if any(word in col.lower() for word in ['datum', 'date', 'time', 'tid'])]
        
        # Find production columns
        production_cols = [col for col in df.columns if any(word in col.lower() for word in ['produktion', 'production', 'kwh', 'mwh', 'power'])]
        
        if not datetime_cols:
            raise ValueError("Could not find datetime column")
        if not production_cols:
            raise ValueError("Could not find production column")
        
        return datetime_cols[0], production_cols[0]
