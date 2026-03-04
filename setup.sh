#!/bin/bash
# Installatie script voor Multi-Agent Development System

echo "🚀 Multi-Agent Development System - Setup"
echo "=========================================="
echo ""

# Check Python versie
echo "Checking Python version..."
python3 --version

if [ $? -ne 0 ]; then
    echo "❌ Python 3 is niet geïnstalleerd. Installeer Python 3.9 of hoger."
    exit 1
fi

echo "✅ Python gevonden"
echo ""

# Create virtual environment (optioneel maar aanbevolen)
read -p "Wil je een virtual environment maken? (aanbevolen) [y/N]: " create_venv

if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    
    echo "Activating virtual environment..."
    source venv/bin/activate
    
    echo "✅ Virtual environment aangemaakt en geactiveerd"
    echo ""
fi

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Installatie mislukt"
    exit 1
fi

echo "✅ Dependencies geïnstalleerd"
echo ""

# Setup .env file
if [ ! -f .env ]; then
    echo "Setting up .env file..."
    cp .env.example .env
    echo "✅ .env file aangemaakt"
    echo ""
    echo "⚠️  BELANGRIJK: Voeg je Anthropic API key toe aan .env"
    echo "   1. Ga naar https://console.anthropic.com/settings/keys"
    echo "   2. Revoke je oude key (als je die per ongeluk hebt gedeeld)"
    echo "   3. Maak een nieuwe key aan"
    echo "   4. Edit .env en vul ANTHROPIC_API_KEY in"
    echo ""
else
    echo "✅ .env file bestaat al"
    echo ""
fi

# Create output directories
echo "Creating output directories..."
mkdir -p output/{requirements,code,reviews,devops}
echo "✅ Output directories aangemaakt"
echo ""

echo "=========================================="
echo "✅ Setup compleet!"
echo ""
echo "Volgende stappen:"
echo "1. Edit .env en voeg je API key toe"
echo "2. Run: python main.py"
echo ""
echo "Voor meer info zie: QUICKSTART.md"
echo "Voor voorbeelden: python examples.py"
echo ""

if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo "💡 Tip: Activeer de virtual environment met:"
    echo "   source venv/bin/activate"
    echo ""
fi
