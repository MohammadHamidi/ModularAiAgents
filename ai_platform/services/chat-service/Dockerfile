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
COPY services/chat-service/requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && \
    pip install -r /app/requirements.txt

# App code
COPY shared /app/shared
COPY QA_EXAMPLES.md /app/QA_EXAMPLES.md
COPY services/chat-service /app/services/chat-service
# Konesh.csv for building konesh knowledge base (tab-delimited, UTF-8)
COPY Konesh.csv /app/Konesh.csv

WORKDIR /app/services/chat-service
ENV PYTHONPATH=/app

# Build local knowledge (verses, konesh from CSV, konesh_type_mapping)
RUN python scripts/build_local_knowledge.py || true

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
