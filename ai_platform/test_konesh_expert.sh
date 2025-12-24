#!/bin/bash

# Test script for Konesh Expert and Orchestrator

echo "🧪 Testing Konesh Expert and Orchestrator"
echo "=========================================="
echo ""

# Base URL - adjust if needed
BASE_URL="http://localhost:8001"

echo "1️⃣ Checking service health..."
curl -s "$BASE_URL/health" | python3 -m json.tool
echo ""
echo ""

echo "2️⃣ Listing available agents..."
curl -s "$BASE_URL/agents" | python3 -m json.tool
echo ""
echo ""

echo "3️⃣ Listing available personas..."
curl -s "$BASE_URL/personas" | python3 -m json.tool
echo ""
echo ""

echo "4️⃣ Checking if konesh_expert is available..."
AGENTS=$(curl -s "$BASE_URL/agents")
if echo "$AGENTS" | grep -q "konesh_expert"; then
    echo "✅ konesh_expert agent is registered"
else
    echo "❌ konesh_expert agent NOT found!"
fi
echo ""
echo ""

echo "5️⃣ Checking if query_konesh tool is available..."
TOOLS=$(curl -s "$BASE_URL/tools")
if echo "$TOOLS" | grep -q "query_konesh"; then
    echo "✅ query_konesh tool is registered"
else
    echo "❌ query_konesh tool NOT found!"
fi
echo ""
echo ""

echo "6️⃣ Testing Konesh Expert directly - Query for خانه category..."
curl -s -X POST "$BASE_URL/chat/konesh_expert" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "چه کنش‌هایی برای خانه هست؟",
    "session_id": "test-konesh-1"
  }' | python3 -m json.tool
echo ""
echo ""

echo "7️⃣ Testing Konesh Expert - Query for specific کنش..."
curl -s -X POST "$BASE_URL/chat/konesh_expert" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "چطور محفل خانگی رو اجرا کنم؟",
    "session_id": "test-konesh-2"
  }' | python3 -m json.tool
echo ""
echo ""

echo "8️⃣ Testing Orchestrator routing - Should route to konesh_expert..."
curl -s -X POST "$BASE_URL/chat/orchestrator" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "کنش‌های مدرسه چیه؟",
    "session_id": "test-orchestrator-1"
  }' | python3 -m json.tool
echo ""
echo ""

echo "9️⃣ Testing Orchestrator routing - Design new کنش..."
curl -s -X POST "$BASE_URL/chat/orchestrator" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "میخوام یک کنش جدید طراحی کنم برای مسجد",
    "session_id": "test-orchestrator-2"
  }' | python3 -m json.tool
echo ""
echo ""

echo "✅ Tests completed!"

