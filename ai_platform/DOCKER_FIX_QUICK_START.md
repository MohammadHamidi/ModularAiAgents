# Docker Build Fix - Quick Action Guide

## Immediate Actions (Do These First)

### 1. Fix Docker DNS (Most Likely Solution)

On your Coolify server, run:

```bash
# Create/edit Docker daemon config
sudo nano /etc/docker/daemon.json
```

Add/update with:

```json
{
  "dns": ["1.1.1.1", "8.8.8.8"]
}
```

Then restart Docker:

```bash
sudo systemctl restart docker
```

### 2. Verify Network Connectivity

Test from the server:

```bash
# Test DNS and TLS
curl -v --connect-timeout 10 https://auth.docker.io/token 2>&1 | head -40
```

If this works, try your deployment again.

### 3. Check System Time

```bash
timedatectl status
```

If not synced:

```bash
sudo timedatectl set-ntp true
```

### 4. Fix Secret Leakage (CRITICAL)

**If Coolify is passing secrets as build args:**

1. **Go to Coolify UI** → Your Service → Environment Variables
2. **Remove ALL secrets from "Build-time Environment Variables"**
3. **Move ALL secrets to "Runtime Environment Variables" only**
4. **Rotate any exposed secrets immediately:**
   - New LiteLLM API key
   - New database password
   - New LightRAG credentials

**Secrets that should NEVER be in build-time:**

- `DATABASE_URL`
- `LITELLM_API_KEY`
- `LIGHTRAG_PASSWORD`
- `LIGHTRAG_USERNAME`
- `LIGHTRAG_API_KEY_HEADER_VALUE`
- `LIGHTRAG_BEARER_TOKEN`

## Quick Diagnostic

Run this on your server to diagnose the network issue:

```bash
docker run --rm --network coolify alpine:3.20 sh -lc '
  apk add --no-cache curl bind-tools ca-certificates;
  date;
  nslookup auth.docker.io || true;
  curl -v --connect-timeout 10 https://auth.docker.io/token 2>&1 | head -60
'
```

**What to look for:**

- ✅ DNS resolves → Good
- ✅ TLS handshake completes → Good
- ❌ Timeout/hang → Network/DNS issue (fix with step 1)

## If DNS Fix Doesn't Work

See `DOCKER_BUILD_TROUBLESHOOTING.md` for:

- Registry mirror configuration
- IPv6 issues
- MTU mismatch fixes
- Firewall/egress rules

## Security Verification

After fixing secrets:

```bash
# Check if secrets are in image (they shouldn't be)
docker history <your-image> --no-trunc | grep -i "litellm\|database\|password"
```

Should return nothing.

## Files Updated

- ✅ `DOCKER_BUILD_TROUBLESHOOTING.md` - Complete troubleshooting guide
- ✅ `COOLIFY_SECURITY_CONFIG.md` - Coolify-specific security guide
- ✅ `Dockerfile` (both services) - Added security warnings
- ✅ `docker-compose.yml` - Added security comments

## Next Steps

1. Apply DNS fix (step 1 above)
2. Fix secret leakage in Coolify (step 4 above)
3. Retry deployment
4. If still failing, see `DOCKER_BUILD_TROUBLESHOOTING.md` for advanced fixes
