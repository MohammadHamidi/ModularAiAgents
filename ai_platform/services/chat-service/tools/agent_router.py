"""
Agent Router Tool
Allows the orchestrator agent to route requests to specialist agents
"""
from typing import Any, Dict, Optional
import logging
from tools.registry import Tool

logger = logging.getLogger(__name__)


class AgentRouterTool(Tool):
    """Tool for routing user requests to specialist agents"""

    def __init__(self, agents_registry: Dict[str, Any], context_manager: Any):
        """
        Initialize the router tool

        Args:
            agents_registry: Dictionary of available agents {agent_key: agent_instance}
            context_manager: Context manager for session handling
        """
        self.agents_registry = agents_registry
        self.context_manager = context_manager
        self.last_response = None  # Store the last specialist agent response for history access

        # Initialize Tool base class with enabled=True explicitly
        super().__init__(
            name="route_to_agent",
            enabled=True,  # Explicitly set to ensure it's enabled
            description="""
        Route a user request to a specialist agent and get their response.

        Use this tool to forward the user's message to the appropriate specialist agent.

        Parameters:
        - agent_key (str, required): The key of the specialist agent to route to.
          Available agents: 'guest_faq', 'action_expert', 'journey_register', 'rewards_invite'
        - user_message (str, required): The user's original message to forward
        - session_id (str, optional): Session ID for maintaining context

        Examples:
        - route_to_agent(agent_key="guest_faq", user_message="سفیر چیه؟")
        - route_to_agent(agent_key="action_expert", user_message="برای دختران روستایی چی بگم؟")
        - route_to_agent(agent_key="journey_register", user_message="می‌خوام ثبتش کنم")
        - route_to_agent(agent_key="rewards_invite", user_message="جوایز چیه؟")

        Returns: The specialist agent's response as a string
        """,
            parameters={
                "type": "object",
                "properties": {
                    "agent_key": {
                        "type": "string",
                        "description": "The key of the specialist agent to route to"
                    },
                    "user_message": {
                        "type": "string",
                        "description": "The user's original message to forward"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Optional session ID for maintaining context"
                    }
                },
                "required": ["agent_key", "user_message"]
            }
        )
        logger.info(f"AgentRouterTool initialized with {len(agents_registry)} agents")

    async def execute(
        self,
        agent_key: str,
        user_message: str,
        session_id: Optional[str] = None,
        history: Optional[list] = None,
        shared_context: Optional[dict] = None
    ) -> str:
        """Execute method for Tool interface - delegates to run()."""
        return await self.run(agent_key, user_message, session_id, history, shared_context)

    async def run(
        self,
        agent_key: str,
        user_message: str,
        session_id: Optional[str] = None,
        history: Optional[list] = None,
        shared_context: Optional[dict] = None
    ) -> str:
        """
        Route the request to a specialist agent

        Args:
            agent_key: Key of the target agent
            user_message: User's message to forward
            session_id: Optional session ID
            history: Conversation history to pass to specialist agent
            shared_context: Shared context to pass to specialist agent

        Returns:
            Specialist agent's response (text output)
            
        Note: The full AgentResponse with updated history is stored in 
        self.last_response for access by the caller.
        """
        try:
            # Remove [REQUESTED_AGENT: ...] prefix if present (orchestrator adds this)
            import re
            cleaned_message = re.sub(r'^\[REQUESTED_AGENT:\s*\w+\]\s*', '', user_message).strip()
            
            # Validate agent exists
            if agent_key not in self.agents_registry:
                available = ", ".join(self.agents_registry.keys())
                return f"❌ Error: Agent '{agent_key}' not found. Available agents: {available}"

            # Get the specialist agent
            specialist_agent = self.agents_registry[agent_key]

            logger.info(f"Routing request to agent '{agent_key}': {cleaned_message[:50]}...")

            # Call the specialist agent using the process() method (ChatAgent interface)
            from shared.base_agent import AgentRequest

            request = AgentRequest(
                message=cleaned_message,  # Use cleaned message without prefix
                session_id=session_id,
                use_shared_context=True
            )

            # Use process() method for ChatAgent (pass history and context to maintain session memory)
            history_to_pass = history or []
            logger.info(f"agent_router.run: Passing {len(history_to_pass)} history messages to specialist agent '{agent_key}'")
            response = await specialist_agent.process(
                request,
                history=history_to_pass,
                shared_context=shared_context or {}
            )

            logger.info(f"Received response from agent '{agent_key}': {len(response.output)} chars")

            # Store the full response for access to updated history
            self.last_response = response

            # Return the specialist's response (text output)
            return response.output

        except Exception as e:
            logger.error(f"Error routing to agent '{agent_key}': {e}", exc_info=True)
            return f"❌ خطا در ارجاع به متخصص: {str(e)}\n\nلطفاً دوباره تلاش کنید."

    def run_sync(
        self,
        agent_key: str,
        user_message: str,
        session_id: Optional[str] = None,
        history: Optional[list] = None,
        shared_context: Optional[dict] = None
    ) -> str:
        """
        Synchronous version of run (for compatibility)

        Note: This will need to be called in an async context
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.run(agent_key, user_message, session_id, history, shared_context))


class AgentRouterToolSync:
    """Synchronous wrapper for the Agent Router Tool (for pydantic-ai compatibility)"""

    def __init__(self, agents_registry: Dict[str, Any], context_manager: Any):
        self.router = AgentRouterTool(agents_registry, context_manager)

    @property
    def name(self) -> str:
        return self.router.name

    @property
    def description(self) -> str:
        return self.router.description

    def run(
        self,
        agent_key: str,
        user_message: str,
        session_id: Optional[str] = None,
        history: Optional[list] = None,
        shared_context: Optional[dict] = None
    ) -> str:
        """
        Route the request to a specialist agent (synchronous)

        This is a wrapper that handles the async call for pydantic-ai tools
        """
        import asyncio

        # Check if we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
            # If we're in a loop, we need to use a different approach
            # Create a new thread to run the async code
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.router.run(agent_key, user_message, session_id, history, shared_context)
                )
                return future.result()
        except RuntimeError:
            # No event loop running, we can use asyncio.run directly
            return asyncio.run(self.router.run(agent_key, user_message, session_id, history, shared_context))
