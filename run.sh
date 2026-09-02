#!/bin/bash
# Quick run script for Ekkaa HRMS

echo "🚀 Starting Ekkaa HRMS..."

# Check venv
if [ ! -d "venv" ]; then
  echo "Creating venv..."
  python3 -m venv venv
fi

source venv/bin/activate

echo "Installing deps..."
pip install -r requirements.txt -q

# Check .env
if [ ! -f ".env" ]; then
  echo "⚠️  .env not found, copying from .env.example (will run in MOCK mode)"
  cp .env.example .env
fi

echo "Starting Flask on port 5000..."
python app.py
