# Docker Build Troubleshooting

## Configured mirrors (Iran)

Builds can use local mirrors to avoid Docker Hub / PyPI / Debian connectivity issues:

| Resource | Mirror | Where configured |
|----------|--------|------------------|
| **Docker images** (base) | (host-level mirror, e.g. `https://focker.ir`) | Configure Docker daemon `registry-mirrors` on the build host |
| **Debian apt** | `http://mirror.iranserver.com/debian` | Dockerfile `sed` + `apt-get update` in chat-service and gateway |
| **PyPI** (Python packages) | `https://mirror-pypi.runflare.com/` | Dockerfile `pip install --index-url ...` in chat-service and gateway |

**Optional – global Docker mirror (build host):**  
To pull *any* image through focker.ir (not only the ones in the Dockerfile), configure the Docker daemon on the build host:

```json
{
  "registry-mirrors": ["https://focker.ir"]
}
```

Then restart Docker. After that, `docker pull python:3.11-slim` will use the mirror automatically.

**Alternative Debian mirrors** (if mirror.iranserver.com is slow):  
- `http://mirror.shatel.ir/debian`  
- `https://linux-repository.arvancloud.ir/debian`  

Edit the `sed` lines in the Dockerfile to point to the mirror you prefer.

To switch back to upstream (Docker Hub + deb.debian.org + PyPI), change each Dockerfile: use `FROM python:3.11-slim`, remove the `sed` and use plain `apt-get update && apt-get install ...`, and remove the `--index-url` / `--trusted-host` options from the `pip install` lines.

---

## Build fails with "failed to fetch anonymous token" / "unexpected EOF"

**Symptom:**
```text
failed to authorize: failed to fetch anonymous token: Get "https://auth.docker.io/token?...": unexpected EOF
target chat-service: failed to solve: python:3.11-slim: failed to resolve source metadata
```

**Cause:** The **build environment (e.g. Coolify’s build server) cannot reach Docker Hub** to pull the base image `python:3.11-slim`. This is a network/infrastructure issue, not an application bug.

**What to do:**

1. **Retry the build**  
   Transient network or Docker Hub issues often clear after some time.

2. **Check outbound access from the build host**  
   From the **same machine/network where the build runs** (Coolify build runner), ensure:
   - `auth.docker.io` (HTTPS) is allowed
   - `registry-1.docker.io` (HTTPS) is allowed  
   If there is a firewall or proxy, it must allow these.

3. **Use a Docker Hub mirror (if available)**  
   If your organization uses a mirror for Docker Hub, configure the Docker daemon on the **build host** to use it (e.g. `registry-mirrors` in `/etc/docker/daemon.json`). Then retry the build.

4. **Avoid `--pull` when base image is already present**  
   If the base image is already on the build host, you can try building **without** `--pull` so Docker uses the cached `python:3.11-slim` and does not hit Docker Hub. In Coolify, check whether the build step can be run without “always pull” for this project.

5. **Confirm Docker Hub status**  
   Check [status.docker.com](https://status.docker.com) for incidents. If there is an outage, wait and retry.

---

## Build is very slow or times out pulling base image

- The build may be waiting on Docker Hub (rate limits or slow network). Same network checks as above apply.
- Increasing build timeout in Coolify (if available) can help when the network is slow but working.

---

## DATABASE_URL format for chat-service

The app expects an **async** PostgreSQL URL:

- **Correct:** `postgresql+asyncpg://user:pass@host:port/dbname`
- **Wrong for this app:** `postgres://user:pass@host:port/dbname` (sync driver)

If you use `postgres://`, the chat-service may fail at runtime. In Coolify (or your env), set:

```bash
DATABASE_URL=postgresql+asyncpg://postgressafiran:YOUR_PASSWORD@81.12.27.188:6363/postgressafiran
```

(Replace `YOUR_PASSWORD` with the real password; no quotes in the URL.)
