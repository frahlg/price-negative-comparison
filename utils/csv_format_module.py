#!/usr/bin/env python3
"""
CSV Format Detector Module

This module provides functionality to automatically detect the format of CSV files
containing electricity production data. It uses an LLM (via xAI API) to analyze
the first few rows and determine the best parameters for pandas.read_csv.

Requirements:
- xAI API key (set as environment variable: XAI_API_KEY)
- requests library (pip install requests)

Usage:
    detector = CSVFormatDetector()
    params = detector.detect_format('path/to/file.csv')
    df = pd.read_csv('path/to/file.csv', **params)
"""

import os
import json
import logging
import pandas as pd
import requests
from io import StringIO
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CSVFormatDetector:
    def __init__(self, api_key: Optional[str] = None, model: str = 'grok-3', sample_rows: int = 10):
        """
        Initialize the CSV format detector.
        
        Args:
            api_key: xAI API key (falls back to env var XAI_API_KEY)
            model: LLM model to use (default: grok-4)
            sample_rows: Number of rows to sample for analysis (default: 10)
        """
        self.api_key = api_key or os.environ.get('XAI_API_KEY')
        if not self.api_key:
            logger.error("xAI API key not found in environment or arguments")
            logger.error(f"Environment variables: {list(os.environ.keys())}")
            raise ValueError("xAI API key not provided. Set XAI_API_KEY environment variable or pass as argument.")
        
        logger.info(f"Using API key: {self.api_key[:10]}...")
        self.model = model
        self.sample_rows = sample_rows
        self.endpoint = 'https://api.x.ai/v1/chat/completions'
        
    def _read_sample(self, file_path: str) -> str:
        """
        Read the first N lines from the CSV file.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            str: Sample text content
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = []
                for i in range(self.sample_rows):
                    try:
                        line = next(f)
                        lines.append(line)
                    except StopIteration:
                        break
            sample = ''.join(lines)
            logger.info(f"Sample text ({len(lines)} lines): {sample[:200]}...")
            return sample
        except UnicodeDecodeError:
            logger.info("UTF-8 failed, trying latin1 encoding")
            # Fallback to latin1 for European files
            with open(file_path, 'r', encoding='latin1') as f:
                lines = []
                for i in range(self.sample_rows):
                    try:
                        line = next(f)
                        lines.append(line)
                    except StopIteration:
                        break
            sample = ''.join(lines)
            logger.info(f"Sample text with latin1 ({len(lines)} lines): {sample[:200]}...")
            return sample
        except Exception as e:
            logger.error(f"Error reading file sample: {e}")
            raise
    
    def _call_llm(self, sample_text: str) -> Dict:
        """
        Call xAI API to analyze the CSV sample.
        
        Args:
            sample_text: Sample CSV content
            
        Returns:
            Dict: Parsed detection results
        """
        prompt = f"""
Analyze this CSV file snippet and detect its format. Respond ONLY with a valid JSON object containing these exact keys:

{{
  "separator": "The field delimiter (e.g., ',', ';', '\\t')",
  "decimal": "The decimal separator (e.g., '.', ',')",
  "has_header": true or false,
  "quotechar": "The quote character (e.g., '"', or null if none)",
  "encoding": "File encoding (e.g., 'utf-8', 'latin1')",
  "datetime_column": "Name or index (0-based) of the datetime column (look for words like 'datum', 'tid', 'date', 'time', 'timestamp')",
  "production_column": "Name or index (0-based) of the production column (look for words like 'produktion', 'production', 'kwh', 'mwh', 'export', 'energy')",
  "other_columns": ["List of other column names or indices if relevant"],
  "parse_dates": ["List of columns to parse as dates, usually just the datetime one"],
  "date_format": "Inferred date format if non-standard (e.g., '%Y-%m-%d %H:%M:%S', or null)",
  "notes": "Any additional observations or potential issues"
}}

Be precise. If no header, use 0-based indices for columns. Assume the file is tab-delimited if spaces seem to separate fields. Detect if numbers use comma as decimal (common in Europe). The file likely contains hourly electricity production data.
        
