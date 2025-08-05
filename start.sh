#!/bin/bash
# Sourceful Energy Price Analysis Tool
# Quick startup script

echo "🔋 Sourceful Energy Price Analysis Tool"
echo "======================================"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env file and add your API keys:"
    echo "   - ENTSO_E_API_TOKEN (get from https://transparency.entsoe.eu/)"
    echo "   - XAI_API_KEY (get from https://console.x.ai/)"
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Start the Flask application
echo "🚀 Starting Sourceful Energy Analysis Tool..."
echo "   Web Interface: http://localhost:5000"
echo "   API Documentation: http://localhost:5000/api/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python app.py
