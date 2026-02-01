#!/usr/bin/env bash
# Integration test for chain-based executor.
# Run with EXECUTOR_MODE=langchain_chain to test chain mode.
# Prerequisites: Chat service running, LITELLM_API_KEY set.

set -e
BASE_URL="${CHAT_SERVICE_URL:-http://localhost:8001}"

echo "=== Testing Chain Executor (EXECUTOR_MODE=langchain_chain) ==="
echo "Chat service URL: $BASE_URL"
echo ""

# Health check - verify executor mode
echo "1. Health check..."
HEALTH=$(curl -s "$BASE_URL/health")
echo "$HEALTH" | python3 -m json.tool
EXECUTOR=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('executor_mode','?'))" 2>/dev/null || echo "?")
echo "Executor mode: $EXECUTOR"
echo ""

# Chat request to guest_faq
echo "2. Chat request to guest_faq..."
RESP=$(curl -s -X POST "$BASE_URL/chat/guest_faq" \
  -H "Content-Type: application/json" \
  -d '{"message": "سلام! سفیر چیه؟", "use_shared_context": true}')
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"
OUTPUT=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('output','')[:200])" 2>/dev/null || echo "")
echo "Output preview: ${OUTPUT}..."
echo ""

echo "=== Test complete ==="
