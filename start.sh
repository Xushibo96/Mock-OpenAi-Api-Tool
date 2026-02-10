#!/bin/bash

# Mock OpenAI Tool - Quick Start Script

set -e

echo "🚀 Mock OpenAI Tool - Quick Start"
echo "=================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.10 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✓ Python version: $PYTHON_VERSION"

# Check if requirements are installed
echo ""
echo "📦 Checking dependencies..."
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "⚠️  Dependencies not found. Installing..."
    pip install -r requirements.txt
else
    echo "✓ Dependencies already installed"
fi

# Start the server
echo ""
echo "🎯 Starting Mock OpenAI Tool..."
echo ""
echo "Access the web interface at: http://localhost:8000"
echo "API endpoint: http://localhost:8000/v1/chat/completions"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python3 -m uvicorn mock_openai_tool.backend.main:app --host 0.0.0.0 --port 8000
