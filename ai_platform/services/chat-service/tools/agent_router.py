"""
Agent Router Tool
Allows the orchestrator agent to route requests to specialist agents
"""
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class AgentRouterTool:
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
        logger.info(f"AgentRouterTool initialized with {len(agents_registry)} agents")

    @property
    def name(self) -> str:
        return "route_to_agent"

    @property
    def description(self) -> str:
        return """
        Route a user request to a specialist agent and get their response.

        Use this tool to forward the user's message to the appropriate specialist agent.

        Parameters:
        - agent_key (str, required): The key of the specialist agent to route to.
          Available agents: 'doctor', 'tutor', 'professional', 'default', 'minimal'
        - user_message (str, required): The user's original message to forward
        - session_id (str, optional): Session ID for maintaining context

        Examples:
        - route_to_agent(agent_key="doctor", user_message="سلام، سردرد دارم")
        - route_to_agent(agent_key="tutor", user_message="Help me with math homework")
        - route_to_agent(agent_key="default", user_message="درباره آیه 12 بگو")

        Returns: The specialist agent's response as a string
        """

    async def run(
        self,
        agent_key: str,
        user_message: str,
        session_id: Optional[str] = None
    ) -> str:
        """
        Route the request to a specialist agent

        Args:
            agent_key: Key of the target agent
            user_message: User's message to forward
            session_id: Optional session ID

        Returns:
            Specialist agent's response
        """
        try:
            # Validate agent exists
            if agent_key not in self.agents_registry:
                available = ", ".join(self.agents_registry.keys())
                return f"❌ Error: Agent '{agent_key}' not found. Available agents: {available}"

            # Get the specialist agent
            specialist_agent = self.agents_registry[agent_key]

            logger.info(f"Routing request to agent '{agent_key}': {user_message[:50]}...")

            # Call the specialist agent
            # Note: This assumes agents have a 'run' or 'chat' method
            # You may need to adjust based on your actual agent interface

            from shared.base_agent import AgentRequest

            request = AgentRequest(
                message=user_message,
                session_id=session_id,
                use_shared_context=True
            )

            # Run the specialist agent
            response = await specialist_agent.chat(request)

            logger.info(f"Received response from agent '{agent_key}': {len(response.output)} chars")

            # Return the specialist's response
            return response.output

        except Exception as e:
            logger.error(f"Error routing to agent '{agent_key}': {e}", exc_info=True)
            return f"❌ خطا در ارجاع به متخصص: {str(e)}\n\nلطفاً دوباره تلاش کنید."

    def run_sync(self, agent_key: str, user_message: str, session_id: Optional[str] = None) -> str:
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

        return loop.run_until_complete(self.run(agent_key, user_message, session_id))


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

    def run(self, agent_key: str, user_message: str, session_id: Optional[str] = None) -> str:
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
                    self.router.run(agent_key, user_message, session_id)
                )
                return future.result()
        except RuntimeError:
            # No event loop running, we can use asyncio.run directly
            return asyncio.run(self.router.run(agent_key, user_message, session_id))
