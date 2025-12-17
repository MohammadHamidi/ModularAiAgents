FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy shared folder first (for dependency resolution)
COPY shared /app/shared

# Copy service code
COPY services/chat-service /app/services/chat-service

# Set working directory to service directory
WORKDIR /app/services/chat-service

# Set PYTHONPATH to include parent directory for shared imports
ENV PYTHONPATH=/app

# Install Python dependencies with retry logic for network issues
COPY services/chat-service/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --default-timeout=100 --retries 5 -r requirements.txt

# Expose port
EXPOSE 8001

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