CSV snippet:
{sample_text}
"""
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a CSV format detection expert."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0,
            "stream": False
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            logger.info(f"Making API call to {self.endpoint} with model {self.model}")
            response = requests.post(self.endpoint, json=payload, headers=headers)
            logger.info(f"API response status: {response.status_code}")
            
            response.raise_for_status()
            response_data = response.json()
            
            content = response_data['choices'][0]['message']['content']
            
            logger.info(f"Raw LLM response: {content}")
            
            # Try to extract JSON from the response (in case it's wrapped in markdown)
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]  # Remove ```json
            if content.endswith('```'):
                content = content[:-3]  # Remove ```
            
            # Parse JSON response
            try:
                result = json.loads(content)
                required_keys = {'separator', 'decimal', 'has_header', 'quotechar', 'encoding',
                               'datetime_column', 'production_column', 'other_columns',
                               'parse_dates', 'date_format', 'notes'}
                if not required_keys.issubset(result.keys()):
                    logger.warning(f"LLM response missing some keys. Got: {result.keys()}")
                    # Still continue if we have the essential keys
                    essential_keys = {'separator', 'decimal', 'has_header', 'datetime_column', 'production_column'}
                    if not essential_keys.issubset(result.keys()):
                        logger.error(f"LLM response missing essential keys. Required: {essential_keys}, Got: {result.keys()}")
                        raise ValueError("LLM response missing essential keys")
                
                # Fill in missing optional keys with defaults
                if 'other_columns' not in result:
                    result['other_columns'] = []
                if 'parse_dates' not in result:
                    result['parse_dates'] = [result['datetime_column']]
                if 'date_format' not in result:
                    result['date_format'] = None
                if 'notes' not in result:
                    result['notes'] = ""
                    
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON: {content}")
                logger.error(f"JSON decode error: {e}")
                raise ValueError(f"Invalid JSON from LLM: {e}")
                
        except requests.RequestException as e:
            logger.error(f"API call failed: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response content: {e.response.text}")
            raise RuntimeError(f"xAI API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in LLM call: {e}")
            raise
    
    def detect_format(self, file_path: str) -> Dict:
        """
        Detect CSV format and return pandas.read_csv parameters.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Dict: Parameters for pd.read_csv
        """
        logger.info(f"Detecting format for {file_path}")
        
        try:
            sample = self._read_sample(file_path)
            logger.info(f"Successfully read sample, calling LLM...")
            
            detection = self._call_llm(sample)
            
            logger.info(f"Detection results: {json.dumps(detection, indent=2)}")
            
            # Build pd.read_csv params
            params = {
                'sep': detection['separator'],
                'decimal': detection['decimal'],
                'header': 0 if detection['has_header'] else None,
                'encoding': detection['encoding'],
                'engine': 'python'  # Better for custom separators
            }
            
            # Add quotechar if specified
            if detection.get('quotechar'):
                params['quotechar'] = detection['quotechar']
            
            # Add parse_dates if specified
            if detection.get('parse_dates'):
                params['parse_dates'] = detection['parse_dates']
            
            # Handle date format if specified
            if detection.get('date_format'):
                params['date_format'] = {detection['datetime_column']: detection['date_format']}
            
            # Handle columns selection
            if detection['has_header']:
                # Check if we have mixed column types (int and str)
                dt_col = detection['datetime_column']
                prod_col = detection['production_column']
                
                # If both are strings or both are ints, use them directly
                if (isinstance(dt_col, str) and isinstance(prod_col, str)) or \
                   (isinstance(dt_col, int) and isinstance(prod_col, int)):
                    params['usecols'] = [dt_col, prod_col]
                else:
                    # Mixed types - can't use usecols with pandas, will read all columns
                    logger.warning(f"Mixed column types (dt: {type(dt_col)}, prod: {type(prod_col)}), reading all columns")
            else:
                # If no header, usecols by index
                try:
                    dt_col = int(detection['datetime_column'])
                    prod_col = int(detection['production_column'])
                    params['usecols'] = [dt_col, prod_col]
                except ValueError:
                    logger.warning("Column indices must be integers when no header, skipping usecols")
            
            # Clean None values
            params = {k: v for k, v in params.items() if v is not None}
            
            return params
            
        except Exception as e:
            logger.error(f"Format detection failed: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise
    
    def test_load(self, file_path: str) -> pd.DataFrame:
        """
        Test loading the CSV with detected params.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            pd.DataFrame: Loaded DataFrame
        """
        params = self.detect_format(file_path)
        detection = self._call_llm(self._read_sample(file_path))  # Get detection results again
        df = pd.read_csv(file_path, **params)
        
        # Rename columns for consistency
        if 'header' in params and params['header'] is None:
            df.columns = ['datetime', 'production_kwh']  # Assume order: datetime, production
        else:
            # Find the actual column names from the detection
            datetime_col = detection['datetime_column']
            production_col = detection['production_column']
            
            df = df.rename(columns={
                datetime_col: 'datetime',
                production_col: 'production_kwh'
            })
        
        df['production_kwh'] = pd.to_numeric(df['production_kwh'], errors='coerce')
        df = df.set_index('datetime')
        
        return df

# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Detect CSV format')
    parser.add_argument('--file', required=True, help='Path to CSV file')
    
    args = parser.parse_args()
    
    try:
        detector = CSVFormatDetector()
        params = detector.detect_format(args.file)
        print("\nDetected pandas.read_csv parameters:")
        print(json.dumps(params, indent=2))
        
        # Test load
        df = pd.read_csv(args.file, **params)
        print("\nSample data:")
        print(df.head())
    except Exception as e:
        logger.error(f"Detection failed: {e}")
        exit(1)