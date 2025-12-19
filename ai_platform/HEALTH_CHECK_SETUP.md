# Health Check Configuration

## Health Check Endpoints

Both services have `/health` endpoints that return JSON:

### Chat-Service Health Endpoint
- **URL**: `http://localhost:8001/health`
- **Response**: `{"status": "healthy", "service": "chat", "agents": [...]}`

### Gateway Health Endpoint
- **URL**: `http://localhost:8000/health`
- **Response**: `{"status": "healthy", "service": "gateway", "chat_service": "connected"}`

## Docker Compose Health Checks

Health checks are configured in `docker-compose.yml`:

### Chat-Service Health Check
```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:8001/health || exit 1"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 30s
```

### Gateway Health Check
```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 30s
```

## Health Check Behavior

- **start_period: 30s**: Waits 30 seconds before starting health checks (gives service time to start)
- **interval: 10s**: Checks every 10 seconds
- **timeout: 5s**: Each check times out after 5 seconds
- **retries: 5**: Must fail 5 consecutive times before marked unhealthy

## Service Dependencies

Gateway depends on chat-service being healthy:
```yaml
depends_on:
  chat-service:
    condition: service_healthy
```

This ensures gateway only starts after chat-service is fully ready.

## Coolify Integration

Coolify will automatically use these health checks to:
- Determine when services are ready
- Route traffic only to healthy services
- Restart unhealthy services
- Show service status in the dashboard

## Troubleshooting

If health checks are failing:
1. Check service logs: `docker-compose logs chat-service` or `docker-compose logs gateway`
2. Verify `/health` endpoint is accessible: `curl http://localhost:8001/health`
3. Check if services are starting properly (database connection, etc.)
4. Verify curl is installed in containers (it's added to Dockerfiles)

