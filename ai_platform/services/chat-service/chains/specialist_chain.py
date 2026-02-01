"""
Specialist Chain - KB-first pipeline for each agent (guest_faq, action_expert, etc.).
Runs: KB retrieval (optional konesh) -> LLM generation.
"""
import asyncio
import os
import logging
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

from shared.prompt_builder import build_system_prompt

logger = logging.getLogger(__name__)

# Greetings that don't need KB
GREETINGS = [
    "سلام", "خداحافظ", "خدا حافظ", "hi", "hello", "bye", "goodbye",
    "صبح بخیر", "عصر بخیر", "شب بخیر"
]


def _is_greeting(message: str) -> bool:
    """Check if message is a simple greeting."""
    msg = message.strip().lower()
    if msg in GREETINGS:
        return True
    for g in GREETINGS:
        if msg.startswith(g) and len(msg) <= len(g) + 2:
            return True
    return False


def _create_llm(temperature: float = 0.7) -> ChatOpenAI:
    """Create LangChain LLM with LiteLLM config."""
    model = os.getenv("LITELLM_MODEL", "gemini-2.5-flash-lite-preview-09-2025")
    api_key = os.getenv("LITELLM_API_KEY", "")
    base_url = os.getenv("LITELLM_BASE_URL", "https://api.avalai.ir/v1")
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        openai_api_key=api_key,
        openai_api_base=base_url,
    )


USER_TEMPLATE = """{kb_context}

{context_block}

User message: {user_message}
"""


class SpecialistChain:
    """KB-first chain for specialist agents."""

    def __init__(
        self,
        agent_key: str,
        agent_config: Any,
        kb_tool: Any,
        konesh_tool: Optional[Any] = None,
    ):
        """
        Args:
            agent_key: guest_faq, action_expert, journey_register, rewards_invite
            agent_config: Full agent config from YAML
            kb_tool: KnowledgeBaseTool instance
            konesh_tool: Optional KoneshQueryTool for action_expert
        """
        self.agent_key = agent_key
        self.agent_config = agent_config
        self.kb_tool = kb_tool
        self.konesh_tool = konesh_tool
        model_config = getattr(agent_config, "model_config", {}) or {}
        temp = model_config.get("temperature", 0.7)
        self.llm = _create_llm(temperature=temp)

    async def _retrieve_kb(self, user_message: str, history: List[Dict]) -> str:
        """Retrieve KB context for user message."""
        if _is_greeting(user_message):
            return ""
        conv = []
        if history:
            for m in history[-4:]:
                role = m.get("role", "user")
                content = m.get("content", "")
                if content:
                    conv.append({"role": role, "content": content[:500]})
        try:
            result = await self.kb_tool.execute(
                query=user_message,
                mode="mix",
                include_references=True,
                only_need_context=True,
                conversation_history=conv if conv else None,
            )
            if result and "[Knowledge Base" in result and "UNAVAILABLE" not in result:
                return result
            return ""
        except Exception as e:
            logger.warning(f"KB retrieval failed: {e}")
            return ""

    async def _retrieve_konesh(self, user_message: str) -> str:
        """Optionally retrieve konesh context for action_expert."""
        if not self.konesh_tool:
            return ""
        try:
            result = await self.konesh_tool.execute(query=user_message)
            if result and "error" not in result.lower():
                return f"[Konesh / کنش Context]\n{result[:3000]}"
        except Exception as e:
            logger.warning(f"Konesh retrieval failed: {e}")
        return ""

    async def run(
        self,
        user_message: str,
        user_info: Dict[str, Any],
        last_user_messages: List[Dict[str, Any]],
        history: List[Dict],
        context_block: str = "",
    ) -> str:
        """
        Run specialist chain: KB -> (optional konesh) -> LLM.

        Returns:
            Generated response text
        """
        # Retrieve KB context
        kb_context = await self._retrieve_kb(user_message, history or [])
        if not kb_context:
            kb_context = ""

        # Optional konesh for action_expert
        konesh_context = ""
        if self.agent_key == "action_expert" and self.konesh_tool:
            konesh_context = await self._retrieve_konesh(user_message)
        if konesh_context:
            kb_context = (kb_context + "\n\n" + konesh_context) if kb_context else konesh_context

        if not kb_context:
            kb_context = "(No KB context retrieved - answer from general knowledge if needed.)"

        # Build system prompt via shared builder
        system_prompt = build_system_prompt(
            self.agent_config,
            user_info,
            last_user_messages,
            executor_mode="langchain_chain",
            agent_key=self.agent_key,
        )

        # Add KB instruction for chain mode
        system_prompt += "\n\n[Context from Knowledge Base provided below. Use it to answer in your warm, natural tone. Never mention KB or database.]"

        # Build user prompt
        ctx_block = context_block or ""
        if ctx_block and not ctx_block.strip().startswith("<"):
            ctx_block = f"<internal_context>\n{ctx_block}\n</internal_context>\n\n"

        user_prompt = USER_TEMPLATE.format(
            kb_context=kb_context,
            context_block=ctx_block,
            user_message=user_message,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = await self.llm.ainvoke(messages)
        return response.content if hasattr(response, "content") else str(response)
