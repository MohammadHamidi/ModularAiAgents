FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (including curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# LAYER 1: Install Python dependencies FIRST (cached if requirements.txt unchanged)
# =============================================================================
COPY services/gateway/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && \
    pip install --default-timeout=100 --retries 5 -r /app/requirements.txt

# =============================================================================
# LAYER 2: Copy code files AFTER dependencies (changes don't invalidate pip cache)
# =============================================================================
# Copy shared folder
COPY shared /app/shared

# Copy service code
COPY services/gateway /app/services/gateway

# Copy static UI files (Chat.html, Icon.png, etc.)
COPY Chat.html /app/Chat.html
COPY Icon.png /app/Icon.png

# Set working directory to service directory
WORKDIR /app/services/gateway

# Set PYTHONPATH to include parent directory for shared imports
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
