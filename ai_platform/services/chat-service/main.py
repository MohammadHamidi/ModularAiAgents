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
from agents.config_loader import load_agent_config, UserDataField, ConfigLoader
from pydantic import BaseModel
from typing import Optional, List

# Import tools
from tools.registry import ToolRegistry, DEFAULT_PERSONA_TOOLS
from tools.knowledge_base import KnowledgeBaseTool, GetLearningResourceTool
from tools.calculator import CalculatorTool
from tools.weather import WeatherTool
from tools.web_search import WebSearchTool, GetCompanyInfoTool

load_dotenv()

# Initialize logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Chat Service")


# =============================================================================
# Pydantic Models for Dynamic Field Management API
# =============================================================================

class FieldCreateRequest(BaseModel):
    """Request model for creating a new user data field."""
    field_name: str  # e.g., "favorite_color"
    normalized_name: str  # e.g., "user_favorite_color"
    description: str  # e.g., "User's favorite color"
    data_type: str = "string"  # "string", "integer", "list"
    enabled: bool = True
    aliases: List[str] = []  # e.g., ["color", "fav_color"]
    examples: List[str] = []  # e.g., ["red", "blue"]
    accumulate: bool = False  # For list types
    validation: dict = {}  # e.g., {"min": 0, "max": 100}

class FieldUpdateRequest(BaseModel):
    """Request model for updating a user data field."""
    description: Optional[str] = None
    data_type: Optional[str] = None
    enabled: Optional[bool] = None
    aliases: Optional[List[str]] = None
    examples: Optional[List[str]] = None
    accumulate: Optional[bool] = None
    validation: Optional[dict] = None

class FieldResponse(BaseModel):
    """Response model for a user data field."""
    field_name: str
    normalized_name: str
    description: str
    data_type: str
    enabled: bool
    aliases: List[str]
    examples: List[str]
    accumulate: bool
    validation: dict


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
AGENT_CONFIGS = {}  # Store configs for each agent for dynamic field management
session_manager = None
context_manager = None
http_client: httpx.AsyncClient | None = None
agent_full_config = None  # Default agent config (backwards compatible)

def register_agent(key: str, agent_class, config: dict, full_config=None):
    """Register agent with configuration"""
    agent_config = AgentConfig(**config)
    if full_config and agent_class == ChatAgent:
        agent = agent_class(agent_config, context_manager, full_config)
        AGENT_CONFIGS[key] = full_config
    else:
        agent = agent_class(agent_config, context_manager)
    AGENTS[key] = agent
    return agent

