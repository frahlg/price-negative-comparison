#!/usr/bin/env python3
"""
AI File Analyzer Module

This module provides functionality to automatically analyze uploaded files (CSV/Excel)
and understand their content using an LLM (via xAI API). It determines:
- File format and appropriate pandas loading parameters
- Data type (production vs consumption)
- Units (kWh, MWh, etc.)
- Time granularity (hourly, daily, etc.)
- Column mapping for datetime and energy values

Requirements:
- xAI API key (set as environment variable: XAI_API_KEY)
- requests library (pip install requests)
- pandas, openpyxl for Excel support

Usage:
    analyzer = AIFileAnalyzer()
    result = analyzer.analyze_file('path/to/file.xlsx')
    df = analyzer.load_data('path/to/file.xlsx', result)
"""

import os
import json
import logging
import pandas as pd
import requests
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AIFileAnalyzer:
    def __init__(self, api_key: Optional[str] = None, model: str = 'grok-3', sample_rows: int = 15):
        """
        Initialize the AI file analyzer.
        
        Args:
            api_key: xAI API key (falls back to env var XAI_API_KEY)
            model: LLM model to use (default: grok-3)
            sample_rows: Number of rows to sample for analysis (default: 15)
        """
        self.api_key = api_key or os.environ.get('XAI_API_KEY')
        if not self.api_key:
            logger.error("xAI API key not found in environment or arguments")
            raise ValueError("xAI API key not provided. Set XAI_API_KEY environment variable or pass as argument.")
        
        logger.info(f"Using API key: {self.api_key[:10]}...")
        self.model = model
        self.sample_rows = sample_rows
        self.endpoint = 'https://api.x.ai/v1/chat/completions'
        
    def _get_file_extension(self, file_path: str) -> str:
        """Get the file extension."""
        return Path(file_path).suffix.lower()
    
    def _read_sample(self, file_path: str) -> Tuple[str, str]:
        """
        Read sample data from CSV or Excel file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple[str, str]: (file_extension, sample_content)
        """
        ext = self._get_file_extension(file_path)
        sample_content = ""
        
        logger.info(f"Reading sample from file: {file_path}")
        logger.info(f"Detected file extension: {ext}")
        
        try:
            if ext == '.csv':
                logger.info("Processing as CSV file")
                # Try different encodings for CSV
                encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
                for encoding in encodings:
                    try:
                        with open(file_path, 'r', encoding=encoding) as f:
                            lines = []
                            for i in range(self.sample_rows):
                                try:
                                    line = next(f)
                                    lines.append(line)
                                except StopIteration:
                                    break
                        sample_content = ''.join(lines)
                        logger.info(f"Successfully read CSV with {encoding} encoding")
                        break
                    except UnicodeDecodeError as e:
                        logger.debug(f"Failed to read with {encoding}: {e}")
                        continue
                        
                if not sample_content:
                    raise ValueError("Could not read CSV file with any supported encoding")
                    
            elif ext in ['.xls', '.xlsx']:
                logger.info(f"Processing as Excel file: {ext}")
                # Read Excel file
                self._detected_sheet_name = None
                self._detected_header_row = 0
                
                try:
                    # Get sheet name info first
                    xl_file = pd.ExcelFile(file_path)
                    self._detected_sheet_name = xl_file.sheet_names[0]
                    logger.info(f"Excel file opened successfully, sheet: {self._detected_sheet_name}")
                    
                    # Try different header positions to find the best one
                    best_header_row = 0
                    best_df = None
                    
                    # Test header positions 0, 1, 2, 3
                    for header_row in [0, 1, 2, 3]:
                        try:
                            df_test = pd.read_excel(file_path, sheet_name=self._detected_sheet_name, 
                                                  header=header_row, nrows=self.sample_rows)
                            
                            # Score this header position based on column quality
                            score = 0
                            
                            # Check for typical energy data column patterns
                            col_names = [str(col).lower() for col in df_test.columns]
                            
                            # Look for datetime columns
                            if any(word in ' '.join(col_names) for word in ['datum', 'date', 'time', 'tid']):
                                score += 10
                            
                            # Look for energy/production columns  
                            if any(word in ' '.join(col_names) for word in ['produktion', 'production', 'kwh', 'mwh', 'energy', 'export']):
                                score += 10
                            
                            # Penalize unnamed columns
                            unnamed_count = sum(1 for col in col_names if 'unnamed' in col)
                            score -= unnamed_count * 3
                            
                            # Check if data looks reasonable (numeric values in potential energy columns)
                            for col in df_test.columns:
                                col_name = str(col).lower()
                                if any(word in col_name for word in ['produktion', 'production', 'kwh', 'mwh', 'energy']):
                                    try:
                                        numeric_count = pd.to_numeric(df_test[col], errors='coerce').notna().sum()
                                        if numeric_count > len(df_test) * 0.7:  # At least 70% numeric
                                            score += 5
                                    except:
                                        pass
                            
                            logger.info(f"Header row {header_row} score: {score}, columns: {df_test.columns.tolist()}")
                            
                            if best_df is None or score > getattr(best_df, '_score', -999):
                                best_df = df_test
                                best_df._score = score
                                best_header_row = header_row
                                
                        except Exception as e:
                            logger.debug(f"Header row {header_row} failed: {e}")
                            continue
                    
                    if best_df is not None:
                        self._detected_header_row = best_header_row
                        sample_content = best_df.to_csv(index=False)
                        logger.info(f"Successfully read Excel file, shape: {best_df.shape}")
                        logger.info(f"Detected sheet name: {self._detected_sheet_name}")
                        logger.info(f"Detected header row: {self._detected_header_row}")
                        logger.info(f"Final columns: {best_df.columns.tolist()}")
                    else:
                        raise ValueError("Could not find suitable header row in Excel file")
                    
                except Exception as e:
                    logger.error(f"Failed to read Excel file: {e}")
                    raise
            else:
                raise ValueError(f"Unsupported file extension: {ext}")
                
            logger.info(f"Sample content preview: {sample_content[:300]}...")
            return ext, sample_content
            
        except Exception as e:
            logger.error(f"Error reading file sample: {e}")
            raise
    
    def _call_llm(self, file_extension: str, sample_content: str, filename: str) -> Dict:
        """
        Call xAI API to analyze the file content.
        
        Args:
            file_extension: File extension (.csv, .xlsx, etc.)
            sample_content: Sample file content
            filename: Original filename for context
            
        Returns:
            Dict: Analysis results
        """
        prompt = f"""
Analyze this {file_extension} file data and provide a comprehensive analysis. The file is named "{filename}".

Respond ONLY with a valid JSON object containing these exact keys:

{{
  "data_type": "Either 'production' or 'consumption' based on the data content",
  "data_description": "Brief description of what the data represents",
  "energy_unit": "The energy unit used (e.g., 'kWh', 'MWh', 'Wh')",
  "time_granularity": "Time granularity (e.g., 'hourly', 'daily', 'monthly', '15min')",
  "datetime_column": "Name or index (0-based) of the datetime/timestamp column",
  "energy_column": "Name or index (0-based) of the main energy value column",
  "other_relevant_columns": ["List of other relevant column names"],
  "pandas_params": {{
    "separator": "Field delimiter for CSV (e.g., ',', ';', '\\t') or null for Excel",
    "decimal": "Decimal separator (e.g., '.', ',')",
    "has_header": true or false,
    "encoding": "File encoding for CSV (e.g., 'utf-8', 'latin1') or null for Excel",
    "sheet_name": "Sheet name for Excel files or null for CSV",
    "parse_dates": ["List of columns to parse as dates"],
    "date_format": "Date format if non-standard (e.g., '%Y-%m-%d %H:%M:%S') or null"
  }},
  "confidence": "High/Medium/Low - your confidence in this analysis",
  "notes": "Any important observations, potential issues, or special handling needed",
  "unit_conversion_needed": "true if unit conversion is needed (e.g., MWh to kWh), false otherwise",
  "conversion_factor": "Multiplication factor to convert to kWh (e.g., 1000 for MWh->kWh) or 1 if no conversion"
}}

Look for these patterns:
- Swedish terms: "Produktion", "Konsumption", "Förbrukning", "Export", "Import"
- English terms: "Production", "Consumption", "Usage", "Export", "Import", "Generation"
- Energy units: kWh, MWh, Wh, kW (instantaneous power)
- Date/time patterns: Various date formats, timestamps
- Typical solar production data: positive values during day hours, zeros at night
- Consumption data: more constant usage patterns

File content sample:
{sample_content}
"""
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an expert in analyzing energy data files. You understand both Swedish and English terminology for solar production and energy consumption data."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,  # Low temperature for consistent analysis
            "stream": False
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            logger.info(f"Making API call to analyze file content")
            response = requests.post(self.endpoint, json=payload, headers=headers)
            logger.info(f"API response status: {response.status_code}")
            
            response.raise_for_status()
            response_data = response.json()
            
            content = response_data['choices'][0]['message']['content']
            logger.info(f"Raw LLM response: {content[:500]}...")
            
            # Clean up the response
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            
            # Parse JSON response
            try:
                result = json.loads(content)
                
                # Validate required keys
                required_keys = {
                    'data_type', 'data_description', 'energy_unit', 'time_granularity',
                    'datetime_column', 'energy_column', 'pandas_params', 'confidence'
                }
                
                if not required_keys.issubset(result.keys()):
                    missing = required_keys - result.keys()
                    logger.error(f"LLM response missing keys: {missing}")
                    raise ValueError(f"Missing required keys: {missing}")
                
                # Fill in optional keys with defaults
                result.setdefault('other_relevant_columns', [])
                result.setdefault('notes', "")
                result.setdefault('unit_conversion_needed', False)
                result.setdefault('conversion_factor', 1)
                
                # Validate pandas_params structure
                if 'pandas_params' not in result or not isinstance(result['pandas_params'], dict):
                    logger.error("Invalid pandas_params structure")
                    raise ValueError("Invalid pandas_params structure")
                
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON response: {content}")
                raise ValueError(f"Invalid JSON from LLM: {e}")
                
        except requests.RequestException as e:
            logger.error(f"API call failed: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response content: {e.response.text}")
            raise RuntimeError(f"xAI API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in LLM call: {e}")
            raise
    
    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze a file and return comprehensive information about its content and format.
        
        Args:
            file_path: Path to the file to analyze
            
        Returns:
            Dict: Complete analysis results
        """
        logger.info(f"Analyzing file: {file_path}")
        
        try:
            # Read sample content
            file_extension, sample_content = self._read_sample(file_path)
            filename = Path(file_path).name
            
            # Get AI analysis
            analysis = self._call_llm(file_extension, sample_content, filename)
            
            # Add file metadata
            analysis['file_path'] = file_path
            analysis['file_extension'] = file_extension
            analysis['filename'] = filename
            
            logger.info(f"Analysis completed. Data type: {analysis['data_type']}, "
                       f"Unit: {analysis['energy_unit']}, "
                       f"Granularity: {analysis['time_granularity']}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"File analysis failed: {e}")
            raise
    
    def load_data(self, file_path: str, analysis: Dict[str, Any]) -> pd.DataFrame:
        """
        Load data from file using the analysis results.
        
        Args:
            file_path: Path to the file
            analysis: Analysis results from analyze_file()
            
        Returns:
            pd.DataFrame: Loaded and processed DataFrame
        """
        logger.info(f"Loading data from {file_path} using analysis results")
        
        try:
            file_extension = analysis['file_extension']
            pandas_params = analysis['pandas_params']
            
            # Build pandas loading parameters
            if file_extension == '.csv':
                load_params = {
                    'sep': pandas_params.get('separator', ','),
                    'decimal': pandas_params.get('decimal', '.'),
                    'encoding': pandas_params.get('encoding', 'utf-8'),
                    'engine': 'python'
                }
                
                if pandas_params.get('has_header'):
                    load_params['header'] = 0
                else:
                    load_params['header'] = None
                    
                if pandas_params.get('parse_dates'):
                    load_params['parse_dates'] = pandas_params['parse_dates']
                    
                if pandas_params.get('date_format'):
                    load_params['date_format'] = pandas_params['date_format']
                
                # Load CSV
                df = pd.read_csv(file_path, **load_params)
                
            elif file_extension in ['.xls', '.xlsx']:
                load_params = {}
                
                # Use the detected sheet name from the _read_sample phase
                if hasattr(self, '_detected_sheet_name'):
                    load_params['sheet_name'] = self._detected_sheet_name
                    logger.info(f"Using detected sheet name: {self._detected_sheet_name}")
                elif pandas_params.get('sheet_name'):
                    load_params['sheet_name'] = pandas_params['sheet_name']
                
                # Use the detected header row
                if hasattr(self, '_detected_header_row'):
                    load_params['header'] = self._detected_header_row
                    logger.info(f"Using detected header row: {self._detected_header_row}")
                elif pandas_params.get('has_header'):
                    load_params['header'] = 0
                else:
                    load_params['header'] = None
                
                # Load Excel
                df = pd.read_excel(file_path, **load_params)
                
                # Parse dates manually for Excel if needed
                if pandas_params.get('parse_dates'):
                    for col in pandas_params['parse_dates']:
                        if col in df.columns:
                            df[col] = pd.to_datetime(df[col], errors='coerce')
            else:
                raise ValueError(f"Unsupported file extension: {file_extension}")
            
            # Process the data according to analysis
            df = self._process_loaded_data(df, analysis)
            
            logger.info(f"Successfully loaded data: {len(df)} rows, "
                       f"date range: {df.index.min()} to {df.index.max()}")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise
    
    def _process_loaded_data(self, df: pd.DataFrame, analysis: Dict[str, Any]) -> pd.DataFrame:
        """
        Process the loaded DataFrame according to the analysis results.
        
        Args:
            df: Raw loaded DataFrame
            analysis: Analysis results
            
        Returns:
            pd.DataFrame: Processed DataFrame with standardized format
        """
        logger.info("Processing loaded data according to analysis")
        
        try:
            # Get column information
            datetime_col = analysis['datetime_column']
            energy_col = analysis['energy_column']
            
            # Handle column references (name vs index)
            if isinstance(datetime_col, int):
                datetime_col = df.columns[datetime_col]
            if isinstance(energy_col, int):
                energy_col = df.columns[energy_col]
            
            # Select relevant columns
            processed_df = df[[datetime_col, energy_col]].copy()
            
            # Set datetime index
            if not pd.api.types.is_datetime64_any_dtype(processed_df[datetime_col]):
                processed_df[datetime_col] = pd.to_datetime(processed_df[datetime_col], errors='coerce')
            
            processed_df = processed_df.set_index(datetime_col)
            
            # Standardize energy column name and convert to numeric
            processed_df.columns = ['production_kwh']  # We'll use this name for both production and consumption
            processed_df['production_kwh'] = pd.to_numeric(processed_df['production_kwh'], errors='coerce')
            
            # Apply unit conversion if needed
            if analysis.get('unit_conversion_needed', False):
                conversion_factor = analysis.get('conversion_factor', 1)
                processed_df['production_kwh'] *= conversion_factor
                logger.info(f"Applied unit conversion factor: {conversion_factor}")
            
            # Remove rows with invalid data
            initial_rows = len(processed_df)
            processed_df = processed_df.dropna()
            if len(processed_df) < initial_rows:
                logger.warning(f"Removed {initial_rows - len(processed_df)} rows with invalid data")
            
            # Add metadata as attributes
            processed_df.attrs['data_type'] = analysis['data_type']
            processed_df.attrs['energy_unit'] = 'kWh'  # Always converted to kWh
            processed_df.attrs['time_granularity'] = analysis['time_granularity']
            processed_df.attrs['original_unit'] = analysis['energy_unit']
            
            logger.info(f"Data processing completed. Final shape: {processed_df.shape}")
            
            return processed_df
            
        except Exception as e:
            logger.error(f"Error processing data: {e}")
            raise

    def get_supported_extensions(self) -> set:
        """Get set of supported file extensions."""
        return {'.csv', '.xls', '.xlsx'}

# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze file format and content')
    parser.add_argument('--file', required=True, help='Path to file to analyze')
    
    args = parser.parse_args()
    
    try:
        analyzer = AIFileAnalyzer()
        
        # Analyze file
        analysis = analyzer.analyze_file(args.file)
        print("\nFile Analysis Results:")
        print(json.dumps(analysis, indent=2))
        
        # Load and preview data
        df = analyzer.load_data(args.file, analysis)
        print(f"\nLoaded DataFrame info:")
        print(f"Shape: {df.shape}")
        print(f"Index: {df.index.name} ({df.index.dtype})")
        print(f"Columns: {list(df.columns)}")
        print(f"Date range: {df.index.min()} to {df.index.max()}")
        print(f"Data type: {df.attrs.get('data_type', 'Unknown')}")
        print(f"Time granularity: {df.attrs.get('time_granularity', 'Unknown')}")
        
        print("\nFirst 5 rows:")
        print(df.head())
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        exit(1)
