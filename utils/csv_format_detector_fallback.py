#!/usr/bin/env python3
"""
CSV Format Detector Module - Fallback Version

This module provides functionality to automatically detect the format of CSV files
containing electricity production data using traditional parsing methods as fallback.
"""

import os
import json
import logging
import pandas as pd
import csv
from io import StringIO
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CSVFormatDetectorFallback:
    """Fallback CSV format detector using traditional methods."""
    
    def __init__(self, sample_rows: int = 10):
        self.sample_rows = sample_rows
    
    def _read_sample(self, file_path: str) -> str:
        """Read the first N lines from the CSV file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = []
                for i in range(self.sample_rows):
                    try:
                        line = next(f)
                        lines.append(line)
                    except StopIteration:
                        break
            return ''.join(lines)
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin1') as f:
                lines = []
                for i in range(self.sample_rows):
                    try:
                        line = next(f)
                        lines.append(line)
                    except StopIteration:
                        break
            return ''.join(lines)
    
    def _detect_delimiter(self, sample: str) -> str:
        """Detect the field delimiter."""
        lines = sample.strip().split('\n')
        if not lines:
            return ','
        
        first_line = lines[0]
        
        # Count potential delimiters
        delimiters = [';', ',', '\t', '|']
        delimiter_counts = {}
        
        for delim in delimiters:
            count = first_line.count(delim)
            if count > 0:
                delimiter_counts[delim] = count
        
        if delimiter_counts:
            # Return the delimiter with the highest count
            return max(delimiter_counts, key=delimiter_counts.get)
        
        return ','
    
    def _detect_decimal(self, sample: str) -> str:
        """Detect decimal separator."""
        # Look for patterns like "0,000" or "1.23"
        if ',' in sample and sample.count(',') > sample.count('.'):
            # Check if commas are used as decimal separators
            lines = sample.strip().split('\n')[1:3]  # Skip header, check first data rows
            for line in lines:
                if ',' in line:
                    # Split by potential field separator and check each field
                    fields = line.split(';') if ';' in line else line.split(',')
                    for field in fields:
                        field = field.strip('"\'')
                        if ',' in field and field.replace(',', '').replace('.', '').isdigit():
                            return ','
        return '.'
    
    def _detect_quote_char(self, sample: str) -> Optional[str]:
        """Detect quote character."""
        if '"' in sample:
            return '"'
        elif "'" in sample:
            return "'"
        return None
    
    def _detect_header(self, sample: str, delimiter: str) -> bool:
        """Detect if the file has a header."""
        lines = sample.strip().split('\n')
        if len(lines) < 2:
            return True
        
        # Parse first two lines
        try:
            reader = csv.reader(lines[:2], delimiter=delimiter)
            first_row = next(reader)
            second_row = next(reader)
            
            # Check if first row contains text and second row contains numbers
            first_has_text = any(not (cell.strip('"\'').replace(',', '.').replace('-', '').replace(':', '').replace(' ', '').isdigit()) for cell in first_row if cell.strip())
            second_has_numbers = any(cell.strip('"\'').replace(',', '.').replace('-', '').replace(':', '').replace(' ', '').replace('.', '').isdigit() for cell in second_row if cell.strip())
            
            return first_has_text and second_has_numbers
        except:
            return True
    
    def _find_columns(self, sample: str, delimiter: str, has_header: bool) -> Tuple[str, str]:
        """Find datetime and production columns."""
        lines = sample.strip().split('\n')
        if not lines:
            return "0", "1"
        
        if has_header:
            # Parse header and look for column names
            header_line = lines[0]
            try:
                reader = csv.reader([header_line], delimiter=delimiter)
                headers = next(reader)
                
                datetime_col = None
                production_col = None
                
                for i, header in enumerate(headers):
                    header_lower = header.lower().strip('"\'')
                    if any(word in header_lower for word in ['datum', 'date', 'time', 'tid', 'timestamp']):
                        datetime_col = header.strip('"\'')
                    elif any(word in header_lower for word in ['produktion', 'production', 'kwh', 'mwh', 'export', 'energy']):
                        production_col = header.strip('"\'')
                
                if datetime_col and production_col:
                    return datetime_col, production_col
                
                # Fallback to positional
                return headers[0].strip('"\''), headers[1].strip('"\'') if len(headers) > 1 else headers[0].strip('"\'')
            except:
                pass
        
        # No header or detection failed, use indices
        return "0", "1"
    
    def detect_format(self, file_path: str) -> Dict:
        """
        Detect CSV format and return pandas.read_csv parameters.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Dict: Parameters for pd.read_csv
        """
        logger.info(f"Detecting format for {file_path}")
        
        sample = self._read_sample(file_path)
        
        # Detect format components
        delimiter = self._detect_delimiter(sample)
        decimal = self._detect_decimal(sample)
        quote_char = self._detect_quote_char(sample)
        has_header = self._detect_header(sample, delimiter)
        datetime_col, production_col = self._find_columns(sample, delimiter, has_header)
        
        logger.info(f"Detected: sep='{delimiter}', decimal='{decimal}', header={has_header}")
        logger.info(f"Columns: datetime='{datetime_col}', production='{production_col}'")
        
        # Build pandas parameters
        params = {
            'sep': delimiter,
            'decimal': decimal,
            'header': 0 if has_header else None,
            'encoding': 'utf-8',
            'engine': 'python'
        }
        
        if quote_char:
            params['quotechar'] = quote_char
        
        # Add column selection
        if has_header and datetime_col and production_col:
            params['usecols'] = [datetime_col, production_col]
        
        return params
    
    def test_load(self, file_path: str) -> pd.DataFrame:
        """Test loading the CSV with detected params."""
        params = self.detect_format(file_path)
        df = pd.read_csv(file_path, **params)
        
        logger.info(f"Loaded DataFrame shape: {df.shape}")
        logger.info(f"Columns: {list(df.columns)}")
        
        return df

# Test function
def test_detector():
    """Test the format detector with the production file."""
    detector = CSVFormatDetectorFallback()
    
    file_path = "data/samples/Produktion - Solvägen 33a.csv"
    if not os.path.exists(file_path):
        print(f"File {file_path} not found")
        return
    
    try:
        params = detector.detect_format(file_path)
        print("\nDetected parameters:")
        print(json.dumps(params, indent=2))
        
        df = detector.test_load(file_path)
        print(f"\nLoaded {len(df)} rows")
        print("\nFirst few rows:")
        print(df.head())
        
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    test_detector()
