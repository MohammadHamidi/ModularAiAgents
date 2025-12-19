# Coolify Deployment Guide

This guide explains how to deploy the AI Platform to Coolify.

## Architecture

The platform consists of:

- **Gateway Service** (port 8000): Serves UI at `/ui` and forwards API requests to chat-service
- **Chat Service** (port 8001): Handles AI agent conversations and context management
- **PostgreSQL** (port 5432): Database for sessions and context

## Deployment Steps

### 1. Environment Variables

Set these environment variables in Coolify:

#### Gateway Service:

- `CHAT_SERVICE_URL`: Internal URL to chat-service (e.g., `http://chat-service:8001`)

#### Chat Service:

- `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql+asyncpg://user:pass@postgres:5432/ai_platform`)
- `LITELLM_API_KEY`: Your LiteLLM API key
- `LITELLM_BASE_URL`: LiteLLM API base URL (default: `https://api.avalai.ir/v1`)
- `LITELLM_MODEL`: Model name (default: `gemini-2.5-flash-lite-preview-09-2025`)
- `MAX_SESSION_MESSAGES`: Maximum messages per session (default: `30`)
- `SESSION_TTL_SECONDS`: Session TTL in seconds (default: `14400` = 4 hours)
- `LIGHTRAG_BASE_URL`: LightRAG server URL (optional)
- `LIGHTRAG_USERNAME`: LightRAG username (optional)
- `LIGHTRAG_PASSWORD`: LightRAG password (optional)
- `LIGHTRAG_API_KEY_HEADER_VALUE`: LightRAG API key (optional)
- `LIGHTRAG_BEARER_TOKEN`: LightRAG bearer token (optional)

#### PostgreSQL:

- `POSTGRES_DB`: Database name (default: `ai_platform`)
- `POSTGRES_USER`: Database user (default: `user`)
- `POSTGRES_PASSWORD`: Database password (default: `pass`)

### 2. Service Configuration

#### Gateway Service (Main Entry Point)

- **Port**: 8000 (expose this port publicly)
- **Build Context**: Project root directory
- **Dockerfile**: `services/gateway/Dockerfile`
- **Access**: `https://your-domain.com/ui` for the chat interface
- **API**: `https://your-domain.com/chat/{agent_key}` for API calls

#### Chat Service

- **Port**: 8001 (internal only, not exposed)
- **Build Context**: Project root directory
- **Dockerfile**: `services/chat-service/Dockerfile`
- **Depends on**: PostgreSQL

#### PostgreSQL

- **Port**: 5432 (internal only)
- **Image**: `postgres:15`
- **Volumes**: Persistent storage for database

### 3. Network Configuration

In Coolify, ensure:

- Gateway service can reach chat-service (internal network)
- Chat-service can reach PostgreSQL (internal network)
- Gateway service is exposed publicly on port 8000

### 4. Static Files

The gateway automatically serves:

- `/ui` → `Chat.html` (main chat interface)
- `/ui/icon.png` → `Icon.png` (logo)

These files are copied into the gateway Docker image during build.

### 5. API Endpoints

All API endpoints are available through the gateway:

- `GET /health` - Health check
- `GET /agents` - List available agents
- `POST /chat/{agent_key}` - Send message to agent
- `GET /session/{session_id}/context` - Get session context
- `GET /session/{session_id}/user-data` - Get session user data
- `DELETE /session/{session_id}` - Delete session
- `GET /ui` - Chat UI (HTML)

### 6. Frontend Configuration

The `Chat.html` file automatically detects the base URL:

- If served from `/ui`, it uses the same origin for API calls
- API calls go to `/chat/{agent_key}` (forwarded by gateway to chat-service)

### 7. Testing Deployment

1. Check gateway health:

   ```bash
   curl https://your-domain.com/health
   ```

2. Access UI:

   ```
   https://your-domain.com/ui
   ```

3. Test API:
   ```bash
   curl -X POST https://your-domain.com/chat/default \
     -H "Content-Type: application/json" \
     -d '{"message": "سلام", "session_id": null, "use_shared_context": true}'
   ```

## Troubleshooting

### UI not loading

- Check that `Chat.html` and `Icon.png` are in the project root
- Verify gateway service is running and accessible
- Check gateway logs for file path errors

### API calls failing

- Verify `CHAT_SERVICE_URL` environment variable is set correctly
- Check that chat-service is running and healthy
- Verify network connectivity between gateway and chat-service

### Database connection issues

- Verify `DATABASE_URL` is correct
- Check PostgreSQL is running and accessible
- Ensure network connectivity between chat-service and PostgreSQL

## Notes for Coolify

- The gateway service should be the main service exposed publicly
- Use Coolify's internal networking for service-to-service communication
- Set `CHAT_SERVICE_URL` to use the internal service name (e.g., `http://chat-service:8001`)
- PostgreSQL should use Coolify's managed database or a separate database service

## Quick Start for Coolify

1. **Create a new application** in Coolify
2. **Set the build context** to your project root directory
3. **Use the gateway Dockerfile**: `services/gateway/Dockerfile`
4. **Expose port 8000** publicly
5. **Set environment variables** as listed above
6. **Access the UI** at: `https://your-domain.com/ui`

The gateway will automatically:

- Serve `Chat.html` at `/ui`
- Forward all `/chat/*` requests to the chat-service
- Forward all `/session/*` requests to the chat-service
- Serve static assets like `Icon.png` at `/ui/icon.png`
