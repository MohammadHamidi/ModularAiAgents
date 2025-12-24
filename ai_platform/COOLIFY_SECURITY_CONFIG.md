# Coolify Security Configuration Guide

## ⚠️ CRITICAL: Preventing Secret Leakage in Builds

If Coolify is passing secrets as build arguments, they can be exposed in:

- Docker image history
- Build logs
- Build caches
- Image metadata

## How to Fix in Coolify UI

### Step 1: Identify Build-Time vs Runtime Variables

In Coolify, environment variables are typically separated into:

- **Build-time Environment Variables** (used during `docker build`)
- **Runtime Environment Variables** (injected at container startup)

### Step 2: Move All Secrets to Runtime Only

**❌ NEVER put these in Build-time Environment Variables:**

- `DATABASE_URL`
- `LITELLM_API_KEY`
- `LIGHTRAG_PASSWORD`
- `LIGHTRAG_USERNAME`
- `LIGHTRAG_API_KEY_HEADER_VALUE`
- `LIGHTRAG_BEARER_TOKEN`
- Any API keys, passwords, or tokens

**✅ ONLY put these in Runtime Environment Variables:**

- All secrets listed above
- Any configuration that contains sensitive data

**✅ Build-time variables (if needed) should only contain:**

- `SOURCE_COMMIT` (git commit hash)
- `BUILD_DATE` (build timestamp)
- `NODE_ENV=production` (non-secret)
- Other non-sensitive metadata

### Step 3: Verify Configuration

1. Go to your service in Coolify
2. Navigate to "Environment Variables" or "Settings"
3. Check both "Build-time" and "Runtime" sections
4. **Remove all secrets from Build-time section**
5. **Ensure all secrets are in Runtime section only**

### Step 4: If Secrets Were Already Exposed

**IMMEDIATE ACTIONS REQUIRED:**

1. **Rotate all exposed credentials:**

   - Generate new LiteLLM API key
   - Change database password
   - Regenerate LightRAG credentials
   - Update any other exposed secrets

2. **Update Coolify environment variables** with new credentials

3. **Rebuild and redeploy** services

4. **Review build logs** to see what was exposed (if accessible)

5. **Consider rebuilding images from scratch** to remove secrets from image history:
   ```bash
   docker image prune -a
   # Then rebuild services
   ```

## Coolify Build Settings

### Recommended Build Configuration

In Coolify service settings:

- **Build Command:** `docker compose build` (without `--pull --no-cache` if possible)
- **Build-time Environment Variables:** Empty or only non-secret metadata
- **Runtime Environment Variables:** All secrets and configuration

### If Coolify Forces `--pull --no-cache`

If Coolify automatically adds `--pull --no-cache` flags:

1. **Pre-pull base images** on the server:

   ```bash
   docker pull python:3.11-slim
   ```

2. **Use Docker layer caching** by ensuring your Dockerfile structure is optimal (already done in current Dockerfiles)

3. **Consider using a registry mirror** if Docker Hub connectivity is unstable (see DOCKER_BUILD_TROUBLESHOOTING.md)

## Verification Checklist

- [ ] No secrets in Coolify "Build-time Environment Variables"
- [ ] All secrets in Coolify "Runtime Environment Variables"
- [ ] Dockerfile has no `ARG` statements for secrets
- [ ] docker-compose.yml has no `build.args` for secrets
- [ ] All exposed secrets have been rotated
- [ ] Services rebuilt after moving secrets

## Testing the Fix

After moving secrets to runtime-only:

1. **Check build logs** - secrets should NOT appear in build output
2. **Inspect image history** (if possible):

   ```bash
   docker history <image-name> --no-trunc
   ```

   Secrets should NOT appear in any layer

3. **Verify runtime functionality** - services should still work correctly with runtime env vars

## Additional Resources

- See `DOCKER_BUILD_TROUBLESHOOTING.md` for network/DNS fixes
- See `docker-compose.yml` for reference configuration
- [Docker BuildKit security best practices](https://docs.docker.com/build/security/)
