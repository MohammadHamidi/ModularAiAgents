# Base image from docker.iranserver.com mirror
# If needed, you can switch back to: FROM python:3.11-slim
FROM docker.iranserver.com/python:3.11-slim

# =============================================================================
# SECURITY WARNING: NEVER use ARG for secrets (API keys, passwords, etc.)
# Build args can end up in image history, build logs, and caches.
# All secrets must be passed as RUNTIME environment variables only.
# See docker-compose.yml environment: section and DOCKER_BUILD_TROUBLESHOOTING.md
# =============================================================================

WORKDIR /app

# Use regional Debian mirror for apt if /etc/apt/sources.list exists (faster and more reliable from Iran)
RUN if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://deb.debian.org/debian|http://mirror.iranserver.com/debian|g' /etc/apt/sources.list && \
      sed -i 's|https://deb.debian.org/debian|http://mirror.iranserver.com/debian|g' /etc/apt/sources.list; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# =============================================================================
# LAYER 1: Install Python dependencies FIRST (cached if requirements.txt unchanged)
# PyPI mirror: https://mirror-pypi.runflare.com/
# =============================================================================
COPY services/gateway/requirements.txt /app/requirements.txt
RUN pip install --index-url https://mirror-pypi.runflare.com/ \
    --trusted-host mirror-pypi.runflare.com --upgrade pip && \
    pip install --index-url https://mirror-pypi.runflare.com/ \
    --trusted-host mirror-pypi.runflare.com \
    --default-timeout=100 --retries 5 -r /app/requirements.txt

# =============================================================================
# LAYER 2: Copy code files AFTER dependencies (changes don't invalidate pip cache)
# =============================================================================
# Copy shared folder
COPY shared /app/shared

# Copy service code
COPY services/gateway /app/services/gateway

# Copy static UI files (Chat.html, Icon.png, monitoring_dashboard.html, etc.)
COPY Chat.html /app/Chat.html
COPY Icon.png /app/Icon.png
COPY favicon.ico /app/favicon.ico
COPY monitoring_dashboard.html /app/monitoring_dashboard.html

# Set working directory to service directory
WORKDIR /app/services/gateway

# Set PYTHONPATH to include parent directory for shared imports
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# Base image from docker.iranserver.com mirror
# If needed, you can switch back to: FROM python:3.11-slim
FROM docker.iranserver.com/python:3.11-slim

# =============================================================================
# SECURITY WARNING: NEVER use ARG for secrets (API keys, passwords, etc.)
# Build args can end up in image history, build logs, and caches.
# All secrets must be passed as RUNTIME environment variables only.
# See docker-compose.yml environment: section and DOCKER_BUILD_TROUBLESHOOTING.md
# =============================================================================

WORKDIR /app

# Use regional Debian mirror for apt if /etc/apt/sources.list exists (faster and more reliable from Iran)
RUN if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://deb.debian.org/debian|http://mirror.iranserver.com/debian|g' /etc/apt/sources.list && \
      sed -i 's|https://deb.debian.org/debian|http://mirror.iranserver.com/debian|g' /etc/apt/sources.list; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# =============================================================================
# LAYER 1: Install Python dependencies FIRST (cached if requirements.txt unchanged)
# PyPI mirror: https://mirror-pypi.runflare.com/
# =============================================================================
COPY services/gateway/requirements.txt /app/requirements.txt
RUN pip install --index-url https://mirror-pypi.runflare.com/ \
    --trusted-host mirror-pypi.runflare.com --upgrade pip && \
    pip install --index-url https://mirror-pypi.runflare.com/ \
    --trusted-host mirror-pypi.runflare.com \
    --default-timeout=100 --retries 5 -r /app/requirements.txt

# =============================================================================
# LAYER 2: Copy code files AFTER dependencies (changes don't invalidate pip cache)
# =============================================================================
# Copy shared folder
COPY shared /app/shared

# Copy service code
COPY services/gateway /app/services/gateway

# Copy static UI files (Chat.html, Icon.png, monitoring_dashboard.html, etc.)
COPY Chat.html /app/Chat.html
COPY Icon.png /app/Icon.png
COPY favicon.ico /app/favicon.ico
COPY monitoring_dashboard.html /app/monitoring_dashboard.html

# Set working directory to service directory
WORKDIR /app/services/gateway

# Set PYTHONPATH to include parent directory for shared imports
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
