# services/chat-service/main.py
import asyncio
import json
import logging
import os
import re
import time
import uuid
import datetime
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from shared.database import SessionManager
from shared.context_manager import ContextManager
from shared.base_agent import AgentRequest
from agents.config_loader import load_agent_config, UserDataField, ConfigLoader
from agents.litellm_compat import create_litellm_compatible_client
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# Import tools
from tools.registry import ToolRegistry
from tools.knowledge_base import KnowledgeBaseTool, GetLearningResourceTool
from tools.calculator import CalculatorTool
from tools.weather import WeatherTool
from tools.web_search import WebSearchTool, GetCompanyInfoTool
from tools.konesh_query import KoneshQueryTool

# Import monitoring
from monitoring import trace_collector

# Import Safiranayeha integration
from integrations.safiranayeha_client import SafiranayehaClient, set_safiranayeha_client
from integrations.path_router import PathRouter, get_path_router, set_path_router
from utils.crypto import decrypt_safiranayeha_param

# Import conversation summarization
from chains.conversation_summarizer_chain import ConversationSummarizerChain
from shared.conversation_context_builder import build_history_context

load_dotenv()

# Initialize logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="AI Platform Chat Service API",
    description="""
    Chat service for the AI Platform that handles AI agent interactions.
    
    ## Features
    - Multiple AI agents with different personas (default, tutor, professional, minimal)
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
# API Request Logging Middleware
# =============================================================================

async def api_request_logging_middleware(request, call_next):
    """Log API requests to service_logs for the log viewer."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    # Skip logging for health/docs/monitoring to avoid blocking when DB is unreachable
    skip_paths = ("/health", "/health/stream", "/monitoring/logs", "/monitoring/logs/stats")
    if request.url.path in skip_paths or request.url.path.startswith("/doc") or request.url.path.startswith("/openapi") or request.url.path.startswith("/redoc"):
        return response
    log_svc = getattr(request.app.state, "log_service", None)
    if log_svc:
        agent_key = None
        m = re.match(r"^/chat/([^/]+)", request.url.path)
        if m:
            agent_key = m.group(1)
        m2 = re.match(r"^/session/([^/]+)/", request.url.path)
        session_id_str = m2.group(1) if m2 else None
        sid = None
        if session_id_str:
            try:
                sid = uuid.UUID(session_id_str)
            except ValueError:
                pass

        async def _log():
            try:
                await log_svc.append_log(
                    log_type="api_request",
                    session_id=sid,
                    agent_key=agent_key,
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=round(duration_ms, 2),
                )
            except Exception:
                pass

        asyncio.create_task(_log())  # Non-blocking; don't await
    return response

@app.middleware("http")
async def add_api_request_logging(request, call_next):
    return await api_request_logging_middleware(request, call_next)


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


# =============================================================================
# Pydantic Models for Safiranayeha Integration
# =============================================================================

class ChatInitRequest(BaseModel):
    """Request model for initializing chat from Safiranayeha website."""
    encrypted_param: str = None  # Optional encrypted parameter from URL
    user_id: Optional[str] = None  # Direct user_id (alternative to encrypted_param)
    path: Optional[str] = None  # Website path (alternative to encrypted_param)


class ChatInitResponse(BaseModel):
    """Response model for chat initialization."""
    session_id: str
    agent_key: str
    user_data: Optional[Dict[str, Any]] = None
    welcome_message: Optional[str] = None


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
AGENT_CONFIGS = {}  # Store configs for each agent (chain-only)
session_manager = None
context_manager = None
http_client: httpx.AsyncClient | None = None
agent_full_config = None  # Default agent config for field management
safiranayeha_client: SafiranayehaClient | None = None  # Safiranayeha API client
path_router: PathRouter | None = None  # Path-to-agent router
chain_executor = None  # LangChain chain-based executor (always used)
conversation_summarizer = None  # For long-session summarization
log_service = None  # For persisting logs to DB

# Static tool mapping for /personas (chain uses tools internally)
PERSONA_TOOL_NAMES = {
    "orchestrator": ["route_to_agent"],
    "guest_faq": ["knowledge_base_query"],
    "action_expert": ["query_konesh", "knowledge_base_query"],
    "journey_register": ["query_konesh", "knowledge_base_query"],
    "rewards_invite": ["knowledge_base_query"],
}


async def _db_connect_test(engine):
    """Run a simple DB check; used with asyncio.wait_for to avoid blocking startup."""
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))

