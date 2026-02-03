#!/bin/bash

# AI Platform Local Startup Script
# This script starts the gateway and chat-service without Docker

set -e  # Exit on error

echo "🚀 Starting AI Platform Services Locally"
echo "========================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found!"
    echo ""
    echo "Please create .env file with required configuration:"
    echo "  cp .env.example .env"
    echo "  nano .env  # Edit with your database and API keys"
    echo ""
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL is not set in .env file!"
    echo ""
    echo "Please add to .env:"
    echo "  DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname"
    echo ""
    exit 1
fi

# Check if LITELLM_API_KEY is set
if [ -z "$LITELLM_API_KEY" ]; then
    echo "⚠️  WARNING: LITELLM_API_KEY is not set in .env file!"
    echo "The AI chat will not work without a valid API key."
fi

# Set PYTHONPATH
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Create logs directory
mkdir -p logs

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    pkill -P $$ 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

echo ""
echo "📦 Installing Python dependencies..."
echo "------------------------------------"

# Install chat-service dependencies
cd services/chat-service
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
deactivate
cd ../..

# Install gateway dependencies
cd services/gateway
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
deactivate
cd ../..

echo "✅ Dependencies installed"
echo ""

# Start chat-service
echo "🔧 Starting Chat Service (port 8001)..."
echo "---------------------------------------"
cd services/chat-service
source venv/bin/activate
export PYTHONPATH="$(pwd)/../..:$PYTHONPATH"
uvicorn main:app --host 0.0.0.0 --port 8001 > ../../logs/chat-service.log 2>&1 &
CHAT_PID=$!
deactivate
cd ../..

# Wait for chat-service to start
echo "Waiting for chat-service to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo "✅ Chat service is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Chat service failed to start. Check logs/chat-service.log"
        cat logs/chat-service.log | tail -20
        cleanup
    fi
    sleep 1
    echo -n "."
done
echo ""

# Start gateway
echo ""
echo "🌐 Starting Gateway (port ${GATEWAY_PORT:-8000})..."
echo "---------------------------------------------------"
cd services/gateway
source venv/bin/activate
export PYTHONPATH="$(pwd)/../..:$PYTHONPATH"
export CHAT_SERVICE_URL=http://localhost:8001
uvicorn main:app --host 0.0.0.0 --port ${GATEWAY_PORT:-8000} > ../../logs/gateway.log 2>&1 &
GATEWAY_PID=$!
deactivate
cd ../..

# Wait for gateway to start
echo "Waiting for gateway to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:${GATEWAY_PORT:-8000}/health > /dev/null 2>&1; then
        echo "✅ Gateway is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Gateway failed to start. Check logs/gateway.log"
        cat logs/gateway.log | tail -20
        cleanup
    fi
    sleep 1
    echo -n "."
done
echo ""

# Display status
echo ""
echo "🎉 All services started successfully!"
echo "====================================="
echo ""
echo "📊 Service URLs:"
echo "  - Chat UI:        http://localhost:${GATEWAY_PORT:-8000}/ui"
echo "  - Gateway API:    http://localhost:${GATEWAY_PORT:-8000}/doc"
echo "  - Chat Service:   http://localhost:8001/doc"
echo "  - Health Check:   http://localhost:${GATEWAY_PORT:-8000}/health"
echo ""
echo "📝 Logs:"
echo "  - Chat Service:   tail -f logs/chat-service.log"
echo "  - Gateway:        tail -f logs/gateway.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Keep script running
wait $CHAT_PID $GATEWAY_PID
