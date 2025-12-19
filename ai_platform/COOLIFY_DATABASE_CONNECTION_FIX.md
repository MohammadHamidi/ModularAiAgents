# Database Connection Error Fix

## Problem

The chat-service is failing with a database connection error:
```
socket.gaierror: [Errno -3] Temporary failure in name resolution
```

This means the `DATABASE_URL` environment variable is either:
1. **Not set** in Coolify
2. **Invalid format** (wrong hostname, port, or credentials)
3. **Database host is unreachable** from the container

## Solution

### Step 1: Set DATABASE_URL in Coolify

1. Go to your Coolify project
2. Navigate to **Environment Variables** for the chat-service
3. Add or update `DATABASE_URL` with the correct format:

```
DATABASE_URL=postgresql+asyncpg://username:password@host:5432/database_name
```

### Step 2: Verify Database URL Format

The `DATABASE_URL` must:
- Start with `postgresql+asyncpg://` (required for async operations)
- Include username and password
- Include host (IP address or hostname)
- Include port (usually 5432 for PostgreSQL)
- Include database name

**Example:**
```
DATABASE_URL=postgresql+asyncpg://myuser:mypassword@db.example.com:5432/mydb
```

### Step 3: Common Issues

#### Issue: Database host is `localhost`
**Problem:** If your database is on the same server but you use `localhost`, the container can't reach it.

**Solution:** Use one of these:
- The **internal Docker network hostname** (if database is in same Docker network)
- The **server's public IP address**
- `host.docker.internal` (only works on Mac/Windows, not in production)
- The **actual database server hostname or IP**

#### Issue: Database is external (different server)
**Solution:** Use the external database's public hostname or IP address.

#### Issue: Database requires SSL
**Solution:** Add SSL parameters to the connection string:
```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?ssl=require
```

### Step 4: Test Connection

After setting `DATABASE_URL`, restart the service in Coolify. Check the logs for:

✅ **Success:**
```
INFO: Database connection test successful
INFO: Database connection initialized successfully
```

❌ **Failure:**
```
ERROR: Database connection test failed: [error details]
ERROR: Please verify:
  1. DATABASE_URL is correct
  2. Database host is reachable from the container
  3. Database credentials are correct
  4. Database exists and is accessible
```

## What Changed

The service now:
1. **Validates DATABASE_URL on startup** - Checks if it's set and has correct format
2. **Tests database connection on startup** - Attempts to connect and reports any issues
3. **Handles connection errors gracefully** - If database is unavailable during requests, the service continues to work (just without session persistence)
4. **Provides clear error messages** - Logs detailed information about what's wrong

## Important Notes

- The service will **start even if database connection fails** (with warnings)
- Chat requests will **still work** but **sessions won't be persisted** if database is unavailable
- Check the logs to see if database connection issues are occurring
- Make sure the database is **accessible from the Docker container network**

## Troubleshooting

### Check if DATABASE_URL is set:
```bash
# In Coolify, check environment variables for chat-service
```

### Test database connectivity from container:
If you have shell access to the container:
```bash
# Try to resolve the hostname
nslookup your-db-host

# Try to connect (if psql is available)
psql "postgresql://user:pass@host:5432/db"
```

### Verify database exists:
Make sure the database name in `DATABASE_URL` actually exists on the PostgreSQL server.

### Check firewall/network:
Ensure the database port (usually 5432) is open and accessible from the Coolify server.

