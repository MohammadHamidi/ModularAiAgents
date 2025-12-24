# Docker Build Troubleshooting Guide

## Network/TLS Connectivity Issues

If you're experiencing `TLS handshake timeout` errors when pulling base images from Docker Hub, follow these steps:

### 1. Verify Connectivity from Build Container

Run this diagnostic on your Coolify server (after a failed deploy):

```bash
docker run --rm --network coolify alpine:3.20 sh -lc '
  apk add --no-cache curl bind-tools ca-certificates;
  date;
  nslookup auth.docker.io || true;
  curl -v --connect-timeout 10 https://auth.docker.io/token 2>&1 | head -60
'
```

**Expected results:**

- DNS resolves `auth.docker.io`
- `curl` connects and completes TLS handshake
- If it hangs/timeouts → confirms network/DNS/egress issue

### 2. Fix Docker DNS (Most Common Solution)

Edit `/etc/docker/daemon.json` (create if missing):

```json
{
  "dns": ["1.1.1.1", "8.8.8.8"]
}
```

Then restart Docker:

```bash
sudo systemctl restart docker
```

Re-run your deployment.

### 3. Check System Time

TLS can fail if the system clock is wrong:

```bash
timedatectl status
```

If not synced:

```bash
sudo timedatectl set-ntp true
```

### 4. Use Registry Mirror (For Restricted Regions)

If you're in a region with unstable Docker Hub access, configure a registry mirror in `/etc/docker/daemon.json`:

```json
{
  "registry-mirrors": ["https://your-mirror-url"]
}
```

Or use a pull-through cache (Harbor, etc.).

### 5. Reduce Build Pressure

Coolify may be using `docker compose build --pull --no-cache`, which forces fresh pulls every deploy.

**Workarounds:**

- Pre-pull base images on the host:
  ```bash
  docker pull python:3.11-slim
  ```
- If possible, disable `--pull` and `--no-cache` in Coolify build settings

### 6. IPv6 Issues

If Docker tries IPv6 first and stalls, force IPv4:

```bash
# Test IPv4 connectivity
curl -4 https://auth.docker.io/token
```

If that works, you may need to disable IPv6 in Docker daemon or configure sysctl.

### 7. MTU Mismatch (VPN/Private Networks)

Check MTU and consider setting Docker MTU in `/etc/docker/daemon.json`:

```json
{
  "mtu": 1450
}
```

Then restart Docker.

### 8. Firewall / Egress Rules

Ensure outbound 443 is open to:

- `auth.docker.io`
- `registry-1.docker.io`

Test from host:

```bash
curl -v --connect-timeout 10 https://auth.docker.io/token 2>&1 | head -40
```

---

## Security: Preventing Secret Leakage

### ⚠️ CRITICAL: Secrets in Build Args

**NEVER pass secrets as Docker build arguments (`ARG`).** Build args can:

- End up in image history/metadata
- Be exposed in build logs
- Be cached in intermediate layers

### Current Setup (Secure)

✅ **Dockerfile**: No `ARG` statements for secrets
✅ **docker-compose.yml**: Secrets are runtime `environment:` variables only

### Coolify Configuration

If Coolify is automatically passing environment variables as build args:

1. **In Coolify UI:**

   - Go to your service settings
   - Find "Build Arguments" or "Build-time Environment Variables"
   - **Remove all secrets** from build-time variables
   - Keep secrets only in **Runtime Environment Variables**

2. **Verify in Coolify:**

   - Build-time env vars should only contain non-secret values like:
     - `SOURCE_COMMIT`
     - `BUILD_DATE`
     - `NODE_ENV=production` (non-secret)
   - Runtime env vars should contain:
     - `DATABASE_URL`
     - `LITELLM_API_KEY`
     - `LIGHTRAG_PASSWORD`
     - All other API keys and secrets

3. **If Secrets Were Exposed:**
   - **Rotate all exposed keys immediately:**
     - LiteLLM API key
     - Database password
     - LightRAG credentials
     - Any other exposed secrets

### Best Practices

1. **Dockerfile ARG usage:**

   ```dockerfile
   # ✅ OK: Non-secret build metadata
   ARG SOURCE_COMMIT
   ARG BUILD_DATE

   # ❌ NEVER: Secrets
   # ARG DATABASE_URL
   # ARG LITELLM_API_KEY
   ```

2. **docker-compose.yml:**

   ```yaml
   services:
     app:
       build:
         context: .
         # ❌ Don't pass secrets here
         # args:
         #   DATABASE_URL: ${DATABASE_URL}
       environment:
         # ✅ Secrets go here (runtime only)
         DATABASE_URL: ${DATABASE_URL}
         LITELLM_API_KEY: ${LITELLM_API_KEY}
   ```

3. **Coolify Environment Variables:**
   - Separate "Build-time" and "Runtime" environment variable sections
   - Only put secrets in "Runtime" section
   - Use "Build-time" only for non-secret metadata

---

## Quick Diagnostic Checklist

- [ ] DNS resolves `auth.docker.io` from build container
- [ ] TLS handshake completes (`curl https://auth.docker.io/token`)
- [ ] System time is synchronized
- [ ] Docker daemon has DNS configured (`/etc/docker/daemon.json`)
- [ ] Outbound 443 is open to Docker Hub
- [ ] No secrets in Dockerfile `ARG` statements
- [ ] No secrets in Coolify build-time environment variables
- [ ] All secrets are in runtime environment variables only

---

## Additional Resources

- [Docker BuildKit documentation](https://docs.docker.com/build/buildkit/)
- [Docker daemon configuration](https://docs.docker.com/config/daemon/)
- [Coolify documentation](https://coolify.io/docs)
