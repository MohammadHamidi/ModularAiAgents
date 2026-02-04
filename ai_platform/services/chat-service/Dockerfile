FROM docker.iranserver.com/python:3.11-slim

WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive

RUN if [ -f /etc/apt/sources.list ]; then \
    sed -i 's|http://deb.debian.org/debian|http://mirror.iranserver.com/debian|g' /etc/apt/sources.list && \
    sed -i 's|https://deb.debian.org/debian|http://mirror.iranserver.com/debian|g' /etc/apt/sources.list; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# PIP config: IranRepo primary + Runflare fallback (needed because IranRepo lacks fastapi)
RUN mkdir -p /etc && \
    printf '%s\n' \
    '[global]' \
    'index-url = https://pypi.iranrepo.ir/simple' \
    'extra-index-url = https://mirror-pypi.runflare.com/simple' \
    'trusted-host = pypi.iranrepo.ir mirror-pypi.runflare.com' \
    'timeout = 300' \
    'retries = 20' \
    'prefer-binary = true' \
    'disable-pip-version-check = true' \
    > /etc/pip.conf

COPY services/chat-service/requirements.txt /app/requirements.txt

# Use pip download cache
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /app/requirements.txt

COPY shared /app/shared
COPY QA_EXAMPLES.md /app/QA_EXAMPLES.md
COPY services/chat-service /app/services/chat-service

WORKDIR /app/services/chat-service
ENV PYTHONPATH=/app

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
