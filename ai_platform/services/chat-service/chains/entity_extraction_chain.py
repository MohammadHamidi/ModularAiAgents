"""
Entity Extraction Chain - Extracts user data fields from user message.
Replaces save_user_info tool in chain-based mode.
"""
import os
import logging
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExtractedField(BaseModel):
    """Single extracted field."""
    field_name: str = Field(description="Normalized field name from the list")
    field_value: str = Field(description="Extracted value")


class ExtractedEntities(BaseModel):
    """Structured output from entity extraction."""
    fields: List[ExtractedField] = Field(
        default_factory=list,
        description="List of extracted field_name, field_value pairs. Empty if nothing to extract."
    )


EXTRACTION_SYSTEM = """You extract user information from messages. Return only fields the user explicitly mentioned.
Field names must be exactly from the allowed list. Return empty list if nothing to extract.
Never invent or assume values."""

EXTRACTION_USER = """Allowed fields: {field_names}

User message: {user_message}

Extract any mentioned user information. Return as list of field_name, field_value."""


def _create_llm() -> ChatOpenAI:
    """Create LangChain LLM with LiteLLM config."""
    model = os.getenv("LITELLM_MODEL", "gemini-2.5-flash-lite-preview-09-2025")
    api_key = os.getenv("LITELLM_API_KEY", "")
    base_url = os.getenv("LITELLM_BASE_URL", "https://api.avalai.ir/v1")
    return ChatOpenAI(
        model=model,
        temperature=0.0,
        openai_api_key=api_key,
        openai_api_base=base_url,
    )


class EntityExtractionChain:
    """Extracts user data from message for context merge."""

    def __init__(self, agent_config: Any):
        """
        Args:
            agent_config: Agent config with get_enabled_fields(), build_field_map()
        """
        self.agent_config = agent_config
        self.llm = _create_llm()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", EXTRACTION_SYSTEM),
            ("user", EXTRACTION_USER),
        ])
        self.chain = self.prompt | self.llm.with_structured_output(ExtractedEntities)

    async def invoke(self, user_message: str) -> Dict[str, Any]:
        """
        Extract user data from message.

        Returns:
            Dict for context merge: {normalized_name: {"value": ...}}
        """
        enabled = self.agent_config.get_enabled_fields()
        if not enabled:
            return {}

        field_names = [f.field_name for f in enabled]
        try:
            result = await self.chain.ainvoke({
                "field_names": ", ".join(field_names),
                "user_message": user_message,
            })
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return {}

        if not result or not result.fields:
            return {}

        field_map = self.agent_config.build_field_map()
        updates = {}
        for item in result.fields:
            norm = field_map.get(item.field_name.lower())
            if norm and item.field_value:
                updates[norm] = {"value": item.field_value}
        return updates
