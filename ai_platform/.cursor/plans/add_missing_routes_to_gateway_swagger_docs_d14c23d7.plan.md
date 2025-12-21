---
name: Add Missing Routes to Gateway Swagger Docs
overview: Add missing agent-related routes to the gateway service so they appear in Swagger documentation. The gateway currently only forwards `/chat/{agent_key}` but is missing `/personas`, `/tools`, and `/tools/{tool_name}` routes that exist in the chat-service.
todos: []
---

# Add Missing Routes to Gateway Swagger Documentation

## Problem

The gateway service Swagger docs only show one POST `/chat/{agent_key}` endpoint, but the chat-service has additional agent-related routes that should be accessible through the gateway:

- `/personas` (GET) - List all available personas
- `/tools` (GET) - List all available tools  
- `/tools/{tool_name}` (GET) - Get detailed tool information

## Solution

Add these missing routes to the gateway service with proper documentation, tags, and forwarding logic.

## Changes Required

### 1. Update `services/gateway/main.py`

Add three new endpoint handlers that forward requests to chat-service:

1. **GET `/personas`** - Forward to chat-service `/personas`

- Tag: `["Agents"]`
- Description: List all available chat personas with their configurations

2. **GET `/tools`** - Forward to chat-service `/tools`

- Tag: `["Tools"]`
- Description: List all available tools in the system

3. **GET `/tools/{tool_name}`** - Forward to chat-service `/tools/{tool_name}`

- Tag: `["Tools"]`
- Description: Get detailed information about a specific tool

### 2. Fix Missing Tag in Chat-Service

The `/session/{session_id}` DELETE endpoint in chat-service is missing the `tags=["Sessions"]` decorator.

## Implementation Details

All new routes should:

- Follow the same pattern as existing gateway routes (forward to chat-service)
- Include proper error handling (HTTPStatusError, RequestError)
- Have descriptive docstrings for Swagger
- Use appropriate tags for organization

## Files to Modify

- `services/gateway/main.py` - Add 3 new route handlers
- `services/chat-service/main.py` - Add missing tag to DELETE session endpoint