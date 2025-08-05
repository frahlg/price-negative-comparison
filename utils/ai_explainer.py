#!/usr/bin/env python3
"""
AI Analysis Explainer Module

This module provides functionality to generate plain text explanations of 
electricity production and price analysis results using an LLM (via xAI API).

Requirements:
- xAI API key (set as environment variable: XAI_API_KEY)
- requests library (pip install requests)

Usage:
    explainer = AIExplainer()
    explanation = explainer.explain_analysis(analysis_data, metadata)
"""

import os
import json
import logging
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AIExplainer:
    def __init__(self, api_key: Optional[str] = None, model: str = 'grok-3'):
        """
        Initialize the AI explainer.
        
        Args:
            api_key: xAI API key (falls back to env var XAI_API_KEY)
            model: LLM model to use (default: grok-3)
        """
        self.api_key = api_key or os.environ.get('XAI_API_KEY')
        if not self.api_key:
            logger.error("xAI API key not found in environment or arguments")
            raise ValueError("xAI API key not provided. Set XAI_API_KEY environment variable or pass as argument.")
        
        logger.info(f"Using API key: {self.api_key[:10]}...")
        self.model = model
        self.endpoint = 'https://api.x.ai/v1/chat/completions'
        
    def _call_llm(self, analysis_data: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """
        Call xAI API to generate analysis explanation.
        
        Args:
            analysis_data: The analysis results
            metadata: Analysis metadata
            
        Returns:
            str: Plain text explanation
        """
        
        # Prepare a clean summary of the data for the LLM
        summary = {
            "metadata": {
                "file_name": metadata.get('file_name', 'N/A'),
                "area_code": metadata.get('area_code', 'N/A'),
                "currency": metadata.get('currency', 'N/A'),
                "currency_rate": metadata.get('currency_rate', 1.0),
                "data_points": metadata.get('data_points', 0),
                "period": f"{metadata.get('start_date', 'N/A')} to {metadata.get('end_date', 'N/A')}"
            },
            "analysis": {
                "period_days": analysis_data.get('period_days', 0),
                "total_hours": analysis_data.get('total_hours', 0),
                "production_total": analysis_data.get('production_total', 0),
                "production_mean": analysis_data.get('production_mean', 0),
                "production_max": analysis_data.get('production_max', 0),
                "hours_with_production": analysis_data.get('hours_with_production', 0),
                "price_min_eur_mwh": analysis_data.get('price_min_eur_mwh', 0),
                "price_max_eur_mwh": analysis_data.get('price_max_eur_mwh', 0),
                "price_mean_eur_mwh": analysis_data.get('price_mean_eur_mwh', 0),
                "price_median_eur_mwh": analysis_data.get('price_median_eur_mwh', 0),
                "negative_price_hours": analysis_data.get('negative_price_hours', 0),
                "negative_price_percentage": analysis_data.get('negative_price_percentage', 0),
                "production_during_negative_prices": analysis_data.get('production_during_negative_prices', 0),
                "production_percentage_negative_prices": analysis_data.get('production_percentage_negative_prices', 0),
                "negative_export_cost_abs_sek": analysis_data.get('negative_export_cost_abs_sek', 0),
                "total_export_value_sek": analysis_data.get('total_export_value_sek', 0),
                "positive_export_value_sek": analysis_data.get('positive_export_value_sek', 0),
                "worst_negative_price_eur_mwh": analysis_data.get('worst_negative_price_eur_mwh'),
                "worst_negative_price_datetime": analysis_data.get('worst_negative_price_datetime')
            }
        }
        
        prompt = f"""
Du är en galen energiguru som kastar sanningar som blixtar och förklarar elmarknadens kaos med vild passion för solpanelhjältar! Analysera datan om elproduktion och priser som en tornado av insikter, ge en kort, max en paragraf-sammanfattning på svenska som exploderar av praktiska råd: tidsperioden som ett äventyr, totalproduktionen som en skattkista, finansiell prestanda med exportvärde och snittpris som vinstlotter, negativa prisers förbannelse (om de dyker upp – kostnad, tidpunkt och hur det suger livet ur plånboken), plus en vansinnig insikt om mönster eller optimeringar som får dig att skrika "UPPGRADERA NU!". Håll tonen konversationell, galet entusiastisk utan teknobabbel, börja rakt på sak med förklaringen – och viska subtilt att Sourceful Energy är den ultimata räddningen, typ genom att nämna hur en Zap skulle fixa allt som ett magiskt svärd mot energikaoset.
Data:
{json.dumps(summary, indent=2)}

"""
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Du är en hjälpsam energianalytiker som förklarar komplex elmarknadsdata på enkelt sätt."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
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
            
            logger.info(f"Generated explanation length: {len(content)} characters")
            
            return content.strip()
                
        except requests.RequestException as e:
            logger.error(f"API call failed: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response content: {e.response.text}")
            raise RuntimeError(f"xAI API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in LLM call: {e}")
            raise
    
    def explain_analysis(self, analysis_data: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """
        Generate a plain text explanation of the analysis results.
        
        Args:
            analysis_data: The analysis results dictionary
            metadata: Analysis metadata dictionary
            
        Returns:
            str: Plain text explanation of the analysis
        """
        logger.info("Generating AI explanation of analysis results")
        
        try:
            explanation = self._call_llm(analysis_data, metadata)
            logger.info("Successfully generated analysis explanation")
            return explanation
            
        except Exception as e:
            logger.error(f"Failed to generate explanation: {e}")
            # Return a fallback explanation if AI fails
            fallback = self._generate_fallback_explanation(analysis_data, metadata)
            logger.info("Using fallback explanation")
            return fallback
    
    def _generate_fallback_explanation(self, analysis_data: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """
        Generate a basic fallback explanation if AI call fails.
        
        Args:
            analysis_data: The analysis results dictionary
            metadata: Analysis metadata dictionary
            
        Returns:
            str: Basic fallback explanation
        """
        currency = metadata.get('currency', 'SEK')
        currency_rate = metadata.get('currency_rate', 1.0)
        
        # Convert key values to display currency
        total_value = analysis_data.get('total_export_value_sek', 0) * (currency_rate / 11.5)
        neg_cost = analysis_data.get('negative_export_cost_abs_sek', 0) * (currency_rate / 11.5)
        
        explanation = f"""
Your solar panels produced {analysis_data.get('production_total', 0):.1f} kWh over {analysis_data.get('period_days', 0)} days in the {metadata.get('area_code', 'N/A')} electricity area. The total export value was {total_value:.2f} {currency}.

During this period, electricity prices ranged from {analysis_data.get('price_min_eur_mwh', 0):.2f} to {analysis_data.get('price_max_eur_mwh', 0):.2f} EUR/MWh, with an average of {analysis_data.get('price_mean_eur_mwh', 0):.2f} EUR/MWh.

"""
        
        neg_hours = analysis_data.get('negative_price_hours', 0)
        if neg_hours > 0:
            explanation += f"There were {neg_hours} hours with negative electricity prices, costing you approximately {neg_cost:.2f} {currency} when your panels were producing during these periods. This represents {analysis_data.get('production_percentage_negative_prices', 0):.1f}% of your total production."
        else:
            explanation += "Fortunately, there were no negative electricity prices during your production periods, which is good news for your returns."
        
        explanation += f"\n\nYour panels were most productive during peak hours, with a maximum hourly production of {analysis_data.get('production_max', 0):.2f} kWh. On average, they produced {analysis_data.get('production_mean', 0):.2f} kWh per hour when generating electricity."
        
        return explanation.strip()

# Example usage
if __name__ == "__main__":
    # Test with sample data
    sample_analysis = {
        "period_days": 30,
        "total_hours": 720,
        "production_total": 450.5,
        "production_mean": 2.1,
        "production_max": 8.2,
        "negative_price_hours": 12,
        "total_export_value_sek": 850.0,
        "negative_export_cost_abs_sek": 45.0
    }
    
    sample_metadata = {
        "area_code": "SE_4",
        "currency": "SEK",
        "currency_rate": 11.5,
        "file_name": "test_production.csv"
    }
    
    try:
        explainer = AIExplainer()
        explanation = explainer.explain_analysis(sample_analysis, sample_metadata)
        print("Generated Explanation:")
        print("=" * 50)
        print(explanation)
    except Exception as e:
        print(f"Error: {e}")
