# Use standard tag for better compatibility and caching
# If you encounter TLS handshake timeouts, try:
# 1. Check server network connectivity to Docker Hub
# 2. Configure Docker registry mirror in Coolify
# 3. Retry the deployment (may be temporary network issue)
FROM python:3.11-slim

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
