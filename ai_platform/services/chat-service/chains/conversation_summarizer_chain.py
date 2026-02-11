"""
Conversation Summarizer Chain - Summarizes conversation history for context.
Uses incremental summarization: can extend existing summary with new messages.
"""
import os
import logging
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """تو یک خلاصه‌ساز مکالمه هستی.
خلاصهٔ زیر را از مکالمهٔ کاربر و دستیار بساز.
نکات کلیدی، تصمیمات، و زمینه را حفظ کن.
مختصر و مفید بنویس. به زبان فارسی."""

INCREMENTAL_SYSTEM_PROMPT = """تو یک خلاصه‌ساز مکالمه هستی.
خلاصهٔ قبلی و پیام‌های جدید را داریم.
خلاصهٔ به‌روز را بنویس که هر دو را ادغام کند.
نکات کلیدی، تصمیمات، و زمینه را حفظ کن.
مختصر و مفید بنویس. به زبان فارسی."""


def _format_messages(messages: List[Dict[str, Any]]) -> str:
    """Format messages for prompt."""
    lines = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if content:
            prefix = "کاربر" if role == "user" else "دستیار"
            lines.append(f"{prefix}: {content[:800]}")
    return "\n".join(lines)


def _create_llm() -> ChatOpenAI:
    """Create LangChain LLM with LiteLLM config."""
    model = os.getenv("LITELLM_MODEL", "gemini-2.5-flash-lite-preview-09-2025")
    api_key = os.getenv("LITELLM_API_KEY", "")
    base_url = os.getenv("LITELLM_BASE_URL", "https://api.avalai.ir/v1")
    return ChatOpenAI(
        model=model,
        temperature=0.3,
        openai_api_key=api_key,
        openai_api_base=base_url,
    )


class ConversationSummarizerChain:
    """Summarizes conversation history for context building."""

    def __init__(self):
        self.llm = _create_llm()

    async def summarize(
        self,
        messages: List[Dict[str, Any]],
        existing_summary: Optional[str] = None,
    ) -> str:
        """
        Summarize messages. If existing_summary is provided, perform incremental
        summarization (existing + new messages -> new summary).

        Args:
            messages: List of {role, content} dicts to summarize
            existing_summary: Optional previous summary to extend

        Returns:
            Summarized text in Persian
        """
        if not messages:
            return existing_summary or ""

        formatted = _format_messages(messages)

        if existing_summary and existing_summary.strip():
            system = SystemMessage(content=INCREMENTAL_SYSTEM_PROMPT)
            user_content = f"""خلاصهٔ قبلی:
{existing_summary}

پیام‌های جدید:
{formatted}

خلاصهٔ به‌روز را بنویس:"""
        else:
            system = SystemMessage(content=SUMMARY_SYSTEM_PROMPT)
            user_content = f"""مکالمه:
{formatted}

خلاصه را بنویس:"""

        try:
            response = await self.llm.ainvoke(
                [system, HumanMessage(content=user_content)]
            )
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.warning(f"Summarization failed: {e}")
            return existing_summary or formatted[:500]
