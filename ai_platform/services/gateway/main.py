import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
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
    - `/chat/{agent_key}` - Send messages to AI agents
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
STATIC_FILES_PATH = Path("/app")
CHAT_HTML_PATH = STATIC_FILES_PATH / "Chat.html"
ICON_PATH = STATIC_FILES_PATH / "Icon.png"


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
        response = await http_client.post(f"/chat/{agent_key}", json=request.dict())
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

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

@app.on_event("shutdown")
async def shutdown():
    """Close HTTP client on shutdown"""
    await http_client.aclose()