@app.on_event("startup")
async def startup():
    global session_manager, context_manager, http_client, agent_full_config
    
    # Initialize managers
    db_url = os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url, pool_pre_ping=True)
    
    session_manager = SessionManager(db_url)
    context_manager = ContextManager(engine)
    
    # Create global httpx client with LiteLLM compatibility hook
    http_client = httpx.AsyncClient(event_hooks={"response": [rewrite_service_tier]})

    # Base config for all agents
    base_config = {
        "api_key": os.getenv("LITELLM_API_KEY"),
        "base_url": os.getenv("LITELLM_BASE_URL", "https://api.avalai.ir/v1")
    }
    default_model = os.getenv("LITELLM_MODEL", "gemini-2.5-flash-lite-preview-09-2025")

    # Load default agent configuration from YAML
    config_file = os.getenv("AGENT_CONFIG_FILE", "agent_config.yaml")
    try:
        agent_full_config = load_agent_config(config_file)
        logging.info(f"Loaded default agent: {agent_full_config.agent_name} v{agent_full_config.agent_version}")
    except Exception as e:
        logging.error(f"Failed to load agent config from {config_file}: {e}")
        logging.info("Falling back to default config")
        agent_full_config = load_agent_config("agent_config.yaml")

    # Get model config from loaded configuration
    model_config = agent_full_config.model_config
    temperature = model_config.get("temperature", 0.7)
    max_turns = model_config.get("max_turns", 12)
    
    # ==========================================================================
    # Initialize Tool Registry with available tools
    # ==========================================================================
    logging.info("Initializing tool registry...")
    
    # Register all available tools
    ToolRegistry.register_tool(KnowledgeBaseTool())
    ToolRegistry.register_tool(GetLearningResourceTool())
    ToolRegistry.register_tool(CalculatorTool())
    ToolRegistry.register_tool(WeatherTool())
    ToolRegistry.register_tool(WebSearchTool())
    ToolRegistry.register_tool(GetCompanyInfoTool())
    
    logging.info(f"Registered {len(ToolRegistry.list_tools())} tools: {ToolRegistry.list_tools()}")
    
    # Define which tools each persona can use
    persona_tool_assignments = {
        "default": ["knowledge_base_search", "calculator", "get_weather"],
        "tutor": ["knowledge_base_search", "calculator", "get_learning_resource"],
        "professional": ["knowledge_base_search", "web_search", "get_company_info", "calculator"],
        "minimal": [],  # Privacy-focused, no external tools
    }
    
    # ==========================================================================
    # Load all personality configs and register multiple agents
    # ==========================================================================
    loader = ConfigLoader()
    available_configs = loader.list_available_configs()
    
    # Define persona mappings (key -> config file)
    persona_configs = {
        "default": "agent_config.yaml",
        "tutor": "personalities/friendly_tutor.yaml",
        "professional": "personalities/professional_assistant.yaml",
        "minimal": "personalities/minimal_assistant.yaml",
    }
    
    # Register each persona as a separate agent with their tools
    for agent_key, config_path in persona_configs.items():
        try:
            persona_config = load_agent_config(config_path)
            persona_model_config = persona_config.model_config
            
            # Get tools for this persona
            tool_names = persona_tool_assignments.get(agent_key, [])
            persona_tools = [ToolRegistry.get_tool(name) for name in tool_names if ToolRegistry.get_tool(name)]
            
            # Create agent config
            agent_config = AgentConfig(
                name=persona_config.agent_name,
                model=default_model,
                max_turns=persona_model_config.get("max_turns", max_turns),
                temperature=persona_model_config.get("temperature", temperature),
                extra={
                    **base_config,
                    "system_prompt": persona_config.get_complete_system_prompt()
                }
            )
            
            # Create agent with custom tools
            agent = ChatAgent(agent_config, context_manager, persona_config, custom_tools=persona_tools)
            AGENTS[agent_key] = agent
            AGENT_CONFIGS[agent_key] = persona_config
            
            logging.info(f"Registered agent '{agent_key}': {persona_config.agent_name} with {len(persona_tools)} tools")
        except Exception as e:
            logging.warning(f"Failed to load persona '{agent_key}' from {config_path}: {e}")
            import traceback
            traceback.print_exc()
            # Skip this persona but continue with others

    # Register translator (special agent, not a persona)
    register_agent("translator", TranslatorAgent, {
        "name": "Translator",
        "model": default_model,
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
    
    logging.info(f"Initialized {len(AGENTS)} agents: {list(AGENTS.keys())}")

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
    """List all available agents with their details."""
    result = {}
    for key, agent in AGENTS.items():
        agent_info = {
            "name": agent.config.name,
            "model": agent.config.model,
            "capabilities": agent.get_capabilities(),
            "max_turns": agent.config.max_turns
        }
        # Add persona description if available
        if key in AGENT_CONFIGS:
            agent_info["description"] = AGENT_CONFIGS[key].description
            agent_info["is_persona"] = True
        else:
            agent_info["is_persona"] = False
        result[key] = agent_info
    return result


@app.get("/personas")
async def list_personas():
    """List all available chat personas."""
    personas = []
    for key, config in AGENT_CONFIGS.items():
        # Get tools for this persona
        agent = AGENTS.get(key)
        tools = [t.name for t in agent.custom_tools] if agent and hasattr(agent, 'custom_tools') else []
        
        personas.append({
            "key": key,
            "name": config.agent_name,
            "version": config.agent_version,
            "description": config.description,
            "fields_count": len(config.get_enabled_fields()),
            "tools": tools,
        })
    return {
        "count": len(personas),
        "personas": personas,
        "usage": "POST /chat/{persona_key} with your message"
    }


@app.get("/tools")
async def list_tools():
    """List all available tools in the system."""
    tools = []
    for name, tool in ToolRegistry.get_all_tools().items():
        tools.append({
            "name": tool.name,
            "description": tool.description[:100] + "..." if len(tool.description) > 100 else tool.description,
            "enabled": tool.enabled,
            "parameters": list(tool.parameters.get("properties", {}).keys())
        })
    return {
        "count": len(tools),
        "tools": tools
    }


@app.get("/tools/{tool_name}")
async def get_tool_info(tool_name: str):
    """Get detailed information about a specific tool."""
    tool = ToolRegistry.get_tool(tool_name)
    if not tool:
        raise HTTPException(404, f"Tool '{tool_name}' not found")
    
    return {
        "name": tool.name,
        "description": tool.description,
        "enabled": tool.enabled,
        "parameters": tool.parameters
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

# =============================================================================
# Dynamic Field Management API
# =============================================================================

@app.get("/config/fields", tags=["Config"])
async def list_fields():
    """List all configured user data fields."""
    global agent_full_config
    if not agent_full_config:
        raise HTTPException(500, "Agent config not loaded")
    
    fields = []
    for f in agent_full_config.user_data_fields:
        fields.append({
            "field_name": f.field_name,
            "normalized_name": f.normalized_name,
            "description": f.description,
            "data_type": f.data_type,
            "enabled": f.enabled,
            "aliases": f.aliases,
            "examples": f.examples,
            "accumulate": f.accumulate,
            "validation": f.validation,
        })
    
    return {
        "count": len(fields),
        "enabled_count": len([f for f in fields if f["enabled"]]),
        "fields": fields
    }


@app.get("/config/fields/{field_name}", tags=["Config"])
async def get_field(field_name: str):
    """Get a specific field by name."""
    global agent_full_config
    if not agent_full_config:
        raise HTTPException(500, "Agent config not loaded")
    
    field = agent_full_config.get_field_by_name(field_name)
    if not field:
        raise HTTPException(404, f"Field '{field_name}' not found")
    
    return {
        "field_name": field.field_name,
        "normalized_name": field.normalized_name,
        "description": field.description,
        "data_type": field.data_type,
        "enabled": field.enabled,
        "aliases": field.aliases,
        "examples": field.examples,
        "accumulate": field.accumulate,
        "validation": field.validation,
    }


@app.post("/config/fields", tags=["Config"])
async def add_field(request: FieldCreateRequest):
    """Add a new user data field at runtime."""
    global agent_full_config, AGENTS
    if not agent_full_config:
        raise HTTPException(500, "Agent config not loaded")
    
    # Check if field already exists
    existing = agent_full_config.get_field_by_name(request.field_name)
    if existing:
        raise HTTPException(400, f"Field '{request.field_name}' already exists")
    
    # Check if normalized_name is unique
    for f in agent_full_config.user_data_fields:
        if f.normalized_name == request.normalized_name:
            raise HTTPException(400, f"Normalized name '{request.normalized_name}' already in use")
    
    # Create new field
    new_field = UserDataField(
        field_name=request.field_name,
        normalized_name=request.normalized_name,
        description=request.description,
        data_type=request.data_type,
        enabled=request.enabled,
        aliases=request.aliases,
        examples=request.examples,
        accumulate=request.accumulate,
        validation=request.validation,
    )
    
    # Add to config
    agent_full_config.user_data_fields.append(new_field)
    
    # Update the default agent's field_map and reinitialize tools
    if "default" in AGENTS:
        AGENTS["default"].field_map = agent_full_config.build_field_map()
        AGENTS["default"].agent_config = agent_full_config
        # Reinitialize to update tool description
        await AGENTS["default"].reinitialize_tools()
    
    logging.info(f"Added new field: {request.field_name} -> {request.normalized_name}")
    
    return {
        "status": "created",
        "field": {
            "field_name": new_field.field_name,
            "normalized_name": new_field.normalized_name,
            "description": new_field.description,
            "data_type": new_field.data_type,
            "enabled": new_field.enabled,
        },
        "tools_reinitialized": True
    }


@app.put("/config/fields/{field_name}", tags=["Config"])
async def update_field(field_name: str, request: FieldUpdateRequest):
    """Update an existing user data field."""
    global agent_full_config, AGENTS
    if not agent_full_config:
        raise HTTPException(500, "Agent config not loaded")
    
    # Find the field
    field = None
    for f in agent_full_config.user_data_fields:
        if f.field_name.lower() == field_name.lower():
            field = f
            break
    
    if not field:
        raise HTTPException(404, f"Field '{field_name}' not found")
    
    # Update fields
    if request.description is not None:
        field.description = request.description
    if request.data_type is not None:
        field.data_type = request.data_type
    if request.enabled is not None:
        field.enabled = request.enabled
    if request.aliases is not None:
        field.aliases = request.aliases
    if request.examples is not None:
        field.examples = request.examples
    if request.accumulate is not None:
        field.accumulate = request.accumulate
    if request.validation is not None:
        field.validation = request.validation
    
    # Update the default agent's field_map
    if "default" in AGENTS:
        AGENTS["default"].field_map = agent_full_config.build_field_map()
    
    logging.info(f"Updated field: {field_name}")
    
    return {
        "status": "updated",
        "field": {
            "field_name": field.field_name,
            "normalized_name": field.normalized_name,
            "description": field.description,
            "data_type": field.data_type,
            "enabled": field.enabled,
            "aliases": field.aliases,
        }
    }


@app.delete("/config/fields/{field_name}", tags=["Config"])
async def delete_field(field_name: str, permanent: bool = False):
    """
    Delete or disable a user data field.
    
    - permanent=false (default): Only disables the field
    - permanent=true: Permanently removes the field
    """
    global agent_full_config, AGENTS
    if not agent_full_config:
        raise HTTPException(500, "Agent config not loaded")
    
    # Find the field
    field_idx = None
    for i, f in enumerate(agent_full_config.user_data_fields):
        if f.field_name.lower() == field_name.lower():
            field_idx = i
            break
    
    if field_idx is None:
        raise HTTPException(404, f"Field '{field_name}' not found")
    
    if permanent:
        # Remove completely
        removed = agent_full_config.user_data_fields.pop(field_idx)
        logging.info(f"Permanently deleted field: {field_name}")
        status = "deleted"
    else:
        # Just disable
        agent_full_config.user_data_fields[field_idx].enabled = False
        logging.info(f"Disabled field: {field_name}")
        status = "disabled"
    
    # Update the default agent's field_map and reinitialize tools
    if "default" in AGENTS:
        AGENTS["default"].field_map = agent_full_config.build_field_map()
        await AGENTS["default"].reinitialize_tools()
    
    return {"status": status, "field_name": field_name, "tools_reinitialized": True}


@app.post("/config/fields/{field_name}/enable", tags=["Config"])
async def enable_field(field_name: str):
    """Re-enable a disabled field."""
    global agent_full_config, AGENTS
    if not agent_full_config:
        raise HTTPException(500, "Agent config not loaded")
    
    # Find and enable
    for f in agent_full_config.user_data_fields:
        if f.field_name.lower() == field_name.lower():
            f.enabled = True
            if "default" in AGENTS:
                AGENTS["default"].field_map = agent_full_config.build_field_map()
            return {"status": "enabled", "field_name": field_name}
    
    raise HTTPException(404, f"Field '{field_name}' not found")


@app.post("/config/reload", tags=["Config"])
async def reload_config():
    """
    Reload configuration from YAML file.
    This will reset all runtime changes and reload from disk.
    """
    global agent_full_config, AGENTS
    
    config_file = os.getenv("AGENT_CONFIG_FILE", "agent_config.yaml")
    try:
        agent_full_config = load_agent_config(config_file)
        
        # Update agents with new config
        if "default" in AGENTS:
            AGENTS["default"].agent_config = agent_full_config
            AGENTS["default"].field_map = agent_full_config.build_field_map()
        
        logging.info(f"Reloaded config: {agent_full_config.agent_name} v{agent_full_config.agent_version}")
        
        return {
            "status": "reloaded",
            "agent_name": agent_full_config.agent_name,
            "agent_version": agent_full_config.agent_version,
            "fields_count": len(agent_full_config.user_data_fields),
            "enabled_fields": len(agent_full_config.get_enabled_fields())
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to reload config: {str(e)}")


@app.get("/config/export", tags=["Config"])
async def export_config():
    """Export current configuration as JSON (for backup or transfer)."""
    global agent_full_config
    if not agent_full_config:
        raise HTTPException(500, "Agent config not loaded")
    
    return {
        "agent_name": agent_full_config.agent_name,
        "agent_version": agent_full_config.agent_version,
        "description": agent_full_config.description,
        "user_data_fields": [
            {
                "field_name": f.field_name,
                "normalized_name": f.normalized_name,
                "description": f.description,
                "data_type": f.data_type,
                "enabled": f.enabled,
                "aliases": f.aliases,
                "examples": f.examples,
                "accumulate": f.accumulate,
                "validation": f.validation,
            }
            for f in agent_full_config.user_data_fields
        ],
        "context_display": agent_full_config.context_display,
        "model_config": agent_full_config.model_config,
    }


@app.on_event("shutdown")
async def shutdown():
    global http_client
    
    await session_manager.dispose()
    await context_manager.engine.dispose()
    
    # Close global http client
    if http_client is not None:
        await http_client.aclose()