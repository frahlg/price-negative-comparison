#!/usr/bin/env python3
"""
Price Production Analysis CLI Tool

Command-line interface for analyzing electricity prices and solar production data.

Usage:
    python main.py [options]
    
Examples:
    python main.py --file production_data.csv --area SE4 --currency SEK
    python main.py --interactive
"""

import argparse
import sys
from pathlib import Path

# Add the parent directory to the path to access modules
sys.path.append(str(Path(__file__).parent.parent))

from cli.cli_analyzer import AnalysisPipeline
from core.negative_price_analysis import analyze_negative_pricing
from core.db_manager import PriceDatabaseManager


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze electricity prices and solar production data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --file production.csv --area SE4 --currency SEK
  %(prog)s --interactive
  %(prog)s --file data.csv --start-date 2024-01-01 --end-date 2024-12-31
        """
    )
    
    parser.add_argument(
        '--file', '-f',
        type=str,
        help='Path to production data CSV file'
    )
    
    parser.add_argument(
        '--area', '-a',
        default='SE4',
        choices=['SE1', 'SE2', 'SE3', 'SE4', 'NO1', 'NO2', 'NO3', 'NO4', 'NO5', 'DK1', 'DK2', 'FI'],
        help='Price area (default: SE4)'
    )
    
    parser.add_argument(
        '--currency', '-c',
        default='SEK',
        choices=['EUR', 'SEK', 'NOK', 'DKK'],
        help='Currency for analysis (default: SEK)'
    )
    
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date for analysis (YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date for analysis (YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Run in interactive mode'
    )
    
    parser.add_argument(
        '--negative-only',
        action='store_true',
        help='Focus analysis on negative price periods only'
    )
    
    parser.add_argument(
        '--db-info',
        action='store_true',
        help='Show database information and exit'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='Output file path for merged data'
    )
    
    args = parser.parse_args()
    
    # Show database info if requested
    if args.db_info:
        db_manager = PriceDatabaseManager()
        info = db_manager.get_database_info()
        print("Database Information:")
        print(f"  Records: {info.get('total_records', 0):,}")
        print(f"  Date range: {info.get('date_range', 'No data')}")
        print(f"  Areas: {', '.join(info.get('areas', []))}")
        return
    
    # Interactive mode
    if args.interactive:
        print("🔌 Price Production Analysis Tool")
        print("=" * 40)
        
        # Get file path
        if not args.file:
            file_path = input("Enter path to production data CSV file: ").strip()
            if not file_path:
                print("Error: File path is required")
                sys.exit(1)
        else:
            file_path = args.file
            
        # Validate file exists
        if not Path(file_path).exists():
            print(f"Error: File '{file_path}' not found")
            sys.exit(1)
            
        print(f"📁 Using file: {file_path}")
        print(f"🌍 Price area: {args.area}")
        print(f"💰 Currency: {args.currency}")
        print()
    
    elif args.file:
        file_path = args.file
        
        # Validate file exists
        if not Path(file_path).exists():
            print(f"Error: File '{file_path}' not found")
            sys.exit(1)
            
    else:
        print("Error: Either --file or --interactive mode is required")
        parser.print_help()
        sys.exit(1)
    
    try:
        # Get currency exchange rate
        currency_rates = {'EUR': 1.0, 'SEK': 11.5, 'NOK': 11.8, 'DKK': 7.46}
        currency_rate = currency_rates.get(args.currency, 11.5)
        
        # Initialize analysis pipeline
        pipeline = AnalysisPipeline()
        
        print("🔍 Analyzing production data...")
        
        # Convert area format (SE4 -> SE_4)
        area_code = args.area.replace('SE', 'SE_').replace('NO', 'NO_').replace('DK', 'DK_')
        
        # Run analysis
        if args.negative_only:
            print("📊 Running negative price analysis...")
            results = analyze_negative_pricing(file_path)
        else:
            print("📊 Running full production analysis...")
            merged_df, analysis = pipeline.run_analysis(
                production_file=file_path,
                area_code=area_code,
                start_date=args.start_date,
                end_date=args.end_date,
                output_file=args.output,
                eur_sek_rate=currency_rate
            )
            
        print("✅ Analysis completed successfully!")
        if args.output:
            print(f"📄 Results saved to: {args.output}")
            
    except KeyboardInterrupt:
        print("\n⚠️  Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
