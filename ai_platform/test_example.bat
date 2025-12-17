@echo off
REM Test script for chat_agent service using curl commands
REM Make sure the service is running on http://localhost:8001

echo ========================================
echo Chat Agent Service Test Examples
echo ========================================
echo.

echo 1. Testing health endpoint...
curl -X GET http://localhost:8001/health
echo.
echo.

echo 2. Listing available agents...
curl -X GET http://localhost:8001/agents
echo.
echo.

echo 3. Testing default chat agent (no session)...
curl -X POST http://localhost:8001/chat/default ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"Hello, how are you?\", \"session_id\": null, \"use_shared_context\": true}"
echo.
echo.

echo 4. Testing translator agent...
curl -X POST http://localhost:8001/chat/translator ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"Hello world\", \"session_id\": null, \"use_shared_context\": false}"
echo.
echo.

echo Test examples completed!
echo Note: Replace the session_id in step 3 with an actual session_id from a previous response to test session continuity.

