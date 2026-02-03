# Troubleshooting Guide

This document helps resolve common issues when deploying and using the AI Platform locally.

## Table of Contents

1. [SES Lockdown Warning](#ses-lockdown-warning)
2. [Tailwind CDN Warning](#tailwind-cdn-warning)
3. [422 HTTP Errors](#422-http-errors)
4. [Port Configuration Issues](#port-configuration-issues)
5. [Database Connection Errors](#database-connection-errors)
6. [CORS Errors](#cors-errors)

---

## SES Lockdown Warning

### Error Message
```
lockdown-install.js:1 SES Removing unpermitted intrinsics
```

### Cause
This warning comes from **browser extensions** (like MetaMask, crypto wallets, etc.) that use Secure EcmaScript (SES) sandboxing. It is **NOT** from our application code.

### Solution
This warning is **harmless** and can be safely ignored. If you want to verify it's from an extension:

1. Open browser in **Incognito/Private mode** (disables extensions)
2. Test the application
3. The warning should disappear

**No code changes needed** - this is expected behavior when certain browser extensions are installed.

---

## Tailwind CDN Warning

### Error Message
```
cdn.tailwindcss.com should not be used in production. To use Tailwind CSS in production, install it as a PostCSS plugin or use the Tailwind CLI
```

### Cause
Previous versions used the Tailwind CDN (`<script src="https://cdn.tailwindcss.com"></script>`) which is not recommended for production.

### Solution
✅ **FIXED** - The latest version now uses compiled Tailwind CSS:

1. **Production Setup:**
   ```bash
   cd ai_platform
   npm install
   npm run build:css
   ```

2. **Rebuild Docker containers:**
   ```bash
   docker-compose build
   docker-compose up -d
   ```

3. **Verify:** The warning should no longer appear in browser console.

See [TAILWIND_SETUP.md](TAILWIND_SETUP.md) for detailed instructions.

---

## 422 HTTP Errors

### Error Message
```
POST http://localhost:8003/chat/guest_faq/stream 422 (Unprocessable Entity)
POST http://localhost:8003/chat/guest_faq 422 (Unprocessable Entity)
```

### Possible Causes

1. **Port Mismatch** - Connecting to wrong port
2. **Request Validation Failure** - Invalid request payload
3. **Service Not Ready** - Backend services still starting
4. **Database Connection Issues** - Database not accessible

### Solutions

#### 1. Check Port Configuration

The default gateway port is **8000**, not 8003. Verify your port settings:

```bash
# Check docker-compose.yml
cat ai_platform/docker-compose.yml | grep GATEWAY_PORT

# Check running containers
docker ps | grep gateway
```

**Fix port in your environment:**

```bash
# In .env or docker-compose.yml
GATEWAY_PORT=8000  # Default port
```

**Or update Chat.html baseUrl:**
```javascript
// Line 526 in Chat.html
baseUrl = 'http://localhost:8003';  // Change to your actual port
```

#### 2. Verify Service Health

Check if services are running and healthy:

```bash
# Check gateway health
curl http://localhost:8000/health

# Check chat-service health
curl http://localhost:8001/health

# Check dependencies (database + LightRAG)
curl http://localhost:8000/health/dependencies
```

Expected healthy response:
```json
{
  "status": "healthy",
  "service": "gateway",
  "chat_service": "connected"
}
```

#### 3. Check Database Connection

422 errors can occur if the database is not accessible:

```bash
# View chat-service logs
docker logs chat-service

# Look for these error messages:
# - "DATABASE_URL environment variable is not set"
# - "Database connection test failed"
# - "Failed to initialize database connection"
```

**Fix:** Ensure `DATABASE_URL` is set in docker-compose.yml or .env:

```bash
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname
```

#### 4. Check Request Payload

The chat endpoint expects this format:

```json
{
  "message": "Your message here",
  "session_id": "optional-uuid-here",
  "use_shared_context": true,
  "user_data": {},
  "from_suggestion": false
}
```

Test with curl:

```bash
curl -X POST http://localhost:8000/chat/guest_faq \
  -H "Content-Type: application/json" \
  -d '{
    "message": "سلام",
    "use_shared_context": true
  }'
```

#### 5. Restart Services

If all else fails, restart the containers:

```bash
cd ai_platform
docker-compose down
docker-compose up -d

# Wait for services to be healthy (30 seconds)
sleep 30

# Check health
curl http://localhost:8000/health
```

---

## Port Configuration Issues

### Problem
Services accessible on unexpected ports (e.g., 8003 instead of 8000).

### Default Ports

- **Gateway:** 8000 (configurable via `GATEWAY_PORT`)
- **Chat Service:** 8001
- **Database:** 5432 (if using local PostgreSQL)

### Configuration

**docker-compose.yml:**
```yaml
services:
  gateway:
    ports:
      - "${GATEWAY_PORT:-8000}:8000"  # Host:Container
```

**Environment variable (.env):**
```bash
GATEWAY_PORT=8000  # Change host port if needed
```

### Port Conflicts

If port 8000 is already in use:

```bash
# Check what's using port 8000
sudo lsof -i :8000

# Option 1: Stop conflicting service
sudo kill <PID>

# Option 2: Change port
GATEWAY_PORT=8001 docker-compose up -d
```

---

## Database Connection Errors

### Error Messages
```
Database connection test failed
DATABASE_URL is required but not set
asyncpg.exceptions.InvalidPasswordError
```

### Solutions

1. **Set DATABASE_URL:**
   ```bash
   # In .env or docker-compose.yml environment section
   DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
   ```

2. **Verify database is accessible:**
   ```bash
   # Test connection with psql
   psql "postgresql://user:pass@host:5432/dbname"

   # Or use Python
   python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('postgresql://user:pass@host:5432/dbname'))"
   ```

3. **Check database host:**
   - Local development: `localhost` or `127.0.0.1`
   - Docker containers: Use service name (e.g., `db`) or container IP
   - Remote database: Use public IP address

4. **Common mistakes:**
   ```bash
   # ❌ Wrong - missing asyncpg driver
   DATABASE_URL=postgresql://user:pass@host:5432/dbname

   # ✅ Correct - includes asyncpg driver
   DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
   ```

---

## CORS Errors

### Error Message
```
Access to fetch at 'http://localhost:8000/chat/guest_faq' from origin 'http://localhost:3000' has been blocked by CORS policy
```

### Solution

CORS is already enabled in the gateway with `allow_origins=["*"]`. If you still get CORS errors:

1. **Check if request is going through gateway:**
   - Gateway (port 8000) ✅ Has CORS enabled
   - Chat-service (port 8001) ❌ Direct access may not have CORS

2. **Always use gateway URL:**
   ```javascript
   // ✅ Correct - goes through gateway
   baseUrl = 'http://localhost:8000';

   // ❌ Wrong - bypasses gateway, no CORS
   baseUrl = 'http://localhost:8001';
   ```

3. **For file:// origins:**
   The gateway allows `file://` origins. If serving from file system, ensure JavaScript uses gateway URL.

---

## Still Having Issues?

1. **Check logs:**
   ```bash
   docker-compose logs gateway
   docker-compose logs chat-service
   ```

2. **Restart services:**
   ```bash
   docker-compose restart
   ```

3. **Rebuild containers:**
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

4. **Test with minimal setup:**
   ```bash
   # Test gateway only
   curl http://localhost:8000/health

   # Test chat-service only
   curl http://localhost:8001/health

   # Test full flow
   curl -X POST http://localhost:8000/chat/guest_faq \
     -H "Content-Type: application/json" \
     -d '{"message": "test"}'
   ```

5. **Check system resources:**
   ```bash
   # Ensure Docker has enough resources
   docker stats

   # Check disk space
   df -h
   ```

---

## Quick Fixes Summary

| Issue | Quick Fix |
|-------|-----------|
| SES warning | Ignore - from browser extensions |
| Tailwind CDN warning | Run `npm run build:css` and rebuild |
| 422 errors | Check port (8000 not 8003), verify health endpoints |
| Port conflicts | Change `GATEWAY_PORT` in .env |
| Database errors | Set `DATABASE_URL` with `postgresql+asyncpg://` |
| CORS errors | Use gateway port (8000), not chat-service (8001) |

---

## Environment Checklist

Before deploying, verify:

- [ ] `DATABASE_URL` is set with `postgresql+asyncpg://` driver
- [ ] Tailwind CSS is compiled: `npm run build:css`
- [ ] Port 8000 is available (or GATEWAY_PORT is set)
- [ ] Docker containers are healthy: `docker ps`
- [ ] Health endpoints respond: `curl http://localhost:8000/health`
- [ ] Database is accessible: `curl http://localhost:8000/health/dependencies`

---

For more help, check:
- [TAILWIND_SETUP.md](TAILWIND_SETUP.md) - Tailwind CSS configuration
- [docker-compose.yml](docker-compose.yml) - Service configuration
- [services/gateway/main.py](services/gateway/main.py) - Gateway routing
- [services/chat-service/main.py](services/chat-service/main.py) - Chat service endpoints
