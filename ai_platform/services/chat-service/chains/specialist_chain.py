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
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

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
    # Set max_tokens to prevent truncation (default 8192 for longer responses)
    max_tokens = int(os.getenv("LITELLM_MAX_TOKENS", "8192"))
    llm = ChatOpenAI(
        model=model,
        temperature=temperature,
        openai_api_key=api_key,
        openai_api_base=base_url,
        max_tokens=max_tokens,
    )
    return llm


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
        local_knowledge_tool: Optional[Any] = None,
        safiran_content_tool: Optional[Any] = None,
        safiran_action_tool: Optional[Any] = None,
    ):
        """
        Args:
            agent_key: guest_faq, action_expert, content_generation_expert, konesh_expert, etc.
            agent_config: Full agent config from YAML
            kb_tool: KnowledgeBaseTool instance
            konesh_tool: Optional KoneshQueryTool
            local_knowledge_tool: Optional LocalKnowledgeTool for verses/angareh/konesh type
            safiran_content_tool: Optional Safiran content query tool
            safiran_action_tool: Optional Safiran action query tool
        """
        self.agent_key = agent_key
        self.agent_config = agent_config
        self.kb_tool = kb_tool
        self.konesh_tool = konesh_tool
        self.local_knowledge_tool = local_knowledge_tool
        self.safiran_content_tool = safiran_content_tool
        self.safiran_action_tool = safiran_action_tool
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
                top_k=12,  # Fetch more context so the AI can give complete answers
                conversation_history=conv if conv else None,
            )
            if result and "[Knowledge Base" in result and "UNAVAILABLE" not in result:
                # Truncate KB context only if very long; allow enough for complete answers
                max_kb_chars = 10000
                if len(result) > max_kb_chars:
                    # Truncate but keep the beginning (most relevant) and add indicator
                    truncated = result[:max_kb_chars]
                    # Try to truncate at a sentence boundary if possible
                    last_period = truncated.rfind('.')
                    last_newline = truncated.rfind('\n')
                    cutoff = max(last_period, last_newline)
                    if cutoff > max_kb_chars * 0.8:  # Only use cutoff if it's not too early
                        truncated = truncated[:cutoff + 1]
                    return truncated + "\n\n[KB context truncated for length - most relevant content shown]"
                return result
            return ""
        except Exception as e:
            logger.warning(f"KB retrieval failed: {e}")
            return ""

    async def _retrieve_konesh(self, user_message: str) -> str:
        """Retrieve konesh context for action_expert, content_generation_expert, konesh_expert."""
        if not self.konesh_tool:
            return ""
        try:
            result = await self.konesh_tool.execute(query=user_message)
            if result and "error" not in result.lower():
                return f"[Konesh / کنش Context]\n{result[:3000]}"
        except Exception as e:
            logger.warning(f"Konesh retrieval failed: {e}")
        return ""

    async def _retrieve_local_knowledge(
        self, user_message: str, user_info: Dict[str, Any]
    ) -> str:
        """Retrieve verse/angareh/konesh type context when message relates to verse, action, or angareh."""
        if not self.local_knowledge_tool:
            return ""
        try:
            # Extract konesh name from action_details if available
            konesh_name: Optional[str] = None
            action_details_data = (user_info or {}).get("action_details")
            if action_details_data:
                action_details = (
                    action_details_data.get("value")
                    if isinstance(action_details_data, dict)
                    else action_details_data
                )
                if isinstance(action_details, dict):
                    data_obj = action_details.get("data") or action_details
                    konesh_name = (
                        data_obj.get("title")
                        or data_obj.get("name")
                        or data_obj.get("actionTitle")
                    )
            result = await self.local_knowledge_tool.execute(
                query=user_message,
                konesh_name=konesh_name,
            )
            if result and "error" not in result.lower():
                return f"[Local Knowledge: ۳۰ آیه و انگاره]\n{result[:2500]}"
        except Exception as e:
            logger.warning(f"Local knowledge retrieval failed: {e}")
        return ""

    def _extract_action_id_from_user_info(self, user_info: Dict[str, Any]) -> Optional[int]:
        entry_path_data = (user_info or {}).get("entry_path")
        if not entry_path_data:
            return None
        entry_path = entry_path_data.get("value") if isinstance(entry_path_data, dict) else entry_path_data
        if not isinstance(entry_path, str):
            return None
        import re
        m = re.search(r"/actions/(\d+)", entry_path)
        return int(m.group(1)) if m else None

    async def _retrieve_safiran_content(self, user_message: str, user_info: Dict[str, Any]) -> str:
        if not self.safiran_content_tool:
            return ""
        try:
            action_id = self._extract_action_id_from_user_info(user_info)
            kwargs: Dict[str, Any] = {"query": user_message, "page": 1, "page_size": 6}
            if action_id:
                kwargs["action_ids"] = [action_id]
            result = await self.safiran_content_tool.execute(**kwargs)
            if result and "error" not in result.lower():
                return f"[Safiran Content Context]\n{result[:3500]}"
        except Exception as e:
            logger.warning(f"Safiran content retrieval failed: {e}")
        return ""

    async def _retrieve_safiran_actions(self, user_message: str, user_info: Dict[str, Any]) -> str:
        if not self.safiran_action_tool:
            return ""
        try:
            # Basic personalized hint from shared context
            level_val = (user_info.get("user_level") or {}).get("value") if isinstance(user_info.get("user_level"), dict) else None
            kwargs: Dict[str, Any] = {"query": user_message, "page": 1, "page_size": 8}
            if isinstance(level_val, int):
                kwargs["levels"] = [level_val]
            result = await self.safiran_action_tool.execute(**kwargs)
            if result and "error" not in result.lower():
                return f"[Safiran Actions Context]\n{result[:3500]}"
        except Exception as e:
            logger.warning(f"Safiran action retrieval failed: {e}")
        return ""

    async def run(
        self,
        user_message: str,
        user_info: Dict[str, Any],
        last_user_messages: List[Dict[str, Any]],
        history: List[Dict],
        context_block: str = "",
    ) -> Dict[str, Any]:
        """
        Run specialist chain: KB -> (optional konesh) -> LLM.

        Returns:
            Dict with output, system_prompt, kb_context, user_prompt for trace collection
        """
        # Retrieve KB context
        kb_context = await self._retrieve_kb(user_message, history or [])
        if not kb_context:
            kb_context = ""

        # Optional local knowledge (verses/angareh/konesh type) for content_generation_expert, konesh_expert
        if self.agent_key in ("content_generation_expert", "konesh_expert") and self.local_knowledge_tool:
            local_ctx = await self._retrieve_local_knowledge(user_message, user_info or {})
            if local_ctx:
                kb_context = (local_ctx + "\n\n" + kb_context) if kb_context else local_ctx

        # Optional konesh for action_expert, content_generation_expert, konesh_expert
        konesh_context = ""
        if self.agent_key in ("action_expert", "content_generation_expert", "konesh_expert") and self.konesh_tool:
            konesh_context = await self._retrieve_konesh(user_message)
        if konesh_context:
            kb_context = (kb_context + "\n\n" + konesh_context) if kb_context else konesh_context

        # Optional Safiran content context for content_generation_expert
        if self.agent_key == "content_generation_expert" and self.safiran_content_tool:
            content_ctx = await self._retrieve_safiran_content(user_message, user_info or {})
            if content_ctx:
                kb_context = (kb_context + "\n\n" + content_ctx) if kb_context else content_ctx

        # Optional Safiran action recommendation context for action_expert
        if self.agent_key == "action_expert" and self.safiran_action_tool:
            actions_ctx = await self._retrieve_safiran_actions(user_message, user_info or {})
            if actions_ctx:
                kb_context = (kb_context + "\n\n" + actions_ctx) if kb_context else actions_ctx

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
        system_prompt += "\n\n[Context from Knowledge Base provided below. Use it fully to answer the user's question completely in your warm, natural tone. Never mention KB or database.]"

        # Build user prompt
        ctx_block = context_block or ""
        if ctx_block and not ctx_block.strip().startswith("<"):
            ctx_block = f"<internal_context>\n{ctx_block}\n</internal_context>\n\n"

        user_prompt = USER_TEMPLATE.format(
            kb_context=kb_context,
            context_block=ctx_block,
            user_message=user_message,
        )

        # Build messages with conversation history
        messages = [SystemMessage(content=system_prompt)]
        
        # Add conversation history (last few messages for context)
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
        
        # Add current user message
        messages.append(HumanMessage(content=user_prompt))
        
        response = await self.llm.ainvoke(messages)
        output = response.content if hasattr(response, "content") else str(response)
        return {
            "output": output,
            "system_prompt": system_prompt,
            "kb_context": kb_context,
            "user_prompt": user_prompt,
        }
