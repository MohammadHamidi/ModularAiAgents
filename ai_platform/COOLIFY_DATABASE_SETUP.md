# Coolify Database Setup

## External Database Configuration

If you're using an external managed database (like the one provided), you need to:

### 1. Set DATABASE_URL in Coolify Environment Variables

Convert your PostgreSQL connection string to asyncpg format:

**Your current DB:**
```
postgresql://postgressafiran:Dfq2OkDvTpV4dzvfvGgTrxWOdXqpu1AfJp70Mye3v@zwgg8ggk040400g40k4g0gsg:5432/postgressafiran
```

**Convert to asyncpg format (for chat-service):**
```
postgresql+asyncpg://postgressafiran:Dfq2OkDvTpV4dzvfvGgTrxWOdXqpu1AfJp70Mye3v@zwgg8ggk040400g40k4g0gsg:5432/postgressafiran
```

### 2. Add to Coolify Environment Variables

In Coolify, add this environment variable for the **chat-service**:

```
DATABASE_URL=postgresql+asyncpg://postgressafiran:Dfq2OkDvTpV4dzvfvGgTrxWOdXqpu1AfJp70Mye3v@zwgg8ggk040400g40k4g0gsg:5432/postgressafiran
```

### 3. Optional: Remove Internal PostgreSQL Service

If you're using an external database, you can remove or comment out the `postgres` service in `docker-compose.yml` to save resources:

```yaml
# postgres:
#   image: postgres:15
#   ...
```

And remove the `depends_on: postgres` from `chat-service`:

```yaml
chat-service:
  # ...
  # depends_on:
  #   - postgres
```

### 4. Verify Database Connection

After deployment, check the chat-service logs to ensure it connects successfully to the database.

## Environment Variables Summary

Make sure these are set in Coolify:

### For chat-service:
- `DATABASE_URL` - Your external database connection string (asyncpg format)
- `LITELLM_API_KEY` - Your LiteLLM API key
- `LITELLM_BASE_URL` - https://api.avalai.ir/v1
- `LITELLM_MODEL` - gemini-2.5-flash-lite-preview-09-2025
- `LIGHTRAG_BASE_URL` - https://safiranlighrag.bedooncode.ir/
- `MAX_SESSION_MESSAGES` - 30
- `SESSION_TTL_SECONDS` - 14400

### For gateway:
- `CHAT_SERVICE_URL` - http://chat-service:8001 (internal Docker network)

