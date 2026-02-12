"""
Router Chain - Classifies user intent and returns target agent_key.
Replaces orchestrator's route_to_agent tool in chain-based mode.
"""
import os
import logging
from typing import Literal

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
from typing import List, Dict, Any

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
- action_expert: تولید متن/اسکریپت/محتوا برای کنش، چی بگم، محفل، فضاسازی، لیست کنش‌ها
- journey_register: ثبت کنش، گزارش، تکمیل پروفایل
- rewards_invite: جایزه، امتیاز، سکه، کد معرف

Rules:
- "ثبت / گزارش کنش" → journey_register
- "چی بگم / متن بده / اسکریپت / محتوا تولید کن" → action_expert
- "لیست کنش‌ها / کنش‌ها رو ببینم / چه کنشی انجام بدم" → action_expert
- سوال جوایز/دعوت → rewards_invite
- معرفی، سفیر چیه، شروع → guest_faq
- ⚠️ مهم: اگر کاربر از صفحه /home آمده و سوال خاصی پرسیده، بر اساس سوال route کن نه path
- If unclear, default to guest_faq
"""

ROUTER_USER_TEMPLATE = """User message: {user_message}

{history_context}

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
        self.chain = self.llm.with_structured_output(RouterResult)

    def invoke(
        self,
        user_message: str,
        history: List[Dict[str, Any]] = None,
        history_summary: str = ""
    ) -> str:
        """
        Route user message to agent_key.

        Args:
            user_message: Current user message
            history: Full conversation history (preferred)
            history_summary: Fallback summary if history not available

        Returns:
            agent_key: guest_faq | action_expert | journey_register | rewards_invite
        """
        # Build messages with conversation history
        messages = [SystemMessage(content=ROUTER_SYSTEM_PROMPT)]
        
        # Add conversation history if available
        if history:
            # Get last 4-6 messages (2-3 exchanges) for context
            recent_history = history[-6:] if len(history) >= 6 else history
            for msg in recent_history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if not content:
                    continue
                    
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
        
        # Add current user message with context note
        if history:
            history_note = "\n\n[Note: Conversation history provided above for context]"
        elif history_summary:
            history_note = f"\n\n[History summary: {history_summary}]"
        else:
            history_note = ""
        
        user_content = f"User message: {user_message}{history_note}\n\nReturn agent_key and reason."
        messages.append(HumanMessage(content=user_content))
        
        try:
            result = self.chain.invoke(messages)
            agent_key = result.agent_key
            if agent_key not in ("guest_faq", "action_expert", "journey_register", "rewards_invite"):
                logger.warning(f"Router returned invalid agent_key '{agent_key}', defaulting to guest_faq")
                agent_key = "guest_faq"
            return agent_key
        except Exception as e:
            logger.warning(f"Router chain failed: {e}, defaulting to guest_faq")
            return "guest_faq"