@app.on_event("startup")
async def startup():
    global session_manager, context_manager, http_client, agent_full_config, safiranayeha_client, path_router, chain_executor, conversation_summarizer, log_service

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
        
        # Test database connection on startup (with timeout so startup does not hang)
        _db_test_seconds = 5
        try:
            await asyncio.wait_for(
                _db_connect_test(engine),
                timeout=_db_test_seconds,
            )
            logging.info("Database connection test successful")
        except asyncio.TimeoutError:
            logging.warning(
                f"Database connection test timed out after {_db_test_seconds}s. "
                "Service will start; DB operations may fail until the database is reachable."
            )
            logging.warning("Verify DATABASE_URL and that the DB host is reachable from the container.")
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
    # This shared client ensures all agents use the same client with compatibility hooks
    http_client = create_litellm_compatible_client()
    logging.info("✅ Created shared HTTP client with LiteLLM compatibility hooks")

    # Load default agent configuration from YAML
    config_file = os.getenv("AGENT_CONFIG_FILE", "agent_config.yaml")
    try:
        agent_full_config = load_agent_config(config_file)
        logging.info(f"Loaded default agent: {agent_full_config.agent_name} v{agent_full_config.agent_version}")
    except Exception as e:
        logging.error(f"Failed to load agent config from {config_file}: {e}")
        logging.info("Falling back to default config")
        agent_full_config = load_agent_config("agent_config.yaml")

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
    
    # ==========================================================================
    # Load all personality configs for chain executor
    # ==========================================================================
    loader = ConfigLoader()
    available_configs = loader.list_available_configs()

    persona_configs = {
        "orchestrator": "personalities/orchestrator.yaml",
        "guest_faq": "personalities/guest_faq.yaml",
        "action_expert": "personalities/action_expert.yaml",
        "journey_register": "personalities/journey_register.yaml",
        "rewards_invite": "personalities/rewards_invite.yaml",
    }

    for agent_key, config_path in persona_configs.items():
        try:
            persona_config = load_agent_config(config_path)
            AGENT_CONFIGS[agent_key] = persona_config
            logging.info(f"Loaded config for '{agent_key}': {persona_config.agent_name}")
        except Exception as e:
            logging.warning(f"Failed to load persona '{agent_key}' from {config_path}: {e}")
            import traceback
            traceback.print_exc()

    # ==========================================================================
    # Initialize Safiranayeha Integration
    # ==========================================================================
    logging.info("Initializing Safiranayeha integration...")

    # Initialize Safiranayeha API client (login will happen on-demand when needed)
    safiranayeha_client = SafiranayehaClient(http_client=http_client)
    set_safiranayeha_client(safiranayeha_client)
    logging.info("Safiranayeha API client initialized (authentication will occur on first use)")

    # Initialize path router
    path_router = PathRouter()
    set_path_router(path_router)
    logging.info(f"Path router initialized with {len(path_router.mappings)} mappings")

    # Initialize conversation summarizer for long sessions
    conversation_summarizer = ConversationSummarizerChain()
    logging.info("Conversation summarizer initialized")

    # Initialize log service for log viewer
    from logging_service import LogService
    log_service = LogService(session_manager.engine)
    logging.info("Log service initialized")

    # Initialize chain executor (always chain-only)
    from chains.chain_executor import ChainExecutor
    kb_tool = ToolRegistry.get_tool("knowledge_base_query")
    konesh_tool = ToolRegistry.get_tool("query_konesh")
    if kb_tool and AGENT_CONFIGS:
        chain_executor = ChainExecutor(
            agent_configs=AGENT_CONFIGS,
            kb_tool=kb_tool,
            konesh_tool=konesh_tool,
            log_service=log_service,
        )
        logging.info("✅ Chain executor initialized")
    else:
        logging.warning("Chain executor not initialized: missing kb_tool or AGENT_CONFIGS")

    logging.info(f"Chat service startup completed. Loaded {len(AGENT_CONFIGS)} agent configs: {list(AGENT_CONFIGS.keys())}")

    # Store log service for middleware access
    app.state.log_service = log_service

    # Set startup completion flag
    app.state.startup_completed = True

    _agent_debug_log(
        hypothesis_id="H1",
        location="services/chat-service/main.py:startup",
        message="startup completed",
        data={"agent_configs": list(AGENT_CONFIGS.keys())},
    )

