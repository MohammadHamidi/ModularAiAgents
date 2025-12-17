# Testing Guide for Chat Agent Service

## Prerequisites

1. **Set Environment Variables**: Create a `.env` file in the `ai_platform` directory with:
   ```
   LITELLM_API_KEY=your_actual_api_key_here
   LITELLM_BASE_URL=https://api.avalai.ir/v1
   LITELLM_MODEL=gemini-2.5-flash-lite-preview-09-2025
   ```

   Or export them in your shell before running docker-compose.

## Step 1: Start the Services

From the `ai_platform` directory, start all services:

```bash
docker-compose up
```

Or run in detached mode:
```bash
docker-compose up -d
```

This will start:
- PostgreSQL database (port 5432)
- Chat Service (port 8001)
- Gateway Service (port 8000)

Wait for all services to be ready. You'll see logs indicating services are running.

## Step 2: Test the Service

### Option A: Using Python Test Script (Recommended)

The test script will run comprehensive tests:

```bash
# Install httpx if not already installed
pip install httpx

# Run the test script
python test_chat_agent.py
```

This will test:
- Health endpoint
- Agent listing
- Chat with default agent
- Session continuity
- Translator agent
- Session context

### Option B: Using curl (Manual Testing)

#### Windows (PowerShell):
```powershell
.\test_example.bat
```

#### Linux/Mac:
```bash
chmod +x test_example.sh
./test_example.sh
```

### Option C: Manual curl Commands

**1. Check health:**
```bash
curl http://localhost:8001/health
```

**2. List available agents:**
```bash
curl http://localhost:8001/agents
```

**3. Send a chat message:**
```bash
curl -X POST http://localhost:8001/chat/default \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Hello, how are you?\", \"session_id\": null, \"use_shared_context\": true}"
```

**4. Continue a conversation (use session_id from previous response):**
```bash
curl -X POST http://localhost:8001/chat/default \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"What was my previous message?\", \"session_id\": \"<session_id_from_above>\", \"use_shared_context\": true}"
```

**5. Test translator agent:**
```bash
curl -X POST http://localhost:8001/chat/translator \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Hello world\", \"session_id\": null, \"use_shared_context\": false}"
```

**6. Get session context:**
```bash
curl http://localhost:8001/session/<session_id>/context
```

## Step 3: View Logs

To see service logs:
```bash
docker-compose logs -f chat-service
```

Or view all logs:
```bash
docker-compose logs -f
```

## Step 4: Stop Services

When done testing:
```bash
docker-compose down
```

To also remove volumes (clears database):
```bash
docker-compose down -v
```

## Troubleshooting

1. **Service won't start**: Check that environment variables are set correctly
2. **Database connection errors**: Ensure PostgreSQL container is running and database schema is initialized
3. **API errors**: Verify LITELLM_API_KEY is valid and LITELLM_BASE_URL is correct
4. **Port already in use**: Stop any services using ports 8000, 8001, or 5432

