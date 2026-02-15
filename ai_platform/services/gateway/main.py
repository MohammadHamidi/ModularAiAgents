import os
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import httpx
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

load_dotenv()

app = FastAPI(
    title="AI Platform Gateway API",
    description="""
    Gateway service for the AI Platform that routes requests to backend services.
    
    ## Features
    - Routes chat requests to chat-service
    - Serves the Chat UI at `/ui`
    - Provides health checks and service status
    - Manages session context and user data
    
    ## API Endpoints
    - `/chat/init` - Initialize chat session from Safiranayeha website
    - `/chat/{agent_key}` - Send messages to AI agents
    - `/chat/{agent_key}/stream` - Stream messages to AI agents (SSE)
    - `/agents` - List available AI agents
    - `/session/{session_id}/context` - Get session context
    - `/session/{session_id}/user-data` - Get user data for a session
    - `/health` - Service health check
    """,
    version="1.0.0",
    docs_url="/doc",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Enable CORS so that browser clients (including file:// origins) can call the gateway
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For now allow all origins; can be restricted later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chat service URL (internal Docker network)
CHAT_SERVICE_URL = os.getenv("CHAT_SERVICE_URL", "http://chat-service:8001")

# HTTP client for forwarding requests
http_client = httpx.AsyncClient(base_url=CHAT_SERVICE_URL, timeout=60.0)

# Path to static files (Chat.html and other UI files)
# In Docker, the project root is mounted at /app
# For local development, try multiple paths
def find_static_file(filename: str) -> Path:
    """Find static file in Docker or local development paths"""
    gateway_dir = Path(__file__).parent
    # Try gateway's own directory first (file shipped with gateway, works in any deployment)
    gateway_file = gateway_dir / filename
    if gateway_file.exists():
        return gateway_file
    # Docker: /app/filename or /app/ai_platform/filename
    for docker_path in [Path("/app") / filename, Path("/app") / "ai_platform" / filename]:
        if docker_path.exists():
            return docker_path
    # Local: ai_platform/filename, services/filename
    for path in [gateway_dir.parent.parent / filename, gateway_dir.parent / filename]:
        if path.exists():
            return path
    return gateway_file  # may 404 if not found

CHAT_HTML_PATH = find_static_file("Chat.html")
ICON_PATH = find_static_file("Icon.png")
FAVICON_PATH = find_static_file("favicon.ico")
MONITORING_DASHBOARD_PATH = find_static_file("monitoring_dashboard.html")
LOG_VIEWER_PATH = find_static_file("log_viewer.html")
USERS_VIEW_PATH = find_static_file("users_view.html")
FEEDBACK_VIEWER_PATH = find_static_file("feedback_viewer.html")


# =============================================================================
# Pydantic Models for API Documentation
# =============================================================================

class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str
    session_id: Optional[str] = None
    user_data: Optional[Dict[str, Any]] = None
    use_shared_context: bool = True
    
    class Config:
        schema_extra = {
            "example": {
                "message": "سلام! سفیران آیه ها چیست؟",
                "session_id": None,
                "user_data": {
                    "name": "علی",
                    "city": "تهران"
                },
                "use_shared_context": True
            }
        }

class ChatInitRequest(BaseModel):
    """Request model for initializing chat from Safiranayeha website."""
    encrypted_param: Optional[str] = None  # Optional encrypted parameter from URL
    user_id: Optional[str] = None  # Direct user_id (alternative to encrypted_param)
    path: Optional[str] = None  # Website path (alternative to encrypted_param)
    from_path: Optional[str] = None  # Page user came from (e.g., from /ai?from=/actions/40)
    
    class Config:
        schema_extra = {
            "example": {
                "encrypted_param": "encrypted_base64_string_from_url",
                "from_path": "/actions/40"
            }
        }

class ChatInitResponse(BaseModel):
    """Response model for chat initialization."""
    session_id: str
    agent_key: str
    user_data: Optional[Dict[str, Any]] = None
    welcome_message: Optional[str] = None
    conversation_starters: Optional[List[str]] = None
    subtitle: Optional[str] = None

class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    output: str
    session_id: str
    suggestions: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    service: str
    chat_service: Optional[str] = None
    error: Optional[str] = None

@app.get("/ui", response_class=HTMLResponse, tags=["UI"])
async def serve_chat_ui():
    """
    Serve the Chat UI interface.
    
    Returns the main Chat.html file for the AI chat interface.
    """
    if CHAT_HTML_PATH.exists():
        return FileResponse(
            CHAT_HTML_PATH,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"}
        )
    else:
        raise HTTPException(status_code=404, detail="Chat.html not found")

@app.get("/favicon.ico", tags=["UI"])
async def serve_favicon():
    """Serve the favicon (browser tab icon)."""
    if FAVICON_PATH.exists():
        return FileResponse(FAVICON_PATH, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="Favicon not found")

@app.get("/ui/icon.png", tags=["UI"])
async def serve_icon():
    """
    Serve the application icon.

    Returns the Icon.png file used in the UI.
    """
    if ICON_PATH.exists():
        return FileResponse(ICON_PATH, media_type="image/png")
    else:
        raise HTTPException(status_code=404, detail="Icon.png not found")

@app.get("/monitoring/dashboard", response_class=HTMLResponse, tags=["Monitoring", "UI"])
async def serve_monitoring_dashboard():
    """
    Serve the Monitoring Dashboard UI.

    Returns an interactive dashboard for monitoring agent execution traces,
    system prompts, KB queries, tool calls, and performance metrics.
    """
    if MONITORING_DASHBOARD_PATH.exists():
        return FileResponse(
            MONITORING_DASHBOARD_PATH,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"}
        )
    else:
        raise HTTPException(status_code=404, detail="monitoring_dashboard.html not found")


@app.get("/monitoring/logs/view", response_class=HTMLResponse, tags=["Monitoring", "UI"])
async def serve_log_viewer():
    """
    Serve the Service Log Viewer UI.

    Returns an interactive log viewer for persisted API requests, traces,
    and conversation logs with filtering, sorting, and pagination.
    """
    if LOG_VIEWER_PATH.exists():
        return FileResponse(
            LOG_VIEWER_PATH,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"}
        )
    else:
        raise HTTPException(status_code=404, detail="log_viewer.html not found")

@app.get("/monitoring/feedback", response_class=HTMLResponse, tags=["Monitoring", "UI"])
async def serve_feedback_viewer():
    """Serve the Chat Feedback admin page."""
    if FEEDBACK_VIEWER_PATH.exists():
        return FileResponse(
            FEEDBACK_VIEWER_PATH,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"}
        )
    raise HTTPException(status_code=404, detail="feedback_viewer.html not found")

@app.get("/health", tags=["Health"], response_model=HealthResponse)
async def health():
    """
    Gateway service health check.
    
    Returns the health status of the gateway and its connection to the chat service.
    """
    try:
        # Check if chat service is available
        response = await http_client.get("/health")
        return {
            "status": "healthy",
            "service": "gateway",
            "chat_service": "connected" if response.status_code == 200 else "disconnected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "gateway",
            "error": str(e)
        }

@app.get("/agents", tags=["Agents"])
async def list_agents():
    """
    List all available AI agents.
    
    Returns a list of all registered AI agents with their configurations,
    capabilities, and metadata.
    """
    try:
        response = await http_client.get("/agents")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.get("/personas", tags=["Agents"])
async def list_personas():
    """
    List all available chat personas.
    
    Returns a list of all configured personas with their keys, names, versions,
    descriptions, field counts, and available tools.
    """
    try:
        response = await http_client.get("/personas")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.get("/tools", tags=["Tools"])
async def list_tools():
    """
    List all available tools in the system.
    
    Returns a list of all registered tools with their names, descriptions,
    enabled status, and parameters.
    """
    try:
        response = await http_client.get("/tools")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.get("/tools/{tool_name}", tags=["Tools"])
async def get_tool_info(tool_name: str):
    """
    Get detailed information about a specific tool.
    
    Returns comprehensive information about the specified tool including
    its name, description, enabled status, and full parameter schema.
    
    - **tool_name**: The name/identifier of the tool to query
    """
    try:
        response = await http_client.get(f"/tools/{tool_name}")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.post("/chat/init", tags=["Chat", "Safiranayeha"], response_model=ChatInitResponse)
async def initialize_chat(request: ChatInitRequest):
    """
    Initialize chat session from Safiranayeha website.
    
    This endpoint handles the encrypted parameter from the Safiranayeha website,
    decrypts it, fetches user data, determines the appropriate agent based on the path,
    and creates a new chat session with pre-loaded user context.
    
    **Flow:**
    1. Decrypt URL parameter to get UserId and Path
    2. Login to Safiranayeha API and fetch user data
    3. Map Path to appropriate AI agent
    4. Create new session with user context
    5. Return session_id and agent_key for chat interface
    
    **Parameters:**
    - **encrypted_param**: AES encrypted base64 string from URL (contains UserId and Path)
    - **user_id**: (Optional) Direct user_id if not using encrypted_param
    - **path**: (Optional) Website path if not using encrypted_param
    
    **Returns:**
    - session_id: UUID for the chat session
    - agent_key: AI agent assigned based on path
    - user_data: User information loaded from Safiranayeha
    - welcome_message: (Optional) Initial greeting from the agent
    """
    try:
        # Exclude None values to avoid validation errors in chat-service
        request_dict = request.dict(exclude_none=True)
        response = await http_client.post("/chat/init", json=request_dict)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.post("/chat/{agent_key}", tags=["Chat"], response_model=ChatResponse)
async def chat(agent_key: str, request: ChatRequest):
    """
    Send a message to an AI agent.
    
    - **agent_key**: The identifier of the agent to use (e.g., 'default', 'tutor', 'professional')
    - **request**: JSON body containing:
      - `message`: The user's message (required)
      - `session_id`: Optional session ID for conversation continuity
      - `user_data`: Optional user data to save/update
      - `use_shared_context`: Whether to use shared context across agents (default: true)
    
    Returns the agent's response with suggestions and metadata.
    """
    try:
        # Exclude None values to avoid validation errors in chat-service
        request_dict = request.dict(exclude_none=True)
        response = await http_client.post(f"/chat/{agent_key}", json=request_dict)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.post("/chat/{agent_key}/stream", tags=["Chat"])
async def chat_stream(agent_key: str, request: ChatRequest):
    """
    Stream a message to an AI agent (Server-Sent Events).
    
    Forwards streaming requests to the chat-service and streams the response
    back to the client as Server-Sent Events (SSE).
    
    - **agent_key**: The identifier of the agent (e.g., 'orchestrator', 'default', 'tutor')
    - **request**: JSON body containing message, session_id, user_data, etc.
    
    Returns a streaming response with SSE format.
    """
    async def forward_stream():
        """Forward stream from chat-service to client"""
        # Create client with longer timeout for streaming
        # The context manager will stay open as long as the generator is active
        async with httpx.AsyncClient(base_url=CHAT_SERVICE_URL, timeout=300.0) as client:
            try:
                # Exclude None values to avoid validation errors in chat-service
                request_dict = request.dict(exclude_none=True)
                async with client.stream(
                    "POST",
                    f"/chat/{agent_key}/stream",
                    json=request_dict
                ) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except httpx.HTTPStatusError as e:
                # For HTTP errors, try to read the error response
                try:
                    error_msg = (await e.response.aread()).decode() if e.response else str(e)
                except Exception:
                    error_msg = str(e)
                yield f"data: {json.dumps({'error': error_msg})}\n\n".encode()
            except httpx.RequestError as e:
                yield f"data: {json.dumps({'error': f'Chat service unavailable: {str(e)}'})}\n\n".encode()
    
    return StreamingResponse(
        forward_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/session/{session_id}/context", tags=["Sessions"])
async def get_session_context(session_id: str):
    """
    Get the context data for a session.
    
    Returns all context information stored for the given session,
    including user data and conversation context.
    """
    try:
        response = await http_client.get(f"/session/{session_id}/context")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.get("/session/{session_id}/history", tags=["Sessions"])
async def get_session_history(session_id: str):
    """
    Get session messages and metadata for conversation history.
    
    Returns messages, agent_type, and metadata for rendering when
    user selects a session from the sidebar.
    """
    try:
        response = await http_client.get(f"/session/{session_id}/history")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.get("/user/sessions", tags=["Sessions"])
async def list_user_sessions(session_id: Optional[str] = None):
    """
    List all sessions for the user who owns the given session.
    
    Requires session_id from a session created via chat/init.
    Returns empty list for guests.
    """
    try:
        params = {"session_id": session_id} if session_id else {}
        response = await http_client.get("/user/sessions", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.get("/session/{session_id}/user-data", tags=["Sessions"])
async def get_session_user_data(session_id: str):
    """
    Get user data for a session.
    
    Returns the user-specific data stored for the given session,
    such as name, location, preferences, etc.
    """
    try:
        response = await http_client.get(f"/session/{session_id}/user-data")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.delete("/session/{session_id}", tags=["Sessions"])
async def delete_session(session_id: str):
    """
    Delete a session and all its associated data.
    
    Permanently removes the session, its conversation history,
    context, and user data.
    """
    try:
        response = await http_client.delete(f"/session/{session_id}")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

# =============================================================================
# Config API (Forward to chat-service)
# =============================================================================

@app.get("/config", tags=["Config"])
async def get_config():
    """Get feature flags (e.g. feedback_enabled) for Chat UI."""
    try:
        response = await http_client.get("/config")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

# =============================================================================
# Chat Feedback API (Forward to chat-service)
# =============================================================================

@app.post("/api/v1/chat/feedback", tags=["Feedback"])
async def submit_feedback(request: Request):
    """Submit message-level feedback (like/dislike)."""
    try:
        body = await request.json()
        response = await http_client.post("/api/v1/chat/feedback", json=body)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.get("/api/v1/chat/feedback", tags=["Feedback"])
async def list_feedback(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    feedback_type: Optional[str] = None,
    reason: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    sort: str = "desc",
):
    """List feedback with filters (admin)."""
    try:
        params = {"page": page, "limit": limit, "sort": sort}
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        if feedback_type:
            params["feedback_type"] = feedback_type
        if reason:
            params["reason"] = reason
        if user_id:
            params["user_id"] = user_id
        if session_id:
            params["session_id"] = session_id
        response = await http_client.get("/api/v1/chat/feedback", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.get("/api/v1/chat/feedback/export", tags=["Feedback"])
async def export_feedback(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    feedback_type: Optional[str] = None,
    reason: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
):
    """Export feedback as CSV (admin)."""
    try:
        params = {}
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        if feedback_type:
            params["feedback_type"] = feedback_type
        if reason:
            params["reason"] = reason
        if user_id:
            params["user_id"] = user_id
        if session_id:
            params["session_id"] = session_id
        response = await http_client.get("/api/v1/chat/feedback/export", params=params)
        response.raise_for_status()
        async def stream():
            async for chunk in response.aiter_bytes():
                yield chunk
        return StreamingResponse(
            stream(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=chat_feedback.csv"}
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

# =============================================================================
# Monitoring API Endpoints (Forward to chat-service)
# =============================================================================

@app.get("/monitoring/traces", tags=["Monitoring"])
async def get_monitoring_traces(
    session_id: Optional[str] = None,
    agent_key: Optional[str] = None,
    limit: int = 50
):
    """
    Get execution traces for monitoring and debugging.

    Forwards the request to chat-service monitoring endpoint.
    Returns execution traces with system prompts, KB queries, tool calls, and performance metrics.
    """
    try:
        params = {"limit": limit}
        if session_id:
            params["session_id"] = session_id
        if agent_key:
            params["agent_key"] = agent_key

        response = await http_client.get("/monitoring/traces", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")


@app.get("/monitoring/traces/recent", tags=["Monitoring"])
async def get_recent_monitoring_traces(count: int = 20):
    """
    Get the most recent execution traces.

    Returns the N most recent traces for live monitoring dashboards.
    """
    try:
        response = await http_client.get("/monitoring/traces/recent", params={"count": count})
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")


@app.get("/monitoring/trace/{trace_id}", tags=["Monitoring"])
async def get_monitoring_trace(trace_id: str):
    """
    Get a specific trace by its ID.

    Returns complete details of a single execution trace.
    """
    try:
        response = await http_client.get(f"/monitoring/trace/{trace_id}")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")


@app.get("/monitoring/stats", tags=["Monitoring"])
async def get_monitoring_stats():
    """
    Get monitoring statistics.

    Returns aggregate statistics about collected traces.
    """
    try:
        response = await http_client.get("/monitoring/stats")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")


@app.delete("/monitoring/traces", tags=["Monitoring"])
async def clear_monitoring_traces():
    """
    Clear all collected traces.

    Removes all traces from memory. Use with caution.
    """
    try:
        response = await http_client.delete("/monitoring/traces")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")


@app.get("/monitoring/logs", tags=["Monitoring"])
async def get_service_logs(
    page: int = 1,
    limit: int = 50,
    session_id: Optional[str] = None,
    agent_key: Optional[str] = None,
    log_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    sort: str = "desc",
    search: Optional[str] = None,
):
    """Query persisted service logs with filters and pagination."""
    try:
        params = {"page": page, "limit": limit, "sort": sort}
        if session_id:
            params["session_id"] = session_id
        if agent_key:
            params["agent_key"] = agent_key
        if log_type:
            params["log_type"] = log_type
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        if search:
            params["search"] = search
        response = await http_client.get("/monitoring/logs", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")


@app.get("/monitoring/logs/stats", tags=["Monitoring"])
async def get_service_logs_stats(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
):
    """Get aggregate stats for service logs."""
    try:
        params = {}
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        response = await http_client.get("/monitoring/logs/stats", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")


@app.get("/monitoring/users/view", response_class=HTMLResponse, tags=["Monitoring", "UI"])
async def serve_users_view():
    """
    Serve the User Management UI: list users (Safiranayeha user IDs), view details,
    GetAIUserData, sessions, chat history, and context per user.
    """
    if USERS_VIEW_PATH.exists():
        return FileResponse(
            USERS_VIEW_PATH,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"}
        )
    raise HTTPException(status_code=404, detail="users_view.html not found")


@app.get("/monitoring/users", tags=["Monitoring"])
async def list_monitoring_users(
    page: int = 1,
    limit: int = 25,
    search: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    min_sessions: Optional[int] = None,
    sort: str = "desc",
):
    """List users with session counts and last activity. Paginated; supports search, date range, min_sessions."""
    try:
        params = {"page": page, "limit": limit, "sort": sort}
        if search is not None:
            params["search"] = search
        if from_date is not None:
            params["from_date"] = from_date
        if to_date is not None:
            params["to_date"] = to_date
        if min_sessions is not None:
            params["min_sessions"] = min_sessions
        response = await http_client.get("/monitoring/users", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")


@app.get("/monitoring/users/{user_id}", tags=["Monitoring"])
async def get_monitoring_user_detail(user_id: str):
    """Get full user detail: GetAIUserData, sessions, chat history, context."""
    try:
        response = await http_client.get(f"/monitoring/users/{user_id}")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")


@app.on_event("shutdown")
async def shutdown():
    """Close HTTP client on shutdown"""
    await http_client.aclose()