@app.get("/health", tags=["Health"])
async def health():
    """
    Chat service health check.

    Returns the health status of the chat service and list of available agents.
    Service is considered healthy if it's running and can accept requests,
    regardless of agent loading status.
    """
    agents_list = list(AGENT_CONFIGS.keys()) if AGENT_CONFIGS else []

    return {
        "status": "healthy",
        "service": "chat",
        "agents": agents_list,
        "agent_count": len(agents_list),
        "chain_executor_ready": chain_executor is not None,
        "message": "Service is running and ready to accept requests",
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
    for key, config in AGENT_CONFIGS.items():
        model_config = getattr(config, "model_config", {}) or {}
        agent_info = {
            "name": config.agent_name,
            "model": model_config.get("default_model", "chain"),
            "capabilities": ["chat", "conversation", "qa", "user_context_extraction"],
            "max_turns": model_config.get("max_turns", 12),
            "description": config.description,
            "is_persona": True,
        }
        result[key] = agent_info
    return result


@app.get("/personas", tags=["Agents"])
async def list_personas():
    """List all available chat personas."""
    personas = []
    for key, config in AGENT_CONFIGS.items():
        tools = PERSONA_TOOL_NAMES.get(key, [])
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
        "usage": "POST /chat/{persona_key} with your message",
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


# =============================================================================
# Safiranayeha Integration Endpoints
# =============================================================================

@app.post("/chat/init", tags=["Chat", "Safiranayeha"])
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

    **Example:**
    ```
    POST /chat/init
    {
        "encrypted_param": "encrypted_base64_string_from_url"
    }
    ```

    **Response:**
    ```json
    {
        "session_id": "uuid-here",
        "agent_key": "action_expert",
        "user_data": {...},
        "welcome_message": "سلام! چطور می‌تونم کمکت کنم؟"
    }
    ```
    """
    global safiranayeha_client, path_router

    try:
        # Step 1: Extract UserId and Path
        if request.encrypted_param:
            # Decrypt parameter
            logging.info("Decrypting Safiranayeha parameter...")
            try:
                decrypted_data = decrypt_safiranayeha_param(request.encrypted_param)
                user_id = decrypted_data.get('UserId')
                path = decrypted_data.get('Path', '/')
                logging.info(f"Decrypted: UserId={user_id}, Path={path}")
            except Exception as e:
                logging.error(f"Failed to decrypt parameter: {e}")
                raise HTTPException(400, f"Invalid encrypted parameter: {str(e)}")
        else:
            # Use direct parameters
            user_id = request.user_id
            path = request.path or '/'
            if not user_id:
                raise HTTPException(400, "Either encrypted_param or user_id must be provided")

        # Step 2: Fetch user data from Safiranayeha API
        logging.info(f"Fetching user data for user_id={user_id}...")
        try:
            user_data_raw = await safiranayeha_client.get_user_data(user_id)
            logging.info(f"Fetched user data with {len(user_data_raw)} fields")
        except Exception as e:
            logging.error(f"Failed to fetch user data: {e}")
            # Continue with empty user data
            user_data_raw = {}
            logging.warning("Continuing with empty user data")

        # Step 3: Determine agent based on path
        agent_key = path_router.get_agent_for_path(path)
        logging.info(f"Mapped path '{path}' to agent '{agent_key}'")

        # Verify agent exists
        if agent_key not in AGENT_CONFIGS:
            logging.warning(f"Agent '{agent_key}' not found, falling back to guest_faq")
            agent_key = "guest_faq"

        # Step 4: Create new session
        session_id = uuid.uuid4()
        logging.info(f"Created new session: {session_id}")

        # Step 5: Normalize and save user data to context
        if user_data_raw:
            normalized_user_data = safiranayeha_client.normalize_user_data_for_context(user_data_raw)
            logging.info(f"Normalized {len(normalized_user_data)} user data fields")

            # Save to context manager
            try:
                await context_manager.merge_context(
                    session_id,
                    normalized_user_data,
                    agent_type=agent_key
                )
                logging.info(f"Saved user context for session {session_id}")
            except Exception as e:
                logging.error(f"Failed to save user context: {e}")
                # Continue anyway

        # Step 6: Generate welcome message (optional)
        welcome_message = None
        # You can customize this based on agent_key
        if agent_key == "guest_faq":
            welcome_message = "سلام! خوش اومدی به سفیران آیه‌ها 🌟 چطور می‌تونم کمکت کنم؟"
        elif agent_key == "action_expert":
            welcome_message = "سلام! برای تولید محتوای کنش‌ها آماده‌ام. چه کنشی مد نظرته؟"
        elif agent_key == "journey_register":
            welcome_message = "سلام! بیا مسیر سفیران رو با هم طی کنیم. از کجا شروع کنیم؟"
        elif agent_key == "rewards_invite":
            welcome_message = "سلام! برای اطلاعات امتیازات و دعوت‌ها اینجام. چه چیزی می‌خوای بدونی؟"
        else:
            welcome_message = "سلام! چطور می‌تونم کمکت کنم؟"

        # Step 7: Return response
        return ChatInitResponse(
            session_id=str(session_id),
            agent_key=agent_key,
            user_data=user_data_raw if user_data_raw else None,
            welcome_message=welcome_message
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error in chat initialization: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to initialize chat: {str(e)}")


@app.get("/safiranayeha/path-mappings", tags=["Safiranayeha"])
async def get_path_mappings():
    """
    Get all path-to-agent mappings.

    Returns the configuration of which website paths map to which AI agents.
    Useful for debugging and understanding the routing logic.

    **Returns:**
    - default_agent: Default agent when no path matches
    - mappings: List of path patterns and their assigned agents
    """
    global path_router

    return {
        "default_agent": path_router.default_agent,
        "mappings": path_router.get_all_mappings(),
        "total_mappings": len(path_router.mappings)
    }


@app.post("/safiranayeha/test-decrypt", tags=["Safiranayeha"])
async def test_decrypt(encrypted_param: str):
    """
    Test endpoint to decrypt Safiranayeha URL parameter.

    **For testing and debugging only.**

    **Parameters:**
    - encrypted_param: AES encrypted base64 string

    **Returns:**
    - decrypted: Decrypted JSON data
    """
    try:
        decrypted = decrypt_safiranayeha_param(encrypted_param)
        return {"success": True, "decrypted": decrypted}
    except Exception as e:
        raise HTTPException(400, f"Decryption failed: {str(e)}")


@app.post("/chat/{agent_key}", tags=["Chat"])
async def chat(agent_key: str, request: AgentRequest):
    """
    Send a message to an AI agent.
    
    Processes the user's message through the specified AI agent and returns a response.
    Supports session management, user data persistence, and shared context across agents.
    
    - **agent_key**: The identifier of the agent (e.g., 'guest_faq', 'action_expert', 'journey_register')
    - **request**: Contains message, optional session_id, user_data, and use_shared_context flag
    
    Routing Logic:
    - Direct routing to the specified agent
    - No orchestrator involvement (path-based routing handled at initialization)
    """
    # Chain-only executor
    if chain_executor is None or agent_key not in AGENT_CONFIGS:
        raise HTTPException(404, f"Agent '{agent_key}' not found")
    executor = chain_executor
    
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
        messages = session["messages"] if session else []
        session_metadata = session.get("metadata", {}) if session else {}
        logging.info(f"Loaded history for session {sid}: {len(messages)} messages")
    except Exception as e:
        logging.error(f"Database connection error when loading session {sid}: {e}")
        messages = []
        session_metadata = {}
        logging.warning("Continuing with empty history due to database error")

    # Build history context (summarization for long sessions)
    effective_history = messages
    summary_block = ""
    updated_metadata = session_metadata
    if conversation_summarizer:
        try:
            effective_history, summary_block, updated_metadata = await build_history_context(
                messages, session_metadata, conversation_summarizer
            )
        except Exception as e:
            logging.warning(f"Conversation context build failed: {e}")

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

    # Process with executor (history + structured shared context)
    request.session_id = str(sid)
    response = await executor.process(
        request, effective_history, shared_context, agent_key=agent_key, summary_block=summary_block
    )

    # Debug log: after agent processing, before persistence
    _agent_debug_log(
        hypothesis_id="H3",
        location="services/chat-service/main.py:chat:post-process",
        message="chat processed",
        data={
            "agent_key": agent_key,
            "history_len": len(messages),
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
    new_history = response.metadata.get("history", messages)
    save_metadata = {**updated_metadata, "last_agent": agent_key}
    try:
        await session_manager.upsert_session(
            sid,
            new_history,
            agent_key,
            metadata=save_metadata,
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
    global agent_full_config
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
    }


@app.put("/config/fields/{field_name}", tags=["Config"])
async def update_field(field_name: str, request: FieldUpdateRequest):
    """Update an existing user data field."""
    global agent_full_config
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
    global agent_full_config
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

    return {"status": status, "field_name": field_name}


@app.post("/config/fields/{field_name}/enable", tags=["Config"])
async def enable_field(field_name: str):
    """Re-enable a disabled field."""
    global agent_full_config
    if not agent_full_config:
        raise HTTPException(500, "Agent config not loaded")
    
    # Find and enable
    for f in agent_full_config.user_data_fields:
        if f.field_name.lower() == field_name.lower():
            f.enabled = True
            return {"status": "enabled", "field_name": field_name}
    
    raise HTTPException(404, f"Field '{field_name}' not found")


@app.post("/config/reload", tags=["Config"])
async def reload_config():
    """
    Reload configuration from YAML file.
    This will reset all runtime changes and reload from disk.
    """
    global agent_full_config

    config_file = os.getenv("AGENT_CONFIG_FILE", "agent_config.yaml")
    try:
        agent_full_config = load_agent_config(config_file)

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


# =============================================================================
# Monitoring API Endpoints
# =============================================================================

@app.get("/monitoring/traces", tags=["Monitoring"])
async def get_traces(
    session_id: Optional[str] = None,
    agent_key: Optional[str] = None,
    limit: int = 50
):
    """
    Get execution traces for monitoring and debugging.

    Returns a list of execution traces with optional filtering by session or agent.
    Each trace contains complete information about the agent execution including
    system prompt, user message, KB queries, tool calls, LLM input/output, and performance metrics.

    - **session_id**: Optional filter by session ID
    - **agent_key**: Optional filter by agent key
    - **limit**: Maximum number of traces to return (default: 50, max: 100)
    """
    # Limit max to 100 for performance
    limit = min(limit, 100)

    traces = trace_collector.get_traces(
        session_id=session_id,
        agent_key=agent_key,
        limit=limit
    )

    return {
        "count": len(traces),
        "traces": traces,
        "filters": {
            "session_id": session_id,
            "agent_key": agent_key,
            "limit": limit
        }
    }


@app.get("/monitoring/traces/recent", tags=["Monitoring"])
async def get_recent_traces(count: int = 20):
    """
    Get the most recent execution traces.

    Returns the N most recent traces for live monitoring dashboards.

    - **count**: Number of recent traces to return (default: 20, max: 50)
    """
    count = min(count, 50)
    traces = trace_collector.get_recent_traces(count=count)

    return {
        "count": len(traces),
        "traces": traces,
        "timestamp": datetime.datetime.now().isoformat()
    }


@app.get("/monitoring/trace/{trace_id}", tags=["Monitoring"])
async def get_trace_by_id(trace_id: str):
    """
    Get a specific trace by its ID.

    Returns complete details of a single execution trace.

    - **trace_id**: The unique identifier of the trace
    """
    trace = trace_collector.get_trace_by_id(trace_id)
    if not trace:
        raise HTTPException(404, f"Trace '{trace_id}' not found")

    return trace


@app.get("/monitoring/stats", tags=["Monitoring"])
async def get_monitoring_stats():
    """
    Get monitoring statistics.

    Returns aggregate statistics about collected traces including
    total count, agent distribution, and average execution time.
    """
    stats = trace_collector.get_stats()
    return stats


@app.delete("/monitoring/traces", tags=["Monitoring"])
async def clear_traces():
    """
    Clear all collected traces.

    Removes all traces from memory. Use with caution.
    """
    trace_collector.clear_traces()
    return {
        "status": "cleared",
        "message": "All traces have been cleared"
    }


# =============================================================================
# Service Logs API (for Log Viewer)
# =============================================================================

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
    """
    Query persisted service logs with filters and pagination.

    Supports filtering by session_id, agent_key, log_type, date range, and text search.
    """
    log_svc = getattr(app.state, "log_service", None)
    if not log_svc:
        return {"items": [], "total": 0, "page": page, "limit": limit}
    try:
        return await log_svc.get_logs(
            page=page,
            limit=limit,
            session_id=session_id,
            agent_key=agent_key,
            log_type=log_type,
            from_date=from_date,
            to_date=to_date,
            sort=sort,
            search=search,
        )
    except ProgrammingError:
        return {"items": [], "total": 0, "page": page, "limit": limit}


@app.get("/monitoring/logs/stats", tags=["Monitoring"])
async def get_service_logs_stats(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
):
    """Get aggregate stats for service logs: count by type, by agent."""
    log_svc = getattr(app.state, "log_service", None)
    if not log_svc:
        return {"total": 0, "by_type": {}, "by_agent": {}}
    try:
        return await log_svc.get_stats(from_date=from_date, to_date=to_date)
    except ProgrammingError:
        return {"total": 0, "by_type": {}, "by_agent": {}}


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
    
    Direct routing to the specified agent.
    Returns streaming response as Server-Sent Events (SSE).
    """
    import asyncio
    
    logging.info(f"Streaming request received for agent_key: {agent_key}, session_id: {request.session_id}")
    logging.info(f"Available agents: {list(AGENT_CONFIGS.keys())}")

    if agent_key not in AGENT_CONFIGS:
        raise HTTPException(404, f"Agent '{agent_key}' not found")
    if chain_executor is None:
        raise HTTPException(503, "Chain executor not initialized")
    executor = chain_executor
    
    # Handle session
    if request.session_id:
        try:
            sid = uuid.UUID(request.session_id)
        except ValueError:
            raise HTTPException(400, "Invalid session_id format")
    else:
        sid = uuid.uuid4()
    
    # Load session history and context
    try:
        session = await session_manager.get_session(sid)
        messages = session["messages"] if session else []
        session_metadata = session.get("metadata", {}) if session else {}
    except Exception as e:
        logging.error(f"Database connection error when loading session {sid}: {e}")
        messages = []
        session_metadata = {}
        logging.warning("Continuing with empty history due to database error")

    # Build history context (summarization for long sessions)
    effective_history = messages
    summary_block = ""
    updated_metadata = session_metadata
    if conversation_summarizer:
        try:
            effective_history, summary_block, updated_metadata = await build_history_context(
                messages, session_metadata, conversation_summarizer
            )
        except Exception as e:
            logging.warning(f"Conversation context build failed: {e}")

    shared_context = {}
    if request.use_shared_context:
        try:
            shared_context = await context_manager.get_context(sid) or {}
        except Exception as e:
            logging.error(f"Database connection error when loading context for session {sid}: {e}")
            logging.warning("Continuing with empty context due to database error")
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
            try:
                response = await executor.process(
                    request, effective_history, shared_context, agent_key=agent_key, summary_block=summary_block
                )
                logging.info(f"Agent processing completed, output length: {len(response.output) if response else 0}")
                
                if not response:
                    logging.error("❌ Agent.process() returned None!")
                    yield f"data: {json.dumps({'error': 'Agent returned no response'})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    return
                
                if not response.output or len(response.output.strip()) == 0:
                    logging.warning("⚠️ Agent returned empty output!")
                    yield f"data: {json.dumps({'error': 'Agent returned empty response'})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    return
                
                # Post-process the output (same as regular endpoint)
                output = response.output
                logging.info(f"✅ Response received, starting to stream output (length: {len(output)})")
            except Exception as process_error:
                logging.error(f"❌ Error in executor.process(): {process_error}", exc_info=True)
                yield f"data: {json.dumps({'error': f'Processing error: {str(process_error)}'})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
                return
            
            # Stream the output word by word for better UX
            logging.info(f"Starting to stream {len(output.split(' '))} words")
            words = output.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.01)  # Small delay for smooth streaming (10ms per word)
            
            logging.info("✅ Finished streaming all chunks, sending done signal")
            # Send done signal
            yield f"data: {json.dumps({'done': True})}\n\n"
            
            # Save session and context (same as regular endpoint)
            if response:
                try:
                    new_history = response.metadata.get("history", messages)
                    save_metadata = {**updated_metadata, "last_agent": agent_key}
                    await session_manager.upsert_session(
                        sid,
                        new_history,
                        agent_key,
                        metadata=save_metadata,
                    )
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
                except Exception as e:
                    logging.error(f"Database connection error when saving session {sid}: {e}")
                    logging.warning("Session not persisted due to database error, but response sent successfully")
                
        except Exception as e:
            logging.error(f"Streaming error: {e}", exc_info=True)
            error_message = str(e)
            # Extract more details from ModelHTTPError
            if hasattr(e, 'status_code') and hasattr(e, 'body'):
                error_message = f"API Error {e.status_code}: {e.body.get('message', str(e)) if isinstance(e.body, dict) else str(e)}"
            yield f"data: {json.dumps({'error': error_message})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
