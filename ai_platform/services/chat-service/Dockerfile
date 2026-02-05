<<<<<<< Updated upstream
FROM docker.iranserver.com/python:3.11-slim
=======
# syntax=docker/dockerfile:1
FROM python:3.11-slim
>>>>>>> Stashed changes

WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive

<<<<<<< Updated upstream
RUN if [ -f /etc/apt/sources.list ]; then \
    sed -i 's|http://deb.debian.org/debian|http://mirror.iranserver.com/debian|g' /etc/apt/sources.list && \
    sed -i 's|https://deb.debian.org/debian|http://mirror.iranserver.com/debian|g' /etc/apt/sources.list && \
    sed -i 's|http://security.debian.org/debian-security|http://mirror.iranserver.com/debian-security|g' /etc/apt/sources.list && \
    sed -i 's|https://security.debian.org/debian-security|http://mirror.iranserver.com/debian-security|g' /etc/apt/sources.list; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# PIP config: PyPI only (no Runflare), with sane timeouts
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

COPY services/chat-service/requirements.txt /app/requirements.txt

# Use pip download cache
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /app/requirements.txt

=======
# System deps (keep minimal; add more only if needed)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better caching)
COPY services/chat-service/requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# Copy app code
>>>>>>> Stashed changes
COPY shared /app/shared
COPY QA_EXAMPLES.md /app/QA_EXAMPLES.md
COPY services/chat-service /app/services/chat-service

WORKDIR /app/services/chat-service
ENV PYTHONPATH=/app

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
