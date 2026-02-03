#!/usr/bin/env bash
# Test Docker build locally before deploying to Coolify.
# Run from ai_platform:  bash test-docker-build.sh
# On Windows PowerShell, run the commands in TEST_DOCKER_BUILD.md instead.

set -e
cd "$(dirname "$0")"
MIRROR="${DOCKER_REGISTRY_MIRROR:-docker.iranserver.com}"
IMAGE="${MIRROR}/library/python:3.11-slim-bookworm"

echo "=== 1. Test pull base image from mirror: $IMAGE ==="
docker pull --platform=linux/amd64 "$IMAGE"
echo "OK: Base image pulled from mirror."

echo ""
echo "=== 2. Build chat-service and gateway (same as Coolify) ==="
docker compose build --no-cache chat-service gateway
echo "OK: Build completed."

echo ""
echo "Done. If both steps succeeded, the same Dockerfiles should work on the server."
