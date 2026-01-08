#!/bin/bash

# Startup script for Alexa Voice Authentication Server

echo "🏠 Alexa Voice Authentication - Home Assistant"
echo "=============================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import flask" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
    echo "✓ Dependencies installed"
    echo ""
fi

# Run tests
echo "Running tests..."
python test_challenge.py
echo ""

# Start the server
echo "=============================================="
echo "Starting Flask server..."
echo "Dashboard: http://localhost:5000"
echo "Health check: http://localhost:5000/health"
echo "Alexa endpoint: /alexa"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=============================================="
echo ""

python server.py
