# Use standard tag for better compatibility and caching
# If you encounter TLS handshake timeouts, see DOCKER_BUILD_TROUBLESHOOTING.md
FROM python:3.11-slim

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
# =============================================================================
COPY services/chat-service/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && \
    pip install --default-timeout=100 --retries 5 -r /app/requirements.txt

# =============================================================================
# LAYER 2: Copy code files AFTER dependencies (changes don't invalidate pip cache)
# =============================================================================
# Copy shared folder
COPY shared /app/shared

# Copy QA examples for few-shot prompt injection
COPY QA_EXAMPLES.md /app/QA_EXAMPLES.md

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
