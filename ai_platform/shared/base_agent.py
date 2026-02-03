from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class AgentConfig(BaseModel):
    """Base configuration for all agents"""
    name: str
    model: str
    max_turns: int = 12
    temperature: float | None = None
    extra: Dict[str, Any] = {}
class AgentRequest(BaseModel):
    message: str
    session_id: str | None = None
    context: Dict[str, Any] = {}  # Request-level context
    use_shared_context: bool = True  # Whether to load shared context
    user_data: Dict[str, Any] = {}  # User data from app (saved immediately)
    from_suggestion: bool = False  # True when user sent message by clicking a suggestion

class AgentResponse(BaseModel):
    session_id: str
    output: str
    metadata: Dict[str, Any] = {}
    context_updates: Dict[str, Any] = {}  # Context to save

class BaseAgent(ABC):
    def __init__(self, config: AgentConfig, context_manager=None):
        self.config = config
        self.context_manager = context_manager
    
    async def load_context(self, session_id: str) -> dict:
        """Load shared context for session"""
        if not self.context_manager:
            return {}
        return await self.context_manager.get_context(session_id) or {}
    
    async def save_context(self, session_id: str, context: dict):
        """Save shared context"""
        if self.context_manager and context:
            await self.context_manager.merge_context(
                session_id, 
                context, 
                agent_type=self.__class__.__name__
            )
    
    @abstractmethod
    async def process(
        self, 
        request: AgentRequest, 
        history: List[Dict] | None = None,
        shared_context: Dict[str, Any] | None = None
    ) -> AgentResponse:
        pass