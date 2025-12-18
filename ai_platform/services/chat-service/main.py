# services/chat-service/main.py
import os
import uuid
import logging
import json
import time
import httpx
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

from shared.database import SessionManager
from shared.context_manager import ContextManager
from shared.base_agent import AgentRequest, AgentConfig
from agents.chat_agent import ChatAgent
from agents.translator_agent import TranslatorAgent
from agents.litellm_compat import rewrite_service_tier
from agents.config_loader import load_agent_config

load_dotenv()

# Initialize logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Chat Service")


# #region agent log helper
DEBUG_LOG_PATH = os.getenv(
    "AGENT_DEBUG_LOG_PATH",
    r"c:\Users\user\Desktop\AI\ModularAiAgents\.cursor\debug.log",
)


def _agent_debug_log(hypothesis_id: str, location: str, message: str, data: dict):
    """Append a single NDJSON debug line for agent debugging."""
    payload = {
        "sessionId": "debug-session",
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # Never let logging break the service
        pass


# #endregion

# Global managers and clients
AGENTS = {}
session_manager = None
context_manager = None
http_client: httpx.AsyncClient | None = None

def register_agent(key: str, agent_class, config: dict, full_config=None):
    """Register agent with configuration"""
    agent_config = AgentConfig(**config)
    if full_config and agent_class == ChatAgent:
        agent = agent_class(agent_config, context_manager, full_config)
    else:
        agent = agent_class(agent_config, context_manager)
    AGENTS[key] = agent
    return agent

@app.on_event("startup")
async def startup():
    global session_manager, context_manager, http_client
    
    # Initialize managers
    db_url = os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url, pool_pre_ping=True)
    
    session_manager = SessionManager(db_url)
    context_manager = ContextManager(engine)
    
    # Create global httpx client with LiteLLM compatibility hook
    http_client = httpx.AsyncClient(event_hooks={"response": [rewrite_service_tier]})

    # Load agent configuration from YAML
    # Can be customized via AGENT_CONFIG_FILE environment variable
    config_file = os.getenv("AGENT_CONFIG_FILE", "agent_config.yaml")
    try:
        agent_full_config = load_agent_config(config_file)
        logging.info(f"Loaded agent config: {agent_full_config.agent_name} v{agent_full_config.agent_version}")
    except Exception as e:
        logging.error(f"Failed to load agent config from {config_file}: {e}")
        logging.info("Falling back to default config")
        agent_full_config = load_agent_config("agent_config.yaml")

    # Register agents
    base_config = {
        "api_key": os.getenv("LITELLM_API_KEY"),
        "base_url": os.getenv("LITELLM_BASE_URL", "https://api.avalai.ir/v1")
    }

    # Get model config from loaded configuration or environment
    model_config = agent_full_config.model_config
    default_model = model_config.get("default_model", "gemini-2.5-flash-lite-preview-09-2025")
    temperature = model_config.get("temperature", 0.7)
    max_turns = model_config.get("max_turns", 12)

    # Register default agent with full configuration
    register_agent("default", ChatAgent, {
        "name": agent_full_config.agent_name,
        "model": os.getenv("LITELLM_MODEL", default_model),
        "max_turns": max_turns,
        "temperature": temperature,
        "extra": {
            **base_config,
            "system_prompt": agent_full_config.get_complete_system_prompt()
        }
    }, full_config=agent_full_config)
    
    register_agent("translator", TranslatorAgent, {
        "name": "Translator",
        "model": os.getenv("LITELLM_MODEL", "gemini-2.5-flash-lite-preview-09-2025"),
        "max_turns": 8,
        "temperature": 0.3,
        "extra": {
            **base_config,
            "system_prompt": "You are a professional translator. Translate accurately and naturally."
        }
    })
    
    # Initialize all agents with shared http_client
    for key, agent in AGENTS.items():
        await agent.initialize(http_client=http_client)

    # Debug log: startup completed and agents registered
    _agent_debug_log(
        hypothesis_id="H1",
        location="services/chat-service/main.py:startup",
        message="startup completed",
        data={"agents": list(AGENTS.keys())},
    )

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "chat",
        "agents": list(AGENTS.keys())
    }

@app.get("/agents")
async def list_agents():
    return {
        key: {
            "name": agent.config.name,
            "model": agent.config.model,
            "capabilities": agent.get_capabilities(),
            "max_turns": agent.config.max_turns
        }
        for key, agent in AGENTS.items()
    }

@app.post("/chat/{agent_key}")
async def chat(agent_key: str, request: AgentRequest):
    if agent_key not in AGENTS:
        raise HTTPException(404, f"Agent '{agent_key}' not found")
    
    agent = AGENTS[agent_key]
    
    # Handle session
    if request.session_id:
        try:
            sid = uuid.UUID(request.session_id)
        except ValueError:
            raise HTTPException(400, "Invalid session_id format")
    else:
        sid = uuid.uuid4()

    # Debug log: chat entry before loading history/context
    _agent_debug_log(
        hypothesis_id="H2",
        location="services/chat-service/main.py:chat:entry",
        message="chat request received",
        data={
            "agent_key": agent_key,
            "has_session_id": bool(request.session_id),
        },
    )

    # Load session history
    session = await session_manager.get_session(sid)
    history = session["messages"] if session else []

    # Load shared context
    shared_context = {}
    if request.use_shared_context:
        shared_context = await context_manager.get_context(sid) or {}

    # Process with agent (history + structured shared context)
    request.session_id = str(sid)
    response = await agent.process(request, history, shared_context)

    # Debug log: after agent processing, before persistence
    _agent_debug_log(
        hypothesis_id="H3",
        location="services/chat-service/main.py:chat:post-process",
        message="chat processed",
        data={
            "agent_key": agent_key,
            "history_len": len(history),
        },
    )
    
    # Save context updates
    if response.context_updates:
        await context_manager.merge_context(
            sid, 
            response.context_updates, 
            agent_type=agent_key
        )
    
    # Save session (agent should return updated history in metadata)
    new_history = response.metadata.get("history", history)
    await session_manager.upsert_session(
        sid, 
        new_history, 
        agent_key,
        metadata={"last_agent": agent_key}
    )
    
    return response

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete session and its context"""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(400, "Invalid session_id")
    
    # Delete from both managers
    await context_manager.delete_context(sid)
    # Add delete method to SessionManager if needed
    
    return {"status": "deleted", "session_id": session_id}

@app.get("/session/{session_id}/context")
async def get_session_context(session_id: str):
    """Get all shared context for session"""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(400, "Invalid session_id")
    
    context = await context_manager.get_context(sid)
    return {"session_id": session_id, "context": context or {}}

@app.on_event("shutdown")
async def shutdown():
    global http_client
    
    await session_manager.dispose()
    await context_manager.engine.dispose()
    
    # Close global http client
    if http_client is not None:
        await http_client.aclose()