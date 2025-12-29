# services/chat-service/main.py
import os
import uuid
import logging
import json
import time
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from shared.database import SessionManager
from shared.context_manager import ContextManager
from shared.base_agent import AgentRequest, AgentConfig
from agents.chat_agent import ChatAgent
from agents.translator_agent import TranslatorAgent
from agents.litellm_compat import rewrite_service_tier
from agents.config_loader import load_agent_config, UserDataField, ConfigLoader
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# Import tools
from tools.registry import ToolRegistry, DEFAULT_PERSONA_TOOLS
from tools.knowledge_base import KnowledgeBaseTool, GetLearningResourceTool
from tools.calculator import CalculatorTool
from tools.weather import WeatherTool
from tools.web_search import WebSearchTool, GetCompanyInfoTool
from tools.konesh_query import KoneshQueryTool

load_dotenv()

# Initialize logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="AI Platform Chat Service API",
    description="""
    Chat service for the AI Platform that handles AI agent interactions.
    
    ## Features
    - Multiple AI agents with different personas (default, tutor, professional, minimal, translator)
    - Session management with conversation history
    - Shared context across agents
    - User data persistence
    - Knowledge base integration (LightRAG)
    - Tool support (calculator, weather, web search, etc.)
    
    ## API Endpoints
    - `/chat/{agent_key}` - Send messages to AI agents
    - `/agents` - List available AI agents
    - `/session/{session_id}/context` - Get session context
    - `/session/{session_id}/user-data` - Get user data for a session
    - `/fields` - Manage user data fields dynamically
    - `/health` - Service health check
    """,
    version="1.0.0",
    docs_url="/doc",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    logging.info("Starting chat service initialization...")

    # Initialize managers
    db_url = os.getenv("DATABASE_URL")

    # Validate DATABASE_URL
    if not db_url:
        logging.error("DATABASE_URL environment variable is not set!")
        logging.error("Please set DATABASE_URL in Coolify environment variables.")
        logging.error("Format: postgresql+asyncpg://user:pass@host:5432/dbname")
        raise ValueError("DATABASE_URL is required but not set")
    
    # Validate DATABASE_URL format
    if not db_url.startswith(("postgresql+asyncpg://", "postgresql://")):
        logging.warning(f"DATABASE_URL format may be incorrect: {db_url[:50]}...")
        logging.warning("Expected format: postgresql+asyncpg://user:pass@host:5432/dbname")
    
    try:
        engine = create_async_engine(db_url, pool_pre_ping=True)
        session_manager = SessionManager(db_url)
        context_manager = ContextManager(engine)
        
        # Test database connection on startup
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logging.info("Database connection test successful")
        except Exception as conn_error:
            logging.error(f"Database connection test failed: {conn_error}")
            logging.error("Service will start but database operations may fail")
            logging.error("Please verify:")
            logging.error("  1. DATABASE_URL is correct")
            logging.error("  2. Database host is reachable from the container")
            logging.error("  3. Database credentials are correct")
            logging.error("  4. Database exists and is accessible")
            # Don't raise - allow service to start, but log the issue
            # Runtime errors will be handled gracefully in request handlers
        
        logging.info("Database connection initialized (with warnings if connection test failed)")
    except Exception as e:
        logging.error(f"Failed to initialize database connection: {e}")
        logging.error(f"DATABASE_URL: {db_url[:50]}..." if len(db_url) > 50 else f"DATABASE_URL: {db_url}")
        logging.error("Please verify DATABASE_URL is correct and the database is accessible")
        raise
    
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
    ToolRegistry.register_tool(KoneshQueryTool())
    
    logging.info(f"Registered {len(ToolRegistry.list_tools())} tools: {ToolRegistry.list_tools()}")
    
    # Define which tools each persona can use
    persona_tool_assignments = {
        "orchestrator": ["route_to_agent"],  # Orchestrator routing tool
        "guest_faq": ["knowledge_base_query"],  # FAQ agent - minimal tools
        "action_expert": ["query_konesh", "knowledge_base_query"],  # Action expert tools
        "journey_register": ["query_konesh"],  # Journey agent - basic tools for verification
        "rewards_invite": ["knowledge_base_query"],  # Rewards agent - basic tools
    }
    
    # ==========================================================================
    # Load all personality configs and register multiple agents
    # ==========================================================================
    loader = ConfigLoader()
    available_configs = loader.list_available_configs()
    
    # Define persona mappings (key -> config file)
    # سفیران آیه‌ها specialized agents
    persona_configs = {
        "orchestrator": "personalities/orchestrator.yaml",  # Context Router
        "guest_faq": "personalities/guest_faq.yaml",  # Guest/FAQ Agent
        "action_expert": "personalities/action_expert.yaml",  # Action Expert (replaces konesh_expert)
        "journey_register": "personalities/journey_register.yaml",  # Journey & Registration Agent
        "rewards_invite": "personalities/rewards_invite.yaml",  # Rewards & Invitation Agent
    }
    
    # Register each persona as a separate agent with their tools
    # Note: orchestrator will get router_tool added later (it needs AGENTS dict to exist first)
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
            "system_prompt": """You are a professional translator. Translate accurately and naturally. Preserve meaning, tone, and formatting.
Do not add advice, suggestions, or extra content.

هر پیام کاربر ممکن است با <internal_context>...</internal_context> شروع شود؛ از آن استفاده کن ولی هرگز در خروجی تکرار نکن.

اگر مطمئن نیستی یا داده کافی نیست، حدس نزن. بگو «اطلاعات کافی ندارم»."""
        }
    })
    
    # Register AgentRouterTool for orchestrator (must be AFTER all agents are in AGENTS dict, but BEFORE initialization)
    from tools.agent_router import AgentRouterTool
    router_tool = AgentRouterTool(AGENTS, context_manager)
    ToolRegistry.register_tool(router_tool)
    
    # Add router tool to orchestrator's custom tools BEFORE initialization
    if "orchestrator" in AGENTS:
        orchestrator_agent = AGENTS["orchestrator"]
        if not hasattr(orchestrator_agent, 'custom_tools') or orchestrator_agent.custom_tools is None:
            orchestrator_agent.custom_tools = []
        orchestrator_agent.custom_tools.append(router_tool)
        logging.info(f"Added route_to_agent tool to orchestrator before initialization")
    
    # Initialize all agents with shared http_client
    for key, agent in AGENTS.items():
        await agent.initialize(http_client=http_client)
    
        logging.info(f"Initialized {len(AGENTS)} agents: {list(AGENTS.keys())}")

        # Debug log: startup completed and agents registered
        logging.info(f"Chat service startup completed successfully! Loaded {len(AGENTS)} agents: {list(AGENTS.keys())}")

        # Set startup completion flag
        app.state.startup_completed = True

        _agent_debug_log(
            hypothesis_id="H1",
            location="services/chat-service/main.py:startup",
            message="startup completed",
            data={"agents": list(AGENTS.keys())},
        )

    # Set startup completion flag
    app.state.startup_completed = True

