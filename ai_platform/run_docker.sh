#!/usr/bin/env bash
# Build and run the AI Platform Docker stack.
# Includes: PostgreSQL, Chat Service, Gateway

set -e
cd "$(dirname "$0")"

echo "=== Building and starting AI Platform ==="
echo ""

# Build and start (detached)
docker compose up --build -d

echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Check status
docker compose ps

echo ""
echo "=== Services ==="
echo "Gateway:    http://localhost:8000"
echo "Chat API:   http://localhost:8001"
echo "PostgreSQL: localhost:5432 (user: aiplatform, db: aiplatform)"
echo ""
echo "Test health:  curl http://localhost:8000/health"
echo "Test chat:    curl -X POST http://localhost:8000/chat/guest_faq -H 'Content-Type: application/json' -d '{\"message\": \"سلام!\"}'"
echo ""
echo "To test chain executor: EXECUTOR_MODE=langchain_chain docker compose up -d"
echo ""
