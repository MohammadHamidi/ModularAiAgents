# Quick Start - Testing Chat Agent

## 1. Start Services

```bash
cd ai_platform
docker-compose up -d
```

Wait a few seconds for services to initialize. Check logs:
```bash
docker-compose logs -f
```

Press Ctrl+C to stop watching logs (services continue running).

## 2. Quick Test

### Test Health Endpoint:
```powershell
curl http://localhost:8001/health
```

### Test Chat Agent (Python):
```powershell
python test_chat_agent.py
```

### Or use the batch script:
```powershell
.\test_example.bat
```

## 3. Manual Test with curl

**Send a chat message:**
```powershell
curl -X POST http://localhost:8001/chat/default -H "Content-Type: application/json" -d '{\"message\": \"Hello!\", \"session_id\": null}'
```

## 4. Stop Services

```bash
docker-compose down
```

