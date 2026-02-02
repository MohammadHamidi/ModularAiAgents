# Use standard tag for better compatibility and caching.
# Base from GHCR (not Docker Hub) so builds succeed when registry-1.docker.io is unreachable (e.g. TLS timeout).
# --platform=linux/amd64 avoids "No matching distribution for pydantic" on ARM build nodes.
FROM --platform=linux/amd64 ghcr.io/docker-library/python:3.11-slim-bookworm

# =============================================================================
# SECURITY WARNING: NEVER use ARG for secrets (API keys, passwords, etc.)
# Build args can end up in image history, build logs, and caches.
# All secrets must be passed as RUNTIME environment variables only.
# See docker-compose.yml environment: section and DOCKER_BUILD_TROUBLESHOOTING.md
# =============================================================================

WORKDIR /app

# Install system dependencies (including curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# LAYER 1: Install Python dependencies FIRST (cached if requirements.txt unchanged)
# Try default PyPI first; on timeout/SSL errors (e.g. Coolify, restricted networks)
# fall back to a public PyPI mirror (Runflare). Use a different mirror if needed via pip config in CI.
# =============================================================================
COPY services/chat-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    (pip install --no-cache-dir --default-timeout=120 --retries 5 -r /app/requirements.txt || \
     pip install --no-cache-dir --default-timeout=300 --retries 10 \
       -i "https://mirror-pypi.runflare.com/simple/" \
       --trusted-host "mirror-pypi.runflare.com" \
       -r /app/requirements.txt)

# =============================================================================
# LAYER 2: Copy code files AFTER dependencies (changes don't invalidate pip cache)
# =============================================================================
# Copy shared folder
COPY shared /app/shared

# Copy QA examples for few-shot prompt injection
COPY QA_EXAMPLES.md /app/QA_EXAMPLES.md

# کنش CSV: Docker build may fail with Persian filenames in COPY. Mount at runtime
# or set KONESH_CSV_PATH, e.g. in docker-compose: volumes: - ./کنش_های سفیران آیه_ها.csv:/app/konesh.csv
# and env: KONESH_CSV_PATH=/app/konesh.csv

# Copy service code
COPY services/chat-service /app/services/chat-service

# Set working directory to service directory
WORKDIR /app/services/chat-service

# Set PYTHONPATH to include parent directory for shared imports
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8001

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
