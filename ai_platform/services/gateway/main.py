import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import httpx
from pathlib import Path

load_dotenv()

app = FastAPI(title="Gateway Service")

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

@app.get("/ui", response_class=HTMLResponse)
async def serve_chat_ui():
    """Serve Chat.html at /ui endpoint"""
    if CHAT_HTML_PATH.exists():
        return FileResponse(
            CHAT_HTML_PATH,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"}
        )
    else:
        raise HTTPException(status_code=404, detail="Chat.html not found")

@app.get("/ui/icon.png")
async def serve_icon():
    """Serve Icon.png"""
    if ICON_PATH.exists():
        return FileResponse(ICON_PATH, media_type="image/png")
    else:
        raise HTTPException(status_code=404, detail="Icon.png not found")

@app.get("/health")
async def health():
    """Gateway health check"""
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

@app.get("/agents")
async def list_agents():
    """Forward request to chat service"""
    try:
        response = await http_client.get("/agents")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.post("/chat/{agent_key}")
async def chat(agent_key: str, request: dict):
    """Forward chat request to chat service"""
    try:
        response = await http_client.post(f"/chat/{agent_key}", json=request)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.get("/session/{session_id}/context")
async def get_session_context(session_id: str):
    """Forward request to chat service"""
    try:
        response = await http_client.get(f"/session/{session_id}/context")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.get("/session/{session_id}/user-data")
async def get_session_user_data(session_id: str):
    """Forward request to chat service"""
    try:
        response = await http_client.get(f"/session/{session_id}/user-data")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Chat service unavailable: {str(e)}")

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Forward request to chat service"""
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
