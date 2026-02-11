#!/bin/bash

echo "🚀 Multi-Agent Development System - Web UI Startup"
echo "=================================================="
echo ""

# Check if we're in the right directory
if [ ! -f "backend/main.py" ]; then
    echo "❌ Error: Please run this script from the web-ui directory"
    exit 1
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

# Check for Node
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    echo "📥 Install from: https://nodejs.org/"
    exit 1
fi

# Setup backend
echo "📦 Setting up backend..."
cd backend

if [ ! -d "venv" ]; then
    echo "  Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "  Activating virtual environment..."
source venv/bin/activate

echo "  Installing backend dependencies..."
pip install -q -r requirements.txt

# Check for .env
if [ ! -f "../../.env" ]; then
    echo ""
    echo "⚠️  No .env file found!"
    echo "   Please create web-ui/backend/.env with your ANTHROPIC_API_KEY"
    echo "   Or make sure .env exists in the parent directory"
    echo ""
    exit 1
fi

cd ..

# Setup frontend
echo ""
echo "📦 Setting up frontend..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "  Installing frontend dependencies (this may take a minute)..."
    npm install
fi

cd ..

# Start servers
echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Starting servers..."
echo ""

# Kill any existing processes on these ports
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null

# Start backend
echo "  Starting backend on http://localhost:8000..."
cd backend
source venv/bin/activate
python main.py &
BACKEND_PID=$!
cd ..

# Wait a bit for backend to start
sleep 3

# Start frontend
echo "  Starting frontend on http://localhost:3000..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "=================================================="
echo "✨ Multi-Agent Dev System is running!"
echo ""
echo "🌐 Open your browser to: http://localhost:3000"
echo ""
echo "📡 Backend API: http://localhost:8000"
echo "📡 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all servers"
echo "=================================================="
echo ""

# Wait for Ctrl+C
trap "echo ''; echo '🛑 Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
