# syntax=docker/dockerfile:1
FROM docker.iranserver.com/python:3.11-slim

WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive

# Debian mirror (IranServer) + minimal system deps
RUN if [ -f /etc/apt/sources.list ]; then \
    sed -i 's|http://deb.debian.org/debian|http://mirror.iranserver.com/debian|g' /etc/apt/sources.list && \
    sed -i 's|https://deb.debian.org/debian|http://mirror.iranserver.com/debian|g' /etc/apt/sources.list && \
    sed -i 's|http://security.debian.org/debian-security|http://mirror.iranserver.com/debian-security|g' /etc/apt/sources.list && \
    sed -i 's|https://security.debian.org/debian-security|http://mirror.iranserver.com/debian-security|g' /etc/apt/sources.list; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# pip config (stable downloads)
RUN mkdir -p /etc && \
    printf '%s\n' \
    '[global]' \
    'index-url = https://pypi.org/simple' \
    'trusted-host = pypi.org' \
    'timeout = 90' \
    'retries = 4' \
    'prefer-binary = true' \
    'disable-pip-version-check = true' \
    > /etc/pip.conf

# Install deps first (better layer cache)
COPY services/gateway/requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && \
    pip install -r /app/requirements.txt

# App code
COPY shared /app/shared
COPY services/gateway /app/services/gateway

# Static UI files (from repo root)
COPY Chat.html /app/Chat.html
COPY Icon.png /app/Icon.png
COPY favicon.ico /app/favicon.ico
COPY monitoring_dashboard.html /app/monitoring_dashboard.html

WORKDIR /app/services/gateway
ENV PYTHONPATH=/app

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
