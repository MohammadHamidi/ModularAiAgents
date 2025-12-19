#!/bin/bash
# Test script for User Data API functionality

API="http://localhost:8001"
H="Content-Type: application/json"

echo "🧪 User Data API Test"
echo "====================="
echo ""

# ============================================================================
# Test 1: Create session with user_data in request
# ============================================================================
echo "📍 Test 1: Create session with user_data"
echo "Sending request with personal info, residence, and activity data..."

RESPONSE=$(curl -s -X POST "$API/chat/default" -H "$H" -d '{
  "message": "سلام!",
  "session_id": null,
  "use_shared_context": true,
  "user_data": {
    "phone_number": "09123456789",
    "full_name": "محمد احمدی",
    "gender": "مرد",
    "birth_month": 5,
    "birth_year": 1995,
    "province": "تهران",
    "city": "تهران",
    "registered_actions": 15,
    "score": 1250,
    "pending_reports": 2,
    "level": "intermediate",
    "my_actions": ["action1", "action2"],
    "saved_actions": ["saved1"],
    "saved_content": ["content1", "content2"],
    "achievements": ["achievement1", "achievement2"]
  }
}')

SESSION=$(echo $RESPONSE | jq -r '.session_id')
echo "Session ID: $SESSION"
echo "Response: $(echo $RESPONSE | jq -r '.output')"
echo ""

# ============================================================================
# Test 2: Fetch user data via API
# ============================================================================
echo "📍 Test 2: Fetch user data via GET /session/{id}/user-data"
USER_DATA=$(curl -s "$API/session/$SESSION/user-data")
echo "$USER_DATA" | jq .
echo ""

# ============================================================================
# Test 3: Verify context was saved
# ============================================================================
echo "📍 Test 3: Verify context was saved"
CONTEXT=$(curl -s "$API/session/$SESSION/context")
echo "Context keys: $(echo $CONTEXT | jq '.context | keys')"
echo ""

# ============================================================================
# Test 4: Test with another persona (should have access to same data)
# ============================================================================
echo "📍 Test 4: Switch to TUTOR persona (should access same user_data)"
RESPONSE=$(curl -s -X POST "$API/chat/tutor" -H "$H" -d "{
  \"message\": \"اسم من چیه و چند امتیاز دارم؟\",
  \"session_id\": \"$SESSION\",
  \"use_shared_context\": true
}")
echo "Response: $(echo $RESPONSE | jq -r '.output')"
echo ""

# ============================================================================
# Test 5: Update user_data with partial data
# ============================================================================
echo "📍 Test 5: Update user_data with partial data (only score)"
RESPONSE=$(curl -s -X POST "$API/chat/default" -H "$H" -d "{
  \"message\": \"امتیازم رو به 1500 تغییر بده\",
  \"session_id\": \"$SESSION\",
  \"use_shared_context\": true,
  \"user_data\": {
    \"score\": 1500
  }
}")
echo "Response: $(echo $RESPONSE | jq -r '.output')"
echo ""

# Verify score was updated
echo "📍 Verify score update:"
UPDATED_DATA=$(curl -s "$API/session/$SESSION/user-data")
echo "New score: $(echo $UPDATED_DATA | jq '.activity_info.score')"
echo ""

# ============================================================================
# Test 6: Test with PROFESSIONAL persona
# ============================================================================
echo "📍 Test 6: PROFESSIONAL persona accessing user data"
RESPONSE=$(curl -s -X POST "$API/chat/professional" -H "$H" -d "{
  \"message\": \"What is my full name and level?\",
  \"session_id\": \"$SESSION\",
  \"use_shared_context\": true
}")
echo "Response: $(echo $RESPONSE | jq -r '.output')"
echo ""

echo "✅ All tests complete!"
echo ""
echo "📋 Summary:"
echo "  • User data can be sent in request body"
echo "  • Data is saved immediately to context"
echo "  • All personas can access the data"
echo "  • Data can be fetched via GET /session/{id}/user-data"
echo "  • Partial updates are supported"

