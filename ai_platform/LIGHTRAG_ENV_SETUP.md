# LightRAG Environment Variables Setup

Add these environment variables to your `.env` file in the root directory.

## Required

```bash
LIGHTRAG_BASE_URL=https://YOUR-LIGHTRAG-HOST
```

## Optional (only if your LightRAG instance requires auth)

### OAuth2 Password Flow

If your server is protected via OAuth2 password flow:

```bash
LIGHTRAG_USERNAME=your_username
LIGHTRAG_PASSWORD=your_password
```

### API Key Header

If your server expects `api_key_header_value` query param:

```bash
LIGHTRAG_API_KEY_HEADER_VALUE=your_api_key
```

### Bearer Token

If your gateway already fetches tokens and stores them:

```bash
LIGHTRAG_BEARER_TOKEN=your_bearer_token
```

## Notes

- The system will try authentication methods in this order:

  1. Bearer token (if `LIGHTRAG_BEARER_TOKEN` is set)
  2. OAuth2 password flow (if username/password are set)
  3. API key query param (if `LIGHTRAG_API_KEY_HEADER_VALUE` is set)
  4. Guest token from `/auth-status` endpoint (if auth is disabled)

- If no auth method is configured and `/auth-status` doesn't provide a guest token, requests will be made without authentication.
