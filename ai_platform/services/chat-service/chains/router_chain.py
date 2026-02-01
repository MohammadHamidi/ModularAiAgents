"""
Router Chain - Classifies user intent and returns target agent_key.
Replaces orchestrator's route_to_agent tool in chain-based mode.
"""
import os
import logging
from typing import Literal

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

AgentKey = Literal["guest_faq", "action_expert", "journey_register", "rewards_invite"]


class RouterResult(BaseModel):
    """Structured output from router chain."""
    agent_key: str = Field(
        description="One of: guest_faq, action_expert, journey_register, rewards_invite"
    )
    reason: str = Field(description="Brief reason for routing decision")


ROUTER_SYSTEM_PROMPT = """You are a router. Analyze the user message and context, then return the single best agent_key.

Available agents:
- guest_faq: معرفی نهضت، سفیر چیه، شروع مسیر، سوالات کلی
- action_expert: تولید متن/اسکریپت/محتوا برای کنش، چی بگم، محفل، فضاسازی
- journey_register: ثبت کنش، گزارش، تکمیل پروفایل
- rewards_invite: جایزه، امتیاز، سکه، کد معرف

Rules:
- "ثبت / گزارش کنش" → journey_register
- "چی بگم / متن بده / اسکریپت" → action_expert
- سوال جوایز/دعوت → rewards_invite
- معرفی، سفیر چیه، شروع → guest_faq
- If unclear, default to guest_faq
"""

ROUTER_USER_TEMPLATE = """User message: {user_message}

History summary (last 2 messages): {history_summary}

Return agent_key and reason."""


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


class RouterChain:
    """Classifies user message and returns target agent_key."""

    def __init__(self):
        self.llm = _create_llm()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", ROUTER_SYSTEM_PROMPT),
            ("user", ROUTER_USER_TEMPLATE),
        ])
        self.chain = self.prompt | self.llm.with_structured_output(RouterResult)

    def invoke(
        self,
        user_message: str,
        history_summary: str = ""
    ) -> str:
        """
        Route user message to agent_key.

        Returns:
            agent_key: guest_faq | action_expert | journey_register | rewards_invite
        """
        result = self.chain.invoke({
            "user_message": user_message,
            "history_summary": history_summary or "(no history)",
        })
        agent_key = result.agent_key
        if agent_key not in ("guest_faq", "action_expert", "journey_register", "rewards_invite"):
            logger.warning(f"Router returned invalid agent_key '{agent_key}', defaulting to guest_faq")
            agent_key = "guest_faq"
        return agent_key
