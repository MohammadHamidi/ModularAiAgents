# Coolify Environment Variables Configuration

## Required Environment Variables for Chat-Service

Set these in Coolify for the **chat-service**:

```bash
# Database (External - REQUIRED)
DATABASE_URL=postgresql+asyncpg://postgressafiran:Dfq2OkDvTpV4dzvfvGgTrxWOdXqpu1AfJp70Mye3v@zwgg8ggk040400g40k4g0gsg:5432/postgressafiran

# LiteLLM Configuration (REQUIRED)
LITELLM_API_KEY=aa-Q3wvkDo2WQRoW47cytnMYozQC9eVaETaKINkeR5ynGMKq06C
LITELLM_BASE_URL=https://api.avalai.ir/v1
LITELLM_MODEL=gemini-2.5-flash-lite-preview-09-2025

# Session Configuration
MAX_SESSION_MESSAGES=30
SESSION_TTL_SECONDS=14400

# LightRAG Configuration (Optional)
LIGHTRAG_BASE_URL=https://safiranlighrag.bedooncode.ir/
LIGHTRAG_USERNAME=
LIGHTRAG_PASSWORD=
LIGHTRAG_API_KEY_HEADER_VALUE=
LIGHTRAG_BEARER_TOKEN=
```

## Required Environment Variables for Gateway

Set these in Coolify for the **gateway**:

```bash
# Internal service communication
CHAT_SERVICE_URL=http://chat-service:8001
```

## Important Notes

1. **DATABASE_URL**: Must use `postgresql+asyncpg://` format (not just `postgresql://`)
2. **LIGHTRAG_BASE_URL**: Can have trailing slash - code will strip it automatically
3. **Empty LightRAG vars**: Leave empty if not using LightRAG authentication
4. **Service URLs**: These are automatically set by Coolify (SERVICE_URL_GATEWAY, etc.)

## Verification

After setting these variables and deploying:
- Check chat-service logs to verify database connection
- Check gateway logs to verify it can reach chat-service
- Test the UI at: `https://safirangate.bedooncode.ir/ui`

