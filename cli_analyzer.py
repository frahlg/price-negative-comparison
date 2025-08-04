#!/usr/bin/env python3
"""
CLI Price Analysis Tool

Command-line interface for running price and production analysis.
"""

import argparse
import pandas as pd
import logging
from pathlib import Path
from price_fetcher import PriceFetcher
from production_loader import ProductionLoader
from price_analyzer import PriceAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """Complete analysis pipeline combining fetching, loading, and analysis."""
    
    def __init__(self, db_path: str = 'price_data.db'):
        """Initialize the analysis pipeline."""
        self.price_fetcher = PriceFetcher(db_path=db_path)
        self.production_loader = ProductionLoader()
        self.analyzer = PriceAnalyzer()
    
    def run_analysis(self, production_file: str, area_code: str, start_date=None, end_date=None, 
                    output_file=None, eur_sek_rate: float = 11.5):
        """
        Run complete analysis pipeline.
        
        Args:
            production_file (str): Path to production CSV file
            area_code (str): Electricity area code
            start_date (str, optional): Start date (YYYY-MM-DD)
            end_date (str, optional): End date (YYYY-MM-DD)
            output_file (str, optional): Output file path
            eur_sek_rate (float): EUR to SEK exchange rate
        """
        # Load production data first to determine date range if not provided
        production_df = self.production_loader.load_production_data(production_file)
        
        # Set date range - use full production timeframe by default
        production_start = pd.Timestamp(production_df.index.min(), tz='Europe/Stockholm')
        production_end = pd.Timestamp(production_df.index.max(), tz='Europe/Stockholm')
        
        # Only limit timeframe if explicitly provided
        if start_date is not None:
            start_date = pd.Timestamp(start_date, tz='Europe/Stockholm')
            if start_date > production_start:
                production_df = production_df[production_df.index >= start_date.tz_localize(None)]
                logger.info(f"Limiting production data to start from: {start_date.date()}")
        else:
            start_date = production_start
            
        if end_date is not None:
            end_date = pd.Timestamp(end_date, tz='Europe/Stockholm')
            if end_date < production_end:
                production_df = production_df[production_df.index <= end_date.tz_localize(None)]
                logger.info(f"Limiting production data to end at: {end_date.date()}")
        else:
            end_date = production_end
        
        logger.info(f"Analysis period: {start_date.date()} to {end_date.date()}")
        
        # Get price data for the determined timeframe
        prices_df = self.price_fetcher.get_price_data(area_code, start_date, end_date)
        
        # Merge data
        merged_df = self.analyzer.merge_data(prices_df, production_df, eur_sek_rate)
        
        # Perform analysis
        analysis = self.analyzer.analyze_data(merged_df)
        
        # Print results
        self.analyzer.print_analysis(analysis)
        
        # Save merged data if output file specified
        if output_file:
            logger.info(f"Saving merged data to {output_file}")
            merged_df.to_csv(output_file)
        
        return merged_df, analysis


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='Analyze electricity prices and solar production data')
    parser.add_argument('--production', required=True, help='Path to production CSV file')
    parser.add_argument('--area', required=True, help='Electricity area code (e.g., SE_4)')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD) - if not provided, uses full production data range')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD) - if not provided, uses full production data range')
    parser.add_argument('--output', help='Output file path for merged data')
    parser.add_argument('--db-path', default='price_data.db', help='Path to the price database file (default: price_data.db)')
    parser.add_argument('--eur-sek-rate', type=float, default=11.5, help='EUR to SEK exchange rate (default: 11.5)')
    
    args = parser.parse_args()
    
    # Create analysis pipeline
    pipeline = AnalysisPipeline(db_path=args.db_path)
    
    # Run analysis
    try:
        merged_df, analysis = pipeline.run_analysis(
            production_file=args.production,
            area_code=args.area,
            start_date=args.start_date,
            end_date=args.end_date,
            output_file=args.output,
            eur_sek_rate=args.eur_sek_rate
        )
        
        print(f"\nAnalysis completed successfully!")
        if args.output:
            print(f"Merged data saved to: {args.output}")
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
