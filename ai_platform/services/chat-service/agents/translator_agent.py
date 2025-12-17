import httpx
from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from shared.base_agent import BaseAgent, AgentConfig, AgentRequest, AgentResponse
from agents.litellm_compat import create_litellm_compatible_client

class TranslatorAgent(BaseAgent):
    """Translator agent implementation"""
    
    async def initialize(self, http_client: httpx.AsyncClient | None = None):
        # Use provided http_client or create a new one
        client = http_client or create_litellm_compatible_client()
        
        openai_client = AsyncOpenAI(
            api_key=self.config.extra.get("api_key"),
            base_url=self.config.extra.get("base_url"),
            http_client=client
        )
        provider = OpenAIProvider(openai_client=openai_client)
        model = OpenAIChatModel(self.config.model, provider=provider)
        
        self.agent = Agent(
            model,
            system_prompt=self.config.extra.get("system_prompt", "")
        )
        # Only store http_client if we created it ourselves
        if http_client is None:
            self.http_client = client
        else:
            self.http_client = None
    
    async def process(self, request: AgentRequest, history=None, shared_context=None) -> AgentResponse:
        result = await self.agent.run(
            request.message,
            message_history=history or []
        )
        
        return AgentResponse(
            session_id=request.session_id,
            output=result.output,
            metadata={"model": self.config.model}
        )
    
    def get_capabilities(self) -> list[str]:
        return ["translation", "language", "translation_service"]
