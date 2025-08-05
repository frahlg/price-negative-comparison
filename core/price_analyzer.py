#!/usr/bin/env python3
"""
Price Analysis Engine

Core analysis logic for electricity prices and solar production data.
Handles data merging, calculations, and statistical analysis.
"""

import pandas as pd
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PriceAnalyzer:
    """Core analysis engine for price and production data."""
    
    @staticmethod
    def merge_data(prices_df: pd.DataFrame, production_df: pd.DataFrame, eur_sek_rate: float = 11.5) -> pd.DataFrame:
        """
        Merge price and production data on datetime index.
        
        Args:
            prices_df (pd.DataFrame): Price data with datetime index
            production_df (pd.DataFrame): Production data with datetime index
            eur_sek_rate (float): EUR to SEK exchange rate
            
        Returns:
            pd.DataFrame: Merged data with calculated columns
        """
        logger.info("Merging price and production data")
        
        # Merge on datetime index
        merged_df = pd.merge(prices_df, production_df, left_index=True, right_index=True, how='inner')
        
        # Add SEK pricing (convert from EUR/MWh to SEK/kWh)
        merged_df['price_sek_per_kwh'] = (merged_df['price_eur_per_mwh'] * eur_sek_rate) / 1000
        
        # Calculate export value/cost for each hour
        merged_df['export_value_sek'] = merged_df['production_kwh'] * merged_df['price_sek_per_kwh']
        
        # Add daily aggregations
        merged_df['production_daily'] = merged_df.groupby(merged_df.index.date)['production_kwh'].transform('sum')
        merged_df['price_daily_avg'] = merged_df.groupby(merged_df.index.date)['price_eur_per_mwh'].transform('mean')
        merged_df['export_value_daily_sek'] = merged_df.groupby(merged_df.index.date)['export_value_sek'].transform('sum')
        
        logger.info(f"Merged data: {len(merged_df)} rows from {merged_df.index.min()} to {merged_df.index.max()}")
        
        return merged_df
    
    @staticmethod
    def analyze_data(merged_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Perform comprehensive analysis on merged price and production data.
        
        Args:
            merged_df (pd.DataFrame): Merged price and production data
            
        Returns:
            Dict[str, Any]: Analysis results with statistics and insights
        """
        analysis = {}
        
        # Basic statistics
        analysis['period_days'] = (merged_df.index.max() - merged_df.index.min()).days
        analysis['total_hours'] = len(merged_df)
        
        # Price statistics in SEK/kWh (user-friendly format)
        analysis['price_min_sek_kwh'] = merged_df['price_sek_per_kwh'].min()
        analysis['price_max_sek_kwh'] = merged_df['price_sek_per_kwh'].max()
        analysis['price_mean_sek_kwh'] = merged_df['price_sek_per_kwh'].mean()
        analysis['price_median_sek_kwh'] = merged_df['price_sek_per_kwh'].median()
        
        # Keep EUR/MWh for reference (internal use)
        analysis['price_min_eur_mwh'] = merged_df['price_eur_per_mwh'].min()
        analysis['price_max_eur_mwh'] = merged_df['price_eur_per_mwh'].max()
        analysis['price_mean_eur_mwh'] = merged_df['price_eur_per_mwh'].mean()
        analysis['price_median_eur_mwh'] = merged_df['price_eur_per_mwh'].median()
        
        # Production statistics
        analysis['production_total'] = merged_df['production_kwh'].sum()
        analysis['production_mean'] = merged_df['production_kwh'].mean()
        analysis['production_max'] = merged_df['production_kwh'].max()
        analysis['hours_with_production'] = (merged_df['production_kwh'] > 0).sum()
        
        # Negative price analysis
        negative_prices = merged_df[merged_df['price_eur_per_mwh'] < 0]
        analysis['negative_price_hours'] = len(negative_prices)
        analysis['production_during_negative_prices'] = negative_prices['production_kwh'].sum()
        analysis['negative_export_cost_sek'] = negative_prices['export_value_sek'].sum()  # This will be negative
        analysis['negative_export_cost_abs_sek'] = abs(negative_prices['export_value_sek'].sum())  # Absolute cost
        
        if len(negative_prices) > 0:
            analysis['avg_production_during_negative_prices'] = negative_prices['production_kwh'].mean()
            analysis['avg_negative_price_sek_per_kwh'] = negative_prices['price_sek_per_kwh'].mean()
            analysis['min_negative_price_sek_per_kwh'] = negative_prices['price_sek_per_kwh'].min()
        else:
            analysis['avg_production_during_negative_prices'] = 0
            analysis['avg_negative_price_sek_per_kwh'] = 0
            analysis['min_negative_price_sek_per_kwh'] = 0
        
        # Total export value
        analysis['total_export_value_sek'] = merged_df['export_value_sek'].sum()
        analysis['positive_export_value_sek'] = merged_df[merged_df['price_eur_per_mwh'] > 0]['export_value_sek'].sum()
        
        # Correlation analysis
        if merged_df['production_kwh'].var() > 0 and merged_df['price_sek_per_kwh'].var() > 0:
            analysis['price_production_correlation'] = merged_df['production_kwh'].corr(merged_df['price_sek_per_kwh'])
        else:
            analysis['price_production_correlation'] = 0
        
        # Volatility metrics
        analysis['price_volatility_std'] = merged_df['price_sek_per_kwh'].std()
        analysis['price_volatility_cv'] = analysis['price_volatility_std'] / analysis['price_mean_sek_kwh'] if analysis['price_mean_sek_kwh'] != 0 else 0
        
        return analysis
    
    @staticmethod
    def print_analysis(analysis: Dict[str, Any]):
        """Print analysis results in a formatted way."""
        print("\n" + "="*60)
        print("PRICE-PRODUCTION ANALYSIS RESULTS")
        print("="*60)
        
        print(f"\nPERIOD OVERVIEW:")
        print(f"  Period covered: {analysis['period_days']} days")
        print(f"  Total hours of data: {analysis['total_hours']}")
        
        print(f"\nPRICE STATISTICS (SEK/kWh):")
        print(f"  Min price: {analysis['price_min_sek_kwh']:.4f} SEK/kWh ({analysis['price_min_eur_mwh']:.2f} EUR/MWh)")
        print(f"  Max price: {analysis['price_max_sek_kwh']:.4f} SEK/kWh ({analysis['price_max_eur_mwh']:.2f} EUR/MWh)")
        print(f"  Mean price: {analysis['price_mean_sek_kwh']:.4f} SEK/kWh ({analysis['price_mean_eur_mwh']:.2f} EUR/MWh)")
        print(f"  Median price: {analysis['price_median_sek_kwh']:.4f} SEK/kWh ({analysis['price_median_eur_mwh']:.2f} EUR/MWh)")
        print(f"  Price volatility (std): {analysis['price_volatility_std']:.4f} SEK/kWh")
        print(f"  Price volatility (CV): {analysis['price_volatility_cv']:.2%}")
        
        print(f"\nPRODUCTION STATISTICS:")
        print(f"  Total production: {analysis['production_total']:.2f} kWh")
        print(f"  Average hourly production: {analysis['production_mean']:.3f} kWh")
        print(f"  Max hourly production: {analysis['production_max']:.3f} kWh")
        print(f"  Hours with production > 0: {analysis['hours_with_production']}")
        
        print(f"\nCORRELATION ANALYSIS:")
        print(f"  Price-Production correlation: {analysis['price_production_correlation']:.3f}")
        
        print(f"\nNEGATIVE PRICE ANALYSIS:")
        print(f"  Hours with negative prices: {analysis['negative_price_hours']}")
        if analysis['negative_price_hours'] > 0:
            print(f"  Production during negative prices: {analysis['production_during_negative_prices']:.2f} kWh")
            print(f"  Average production during negative prices: {analysis['avg_production_during_negative_prices']:.3f} kWh")
            print(f"  Lowest negative price: {analysis['min_negative_price_sek_per_kwh']:.4f} SEK/kWh")
            print(f"  Average negative price: {analysis['avg_negative_price_sek_per_kwh']:.4f} SEK/kWh")
            print(f"  COST of negative price exports: {analysis['negative_export_cost_abs_sek']:.2f} SEK")
        else:
            print(f"  No negative price periods found")
        
        print(f"\nEXPORT VALUE ANALYSIS:")
        print(f"  Total export value: {analysis['total_export_value_sek']:.2f} SEK")
        print(f"  Positive price export value: {analysis['positive_export_value_sek']:.2f} SEK")
        print(f"  Net export value (after negative costs): {analysis['total_export_value_sek']:.2f} SEK")
        
        print("\n" + "="*60)
    
    @staticmethod
    def get_daily_summary(merged_df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate daily summary statistics.
        
        Args:
            merged_df (pd.DataFrame): Merged hourly data
            
        Returns:
            pd.DataFrame: Daily summary with aggregated metrics
        """
        daily_summary = merged_df.groupby(merged_df.index.date).agg({
            'production_kwh': ['sum', 'mean', 'max'],
            'price_eur_per_mwh': ['mean', 'min', 'max'],
            'price_sek_per_kwh': ['mean', 'min', 'max'],
            'export_value_sek': 'sum'
        }).round(3)
        
        # Flatten column names
        daily_summary.columns = ['_'.join(col).strip() for col in daily_summary.columns]
        
        return daily_summary
