#!/usr/bin/env python3
"""
Test client for the Price Production Analysis Flask API

Example usage:
    python test_api_client.py
"""

import requests
import json
from pathlib import Path

API_BASE_URL = 'http://127.0.0.1:5000'

def test_health():
    """Test health endpoint."""
    print("Testing health endpoint...")
    response = requests.get(f'{API_BASE_URL}/health')
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_currencies():
    """Test currencies endpoint."""
    print("Testing currencies endpoint...")
    response = requests.get(f'{API_BASE_URL}/currencies')
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_database_info():
    """Test database info endpoint."""
    print("Testing database info endpoint...")
    response = requests.get(f'{API_BASE_URL}/database/info')
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_database_areas():
    """Test database areas endpoint."""
    print("Testing database areas endpoint...")
    response = requests.get(f'{API_BASE_URL}/database/areas')
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_analyze_production(csv_file, area='SE_4', currency='SEK'):
    """Test production analysis endpoint."""
    print(f"Testing analyze endpoint with {csv_file}, area={area}, currency={currency}...")
    
    if not Path(csv_file).exists():
        print(f"File {csv_file} not found!")
        return
    
    with open(csv_file, 'rb') as f:
        files = {'file': f}
        data = {
            'area': area,
            'currency': currency,
            'start_date': '2025-06-01',
            'end_date': '2025-06-30'
        }
        
        response = requests.post(f'{API_BASE_URL}/analyze', files=files, data=data)
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("Analysis Results:")
        print(f"  Period: {result['analysis']['period']['days']} days")
        print(f"  Currency: {result['analysis']['prices']['currency']}")
        print(f"  Price range: {result['analysis']['prices']['min']['display']} to {result['analysis']['prices']['max']['display']}")
        print(f"  Total production: {result['analysis']['production']['total_kwh']} kWh")
        print(f"  Negative price hours: {result['analysis']['negative_prices']['hours_count']}")
        if result['analysis']['negative_prices']['total_cost']:
            print(f"  Negative price cost: {result['analysis']['negative_prices']['total_cost']['value']} {result['analysis']['negative_prices']['total_cost']['currency']}")
        print(f"  Total export value: {result['analysis']['export_value']['total']['value']} {result['analysis']['export_value']['total']['currency']}")
    else:
        print(f"Error: {response.text}")
    print()

def main():
    """Run all tests."""
    print("Price Production Analysis API Test Client")
    print("=" * 50)
    
    try:
        # Test basic endpoints
        test_health()
        test_currencies()
        test_database_info()
        test_database_areas()
        
        # Test analysis with different currencies
        production_file = "Produktion - Solvägen 33a.csv"
        if Path(production_file).exists():
            test_analyze_production(production_file, area='SE_4', currency='SEK')
            test_analyze_production(production_file, area='SE_4', currency='EUR')
            test_analyze_production(production_file, area='SE_4', currency='USD')
        else:
            print(f"Production file {production_file} not found. Skipping analysis tests.")
            print("Available CSV files:")
            for csv_file in Path('.').glob('*.csv'):
                print(f"  {csv_file}")
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to the API server.")
        print("Please make sure the Flask API is running:")
        print("  python flask_api.py")

if __name__ == '__main__':
    main()
