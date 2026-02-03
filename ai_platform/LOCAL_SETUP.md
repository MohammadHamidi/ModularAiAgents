# Local Setup Guide (Without Docker)

This guide helps you run the AI Platform services locally without Docker.

## Prerequisites

- Python 3.11+ installed
- PostgreSQL database (local or remote)
- API key for LiteLLM/OpenRouter
- npm (for Tailwind CSS compilation)

## Quick Start

### 1. Create Environment File

```bash
cd ai_platform
cp .env.example .env
nano .env  # Edit with your configuration
```

**Required variables in .env:**

```bash
# REQUIRED: PostgreSQL database URL
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/ai_platform

# REQUIRED: API key for AI models
LITELLM_API_KEY=sk-your-api-key-here
```

### 2. Compile Tailwind CSS

```bash
cd ai_platform
npm install
npm run build:css
```

This generates `static/css/tailwind.css` which is required for the UI.

### 3. Start Services

```bash
cd ai_platform
./start_local.sh
```

This script will:
- ✅ Check environment variables
- ✅ Create virtual environments
- ✅ Install Python dependencies
- ✅ Start chat-service on port 8001
- ✅ Start gateway on port 8000 (or GATEWAY_PORT from .env)
- ✅ Display service URLs and logs

### 4. Access the UI

Open your browser and go to:
```
http://localhost:8000/ui
```

## Manual Start (Advanced)

If you prefer to start services manually:

### Terminal 1: Chat Service
```bash
cd ai_platform/services/chat-service
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH="$(pwd)/../..:$PYTHONPATH"
export $(grep -v '^#' ../../.env | xargs)
uvicorn main:app --host 0.0.0.0 --port 8001
```

### Terminal 2: Gateway
```bash
cd ai_platform/services/gateway
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH="$(pwd)/../..:$PYTHONPATH"
export $(grep -v '^#' ../../.env | xargs)
export CHAT_SERVICE_URL=http://localhost:8001
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Environment Variables Reference

### Required
- `DATABASE_URL` - PostgreSQL connection string with asyncpg driver
- `LITELLM_API_KEY` - API key for AI model provider

### Optional
- `GATEWAY_PORT` - Gateway port (default: 8000)
- `LITELLM_BASE_URL` - LiteLLM base URL (default: https://openrouter.ai/api/v1)
- `LITELLM_MODEL` - AI model to use (default: google/gemini-2.5-flash-preview-09-2025)
- `LIGHTRAG_BASE_URL` - Knowledge base URL
- `EXECUTOR_MODE` - Executor mode: pydantic_ai or langchain_chain

## Database Setup

### Option 1: Local PostgreSQL

```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib  # Ubuntu/Debian
brew install postgresql  # macOS

# Create database
sudo -u postgres psql
CREATE DATABASE ai_platform;
CREATE USER ai_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE ai_platform TO ai_user;
\q

# Update .env
DATABASE_URL=postgresql+asyncpg://ai_user:your_password@localhost:5432/ai_platform
```

### Option 2: Remote PostgreSQL

If you have a remote PostgreSQL database:

```bash
# In .env
DATABASE_URL=postgresql+asyncpg://user:password@remote-host:5432/dbname
```

### Option 3: SQLite (Not Recommended)

The application requires PostgreSQL with asyncpg. SQLite is not supported.

## Troubleshooting

### Services won't start

1. **Check logs:**
   ```bash
   tail -f logs/chat-service.log
   tail -f logs/gateway.log
   ```

2. **Check DATABASE_URL:**
   ```bash
   # Test database connection
   python3 -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('your_database_url'))"
   ```

3. **Check ports:**
   ```bash
   # See what's using ports 8000/8001
   lsof -i :8000
   lsof -i :8001
   ```

### UI shows "Error connecting to server"

1. **Verify services are running:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8001/health
   ```

2. **Check if Tailwind CSS is compiled:**
   ```bash
   ls -lh static/css/tailwind.css
   # Should show a ~15KB file
   ```

3. **Check browser console:**
   - Open Developer Tools (F12)
   - Look for errors in Console tab
   - Check Network tab for failed requests

### 422 Unprocessable Entity errors

1. **Port mismatch:**
   - Verify you're accessing the correct port (default: 8000)
   - Check GATEWAY_PORT in .env

2. **Database not accessible:**
   ```bash
   curl http://localhost:8000/health/dependencies
   # Should return: {"database":"ok","lightrag":"..."}
   ```

### Permission denied on start_local.sh

```bash
chmod +x start_local.sh
```

## Stopping Services

Press `Ctrl+C` in the terminal where start_local.sh is running, or:

```bash
# Kill all uvicorn processes
pkill -f uvicorn
```

## Development Workflow

1. **Make code changes**
2. **Restart affected service:**
   ```bash
   # Kill and restart
   pkill -f "uvicorn.*chat-service"
   cd services/chat-service && source venv/bin/activate && uvicorn main:app --port 8001
   ```

3. **For Tailwind CSS changes:**
   ```bash
   npm run build:css
   # Or use watch mode during development:
   npm run dev
   ```

## Production Deployment

For production, use Docker instead of this local setup:

```bash
cd ai_platform
docker-compose up -d
```

See [docker-compose.yml](docker-compose.yml) for Docker setup.

## Service URLs

After starting services:

| Service | URL | Description |
|---------|-----|-------------|
| Chat UI | http://localhost:8000/ui | Main chat interface |
| Gateway API Docs | http://localhost:8000/doc | Swagger/OpenAPI docs |
| Chat Service Docs | http://localhost:8001/doc | Chat service API |
| Gateway Health | http://localhost:8000/health | Health check |
| Dependencies Health | http://localhost:8000/health/dependencies | DB + LightRAG status |
| Monitoring Dashboard | http://localhost:8000/monitoring/dashboard | Trace monitoring |

## Next Steps

- Configure your database and API keys in `.env`
- Run `npm run build:css` to compile Tailwind
- Run `./start_local.sh` to start services
- Open http://localhost:8000/ui in your browser
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if you encounter issues