@app.get("/health", tags=["Health"])
async def health():
    """
    Chat service health check.

    Returns the health status of the chat service and list of available agents.
    Service is considered healthy if it's running and can accept requests,
    regardless of agent loading status.
    """
    agents_list = list(AGENTS.keys()) if AGENTS else []

    return {
        "status": "healthy",  # Always healthy if service is responding
        "service": "chat",
        "agents": agents_list,
        "agent_count": len(agents_list),
        "message": "Service is running and ready to accept requests"
    }

@app.get("/health/stream", tags=["Health"])
async def health_stream():
    """
    Streaming endpoint health check.
    
    Tests if the streaming infrastructure is working correctly.
    Returns a simple SSE stream to verify connectivity.
    """
    async def test_stream():
        yield f"data: {json.dumps({'status': 'ok', 'message': 'Streaming endpoint is working'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
    
    return StreamingResponse(
        test_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/agents", tags=["Agents"])
async def list_agents():
    """
    List all available AI agents with their details.
    
    Returns information about each agent including name, model, capabilities, and max turns.
    """
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


@app.get("/personas", tags=["Agents"])
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


@app.get("/tools", tags=["Tools"])
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


@app.get("/tools/{tool_name}", tags=["Tools"])
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

def normalize_user_data(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize user_data from app format to context format.
    Maps app field names to normalized context field names.
    """
    if not user_data:
        return {}
    
    # Mapping from app field names to normalized context field names
    field_mapping = {
        # Personal Information (اطلاعات فردی)
        "phone_number": "user_phone",
        "شماره_همراه": "user_phone",
        "full_name": "user_full_name",
        "نام_و_نام_خانوادگی": "user_full_name",
        "gender": "user_gender",
        "جنسیت": "user_gender",
        "birth_month": "user_birth_month",
        "ماه_تولد": "user_birth_month",
        "birth_year": "user_birth_year",
        "سال_تولد": "user_birth_year",
        
        # Residence Information (اطلاعات محل سکونت)
        "province": "user_province",
        "استان": "user_province",
        "city": "user_city",
        "شهر": "user_city",
        
        # Activity Information (اطلاعات Activities)
        "registered_actions": "user_registered_actions",
        "کنش_ثبت_شده": "user_registered_actions",
        "score": "user_score",
        "امتیاز": "user_score",
        "pending_reports": "user_pending_reports",
        "در_انتظار_ثبت_گزارش": "user_pending_reports",
        "level": "user_level",
        "سطح_من": "user_level",
        "my_actions": "user_my_actions",
        "کنش_های_من": "user_my_actions",
        "saved_actions": "user_saved_actions",
        "کنش_های_ذخیره_شده": "user_saved_actions",
        "saved_content": "user_saved_content",
        "محتوای_ذخیره_شده": "user_saved_content",
        "achievements": "user_achievements",
        "دستاوردها": "user_achievements",
    }
    
    normalized = {}
    for key, value in user_data.items():
        # Map to normalized field name
        normalized_key = field_mapping.get(key, key)
        
        # Wrap value in standard format
        if isinstance(value, (list, dict)):
            normalized[normalized_key] = {"value": value}
        else:
            normalized[normalized_key] = {"value": value}
    
    return normalized


@app.post("/chat/{agent_key}", tags=["Chat"])
async def chat(agent_key: str, request: AgentRequest):
    """
    Send a message to an AI agent.
    
    Processes the user's message through the specified AI agent and returns a response.
    Supports session management, user data persistence, and shared context across agents.
    
    - **agent_key**: The identifier of the agent (e.g., 'default', 'tutor', 'professional', 'orchestrator')
    - **request**: Contains message, optional session_id, user_data, and use_shared_context flag
    
    Routing Logic:
    - If agent_key is 'orchestrator', request goes directly to orchestrator
    - If agent_key is any other agent, request first goes to orchestrator for intelligent routing
    - Orchestrator will route to the requested agent or choose a better one based on the message content
    """
    # Check if orchestrator is available
    if "orchestrator" not in AGENTS:
        # Fallback: if orchestrator not available, use direct routing
        if agent_key not in AGENTS:
            raise HTTPException(404, f"Agent '{agent_key}' not found")
        agent = AGENTS[agent_key]
    else:
        # Always route through orchestrator first (unless explicitly requesting orchestrator)
        if agent_key == "orchestrator":
            # Direct access to orchestrator
            agent = AGENTS["orchestrator"]
        else:
            # Route through orchestrator, but pass the requested agent_key as hint
            # The orchestrator will decide whether to use the requested agent or route to a better one
            orchestrator_agent = AGENTS["orchestrator"]
            
            # Enhance message with requested agent hint for orchestrator
            # Format: Add hint at the beginning of message (orchestrator will see this)
            if agent_key in AGENTS:
                # Add hint in a way orchestrator can understand
                # We'll add it to the message as a prefix that orchestrator can parse
                hint_prefix = f"[REQUESTED_AGENT: {agent_key}] "
                enhanced_message = hint_prefix + request.message
                # Create a new request with enhanced message
                from shared.base_agent import AgentRequest
                request = AgentRequest(
                    message=enhanced_message,
                    session_id=request.session_id,
                    user_data=request.user_data,
                    use_shared_context=request.use_shared_context
                )
            
            # Use orchestrator for routing
            agent = orchestrator_agent
    
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
            "has_user_data": bool(request.user_data),
        },
    )

    # ==========================================================================
    # Save user_data immediately if provided
    # ==========================================================================
    if request.user_data:
        normalized_user_data = normalize_user_data(request.user_data)
        if normalized_user_data:
            # Save immediately to context
            try:
                await context_manager.merge_context(
                    sid,
                    normalized_user_data,
                    agent_type=agent_key
                )
                logging.info(f"Saved user_data for session {sid}: {list(normalized_user_data.keys())}")
            except Exception as e:
                logging.error(f"Database connection error when saving user_data for session {sid}: {e}")
                logging.warning("User data not persisted due to database error, but continuing with request")

    # Load session history
    try:
        session = await session_manager.get_session(sid)
        history = session["messages"] if session else []
    except Exception as e:
        logging.error(f"Database connection error when loading session {sid}: {e}")
        # Continue with empty history if database is unavailable
        # This allows the service to work even if database has temporary issues
        history = []
        logging.warning("Continuing with empty history due to database error")

    # Load shared context (includes any user_data just saved)
    shared_context = {}
    if request.use_shared_context:
        try:
            shared_context = await context_manager.get_context(sid) or {}
        except Exception as e:
            logging.error(f"Database connection error when loading context for session {sid}: {e}")
            logging.warning("Continuing with empty context due to database error")
            shared_context = {}
        
        # Also merge any additional user_data that wasn't saved yet
        if request.user_data:
            normalized_user_data = normalize_user_data(request.user_data)
            shared_context.update(normalized_user_data)

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
        try:
            await context_manager.merge_context(
                sid, 
                response.context_updates, 
                agent_type=agent_key
            )
        except Exception as e:
            logging.error(f"Database connection error when saving context for session {sid}: {e}")
            logging.warning("Context not persisted due to database error, but response sent successfully")
    
    # Save session (agent should return updated history in metadata)
    new_history = response.metadata.get("history", history)
    try:
        await session_manager.upsert_session(
            sid, 
            new_history, 
            agent_key,
            metadata={"last_agent": agent_key}
        )
    except Exception as e:
        logging.error(f"Database connection error when saving session {sid}: {e}")
        # Log but don't fail the request - user still gets their response
        logging.warning("Session not persisted due to database error, but response sent successfully")
    
    return response


@app.delete("/session/{session_id}", tags=["Sessions"])
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

@app.get("/session/{session_id}/context", tags=["Sessions"])
async def get_session_context(session_id: str):
    """Get all shared context for session"""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(400, "Invalid session_id")
    
    context = await context_manager.get_context(sid)
    return {"session_id": session_id, "context": context or {}}


@app.get("/session/{session_id}/user-data", tags=["Sessions"])
async def get_session_user_data(session_id: str):
    """
    Get user data for a session in app format.
    Returns user data normalized back to app field names.
    """
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(400, "Invalid session_id")
    
    context = await context_manager.get_context(sid) or {}
    
    # Reverse mapping: normalized -> app field names
    reverse_mapping = {
        "user_phone": "phone_number",
        "user_full_name": "full_name",
        "user_gender": "gender",
        "user_birth_month": "birth_month",
        "user_birth_year": "birth_year",
        "user_province": "province",
        "user_city": "city",
        "user_registered_actions": "registered_actions",
        "user_score": "score",
        "user_pending_reports": "pending_reports",
        "user_level": "level",
        "user_my_actions": "my_actions",
        "user_saved_actions": "saved_actions",
        "user_saved_content": "saved_content",
        "user_achievements": "achievements",
        # Also include standard fields
        "user_name": "name",
        "user_age": "age",
        "user_location": "location",
        "user_occupation": "occupation",
        "user_interests": "interests",
        "preferred_language": "language",
    }
    
    # Convert context back to app format
    user_data = {}
    for normalized_key, value_data in context.items():
        app_key = reverse_mapping.get(normalized_key, normalized_key)
        # Extract value from {"value": ...} format
        if isinstance(value_data, dict) and "value" in value_data:
            user_data[app_key] = value_data["value"]
        else:
            user_data[app_key] = value_data
    
    # Organize by categories
    personal_info = {
        "phone_number": user_data.get("phone_number"),
        "full_name": user_data.get("full_name"),
        "gender": user_data.get("gender"),
        "birth_month": user_data.get("birth_month"),
        "birth_year": user_data.get("birth_year"),
    }
    
    residence_info = {
        "province": user_data.get("province"),
        "city": user_data.get("city"),
    }
    
    activity_info = {
        "registered_actions": user_data.get("registered_actions"),
        "score": user_data.get("score"),
        "pending_reports": user_data.get("pending_reports"),
        "level": user_data.get("level"),
        "my_actions": user_data.get("my_actions"),
        "saved_actions": user_data.get("saved_actions"),
        "saved_content": user_data.get("saved_content"),
        "achievements": user_data.get("achievements"),
    }
    
    return {
        "session_id": session_id,
        "personal_info": {k: v for k, v in personal_info.items() if v is not None},
        "residence_info": {k: v for k, v in residence_info.items() if v is not None},
        "activity_info": {k: v for k, v in activity_info.items() if v is not None},
        "all_data": user_data  # Complete flat structure
    }

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


@app.post("/chat/{agent_key}/stream", tags=["Chat"])
async def chat_stream(agent_key: str, request: AgentRequest):
    """
    Stream a message to an AI agent (Server-Sent Events).
    
    All requests are routed through orchestrator for intelligent routing.
    Returns streaming response as Server-Sent Events (SSE).
    """
    import asyncio
    
    logging.info(f"Streaming request received for agent_key: {agent_key}, session_id: {request.session_id}")
    logging.info(f"Available agents: {list(AGENTS.keys())}")
    
    # Use the same routing logic as regular chat endpoint
    if "orchestrator" not in AGENTS:
        if agent_key not in AGENTS:
            raise HTTPException(404, f"Agent '{agent_key}' not found")
        agent = AGENTS[agent_key]
    else:
        if agent_key == "orchestrator":
            agent = AGENTS["orchestrator"]
        else:
            orchestrator_agent = AGENTS["orchestrator"]
            if agent_key in AGENTS:
                hint_prefix = f"[REQUESTED_AGENT: {agent_key}] "
                enhanced_message = hint_prefix + request.message
                from shared.base_agent import AgentRequest
                request = AgentRequest(
                    message=enhanced_message,
                    session_id=request.session_id,
                    user_data=request.user_data,
                    use_shared_context=request.use_shared_context
                )
            agent = orchestrator_agent
    
    # Handle session
    if request.session_id:
        try:
            sid = uuid.UUID(request.session_id)
        except ValueError:
            raise HTTPException(400, "Invalid session_id format")
    else:
        sid = uuid.uuid4()
    
    # Load session history and context (same as regular endpoint)
    try:
        session = await session_manager.get_session(sid)
        history = session["messages"] if session else []
    except Exception as e:
        logging.error(f"Database connection error when loading session {sid}: {e}")
        history = []
    
    shared_context = {}
    if request.use_shared_context:
        try:
            shared_context = await context_manager.get_context(sid) or {}
        except Exception as e:
            logging.error(f"Database connection error when loading context for session {sid}: {e}")
            shared_context = {}
        
        if request.user_data:
            normalized_user_data = normalize_user_data(request.user_data)
            shared_context.update(normalized_user_data)
    
    request.session_id = str(sid)
    
    async def generate_stream():
        """Generate streaming response chunks"""
        response = None
        try:
            logging.info(f"Starting stream generation for agent: {agent_key}, session: {sid}")
            
            # Send session ID first
            yield f"data: {json.dumps({'session_id': str(sid)})}\n\n"
            
            # Process the request
            logging.info(f"Processing request with agent: {agent_key}")
            response = await agent.process(request, history, shared_context)
            logging.info(f"Agent processing completed, output length: {len(response.output) if response else 0}")
            
            # Post-process the output (same as regular endpoint)
            output = response.output
            
            # Stream the output word by word for better UX
            words = output.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.01)  # Small delay for smooth streaming (10ms per word)
            
            # Send done signal
            yield f"data: {json.dumps({'done': True})}\n\n"
            
            # Save session and context (same as regular endpoint)
            if response:
                try:
                    new_history = response.metadata.get("history", history)
                    await session_manager.upsert_session(
                        sid,
                        new_history,
                        agent_key,
                        metadata={"last_agent": agent_key}
                    )
                    if response.context_updates:
                        await context_manager.merge_context(
                            sid,
                            response.context_updates,
                            agent_type=agent_key
                        )
                except Exception as e:
                    logging.error(f"Error saving session/context: {e}")
                
        except Exception as e:
            logging.error(f"Streaming error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
