"""
Complete example of integrating the Orchestrator Agent
This file shows the exact code modifications needed in main.py
"""

# ============================================================================
# STEP 1: Add this import near the top (after other tool imports)
# ============================================================================

from tools.agent_router import AgentRouterToolSync


# ============================================================================
# STEP 2: Create a wrapper class for the routing tool
# Add this BEFORE the @app.on_event("startup") function
# ============================================================================

class RouterToolWrapper:
    """Wrapper to make AgentRouterToolSync compatible with Tool interface"""

    def __init__(self, router):
        self.router = router
        self._enabled = True

    @property
    def name(self) -> str:
        return "route_to_agent"

    @property
    def description(self) -> str:
        return self.router.description

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "agent_key": {
                    "type": "string",
                    "description": "The specialist agent key: doctor, tutor, professional, default, minimal",
                    "enum": ["doctor", "tutor", "professional", "default", "minimal"]
                },
                "user_message": {
                    "type": "string",
                    "description": "The user's original message to forward"
                }
            },
            "required": ["agent_key", "user_message"]
        }

    async def execute(self, agent_key: str, user_message: str, session_id: str = None) -> str:
        """Execute the routing"""
        return self.router.run(agent_key, user_message, session_id)


# ============================================================================
# STEP 3: Modify the startup function
# Replace the existing agent registration code with this two-pass approach
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database, tools, and agents"""

    # ... existing database setup code ...
    # ... existing tool registry code ...
    # ... existing persona_configs definition ...

    # ========================================================================
    # MODIFIED AGENT REGISTRATION - TWO PASS APPROACH
    # ========================================================================

    # Define persona configs (including orchestrator)
    persona_configs = {
        "default": "agent_config.yaml",
        "tutor": "personalities/friendly_tutor.yaml",
        "professional": "personalities/professional_assistant.yaml",
        "minimal": "personalities/minimal_assistant.yaml",
        "orchestrator": "personalities/orchestrator.yaml",  # ✅ NEW
    }

    # Tool assignments (orchestrator gets routing tool separately)
    persona_tool_assignments = {
        "default": ["knowledge_base_query", "calculator", "get_weather"],
        "tutor": ["knowledge_base_query", "calculator", "get_learning_resource"],
        "professional": ["knowledge_base_query", "web_search", "get_company_info", "calculator"],
        "minimal": [],
        "orchestrator": [],  # ✅ Will get routing tool separately
    }

    # ========================================================================
    # PASS 1: Register all specialist agents (NOT orchestrator)
    # ========================================================================
    logging.info("=" * 60)
    logging.info("PASS 1: Registering specialist agents...")
    logging.info("=" * 60)

    for agent_key, config_path in persona_configs.items():
        # Skip orchestrator in first pass
        if agent_key == "orchestrator":
            continue

        try:
            persona_config = load_agent_config(config_path)
            persona_model_config = persona_config.model_config

            # Get tools for this persona
            tool_names = persona_tool_assignments.get(agent_key, [])
            persona_tools = [
                ToolRegistry.get_tool(name)
                for name in tool_names
                if ToolRegistry.get_tool(name)
            ]

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

            # Create and initialize agent
            agent = ChatAgent(
                agent_config,
                context_manager,
                persona_config,
                custom_tools=persona_tools
            )

            # Initialize with shared http client
            await agent.initialize(http_client)

            # Register in global registry
            AGENTS[agent_key] = agent
            AGENT_CONFIGS[agent_key] = persona_config

            logging.info(
                f"✅ Registered '{agent_key}': {persona_config.agent_name} "
                f"with {len(persona_tools)} tools"
            )

        except Exception as e:
            logging.error(f"❌ Failed to load '{agent_key}' from {config_path}: {e}")
            import traceback
            traceback.print_exc()

    # ========================================================================
    # PASS 2: Register orchestrator with routing tool
    # ========================================================================
    logging.info("=" * 60)
    logging.info("PASS 2: Registering orchestrator agent...")
    logging.info("=" * 60)

    if "orchestrator" in persona_configs:
        try:
            orchestrator_config_path = persona_configs["orchestrator"]
            orchestrator_persona_config = load_agent_config(orchestrator_config_path)
            orchestrator_model_config = orchestrator_persona_config.model_config

            # Create routing tool with access to all specialist agents
            routing_tool_core = AgentRouterToolSync(AGENTS, context_manager)
            routing_tool = RouterToolWrapper(routing_tool_core)

            logging.info(f"Created routing tool with access to {len(AGENTS)} specialist agents")

            # Create orchestrator agent config
            orchestrator_agent_config = AgentConfig(
                name=orchestrator_persona_config.agent_name,
                model=default_model,
                max_turns=orchestrator_model_config.get("max_turns", 3),
                temperature=orchestrator_model_config.get("temperature", 0.3),
                extra={
                    **base_config,
                    "system_prompt": orchestrator_persona_config.get_complete_system_prompt()
                }
            )

            # Create orchestrator agent with routing tool
            orchestrator_agent = ChatAgent(
                orchestrator_agent_config,
                context_manager,
                orchestrator_persona_config,
                custom_tools=[routing_tool]
            )

            # Initialize orchestrator
            await orchestrator_agent.initialize(http_client)

            # Register orchestrator
            AGENTS["orchestrator"] = orchestrator_agent
            AGENT_CONFIGS["orchestrator"] = orchestrator_persona_config

            logging.info(
                f"✅ Registered orchestrator with routing to "
                f"{len(AGENTS)-1} specialists: {list(AGENTS.keys())}"
            )

        except Exception as e:
            logging.error(f"❌ Failed to load orchestrator: {e}")
            import traceback
            traceback.print_exc()

    # ========================================================================
    # Summary
    # ========================================================================
    logging.info("=" * 60)
    logging.info(f"✅ Startup complete! Registered {len(AGENTS)} agents:")
    for key in AGENTS.keys():
        logging.info(f"   - {key}")
    logging.info("=" * 60)


# ============================================================================
# TESTING EXAMPLES
# ============================================================================

"""
Test the orchestrator:

1. Medical query (should route to doctor):
   curl -X POST http://localhost:8000/chat/orchestrator \
     -H "Content-Type: application/json" \
     -d '{"message": "سلام، سردرد دارم", "session_id": null}'

2. Educational query (should route to tutor):
   curl -X POST http://localhost:8000/chat/orchestrator \
     -H "Content-Type: application/json" \
     -d '{"message": "Help me learn math", "session_id": null}'

3. Religious query (should route to default):
   curl -X POST http://localhost:8000/chat/orchestrator \
     -H "Content-Type: application/json" \
     -d '{"message": "درباره آیه 12 بگو", "session_id": null}'

4. Business query (should route to professional):
   curl -X POST http://localhost:8000/chat/orchestrator \
     -H "Content-Type: application/json" \
     -d '{"message": "I need a business plan", "session_id": null}'
"""


# ============================================================================
# WHAT HAPPENS BEHIND THE SCENES
# ============================================================================

"""
User sends: "سلام، سردرد دارم"
↓
Gateway forwards to: /chat/orchestrator
↓
Orchestrator Agent receives message
↓
Orchestrator analyzes: Contains "سردرد" (headache) → medical topic
↓
Orchestrator calls: route_to_agent(agent_key="doctor", user_message="سلام، سردرد دارم")
↓
Routing tool forwards to Doctor Agent
↓
Doctor Agent processes: "سلام، سردرد دارم"
↓
Doctor Agent returns medical response
↓
Routing tool returns response to Orchestrator
↓
Orchestrator returns response to user
↓
User receives: Medical advice from Doctor Agent (seamlessly!)
"""
