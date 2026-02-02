"""
Specialist Chain - KB-first pipeline for each agent (guest_faq, action_expert, etc.).
Runs: KB retrieval (optional konesh, optional konesh_csv + KB motevali) -> LLM generation.
"""
import asyncio
import json
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

# Keywords that indicate the user is asking about کنش (use CSV + optional KB motevali)
# Include exact terms and meaning-related / colloquial variants so questions that
# mean "what actions can I do" trigger CSV even without the word "کنش".
KONESH_TOPIC_KEYWORDS = [
    # Exact
    "کنش", "کنش ویژه", "ویژه", "بستر انجام", "بستر", "سطح سختی", "کنش‌گر",
    "هشتگ", "محفل", "صبحگاه", "فضاسازی", "مسجد", "مدرسه", "خانه", "فضای مجازی",
    "لیست کنش", "همه کنش", "کنش‌های خانه", "کنش‌های مدرسه", "کنش‌های مسجد",
    # Meaning-related: activities, suggestions, "what to do"
    "فعالیت", "فعالیت قرآنی", "فعالیت‌های قرآنی", "کارهای قرآنی", "کار قرآنی",
    "برنامه قرآنی", "برنامه‌های قرآنی", "اقدام", "اقدامات", "محتوا برای",
    "چه کار", "چه کاری", "چیکار", "چه فعالیتی", "چه برنامه‌ای", "چه اقدام",
    "پیشنهاد", "پیشنهاد بده", "پیشنهاد کن", "از کجا شروع", "شروع کنم",
    "کارهای خانه", "کارهای مدرسه", "کارهای مسجد", "تو خونه", "توی مدرسه", "تو مسجد",
    "خونه", "خانواده",  # colloquial / family often means home context
]

# Context places: if the message contains one of these AND looks like a question,
# treat as کنش-related even without other keywords.
KONESH_CONTEXT_PLACES = [
    "خانه", "خونه", "مدرسه", "مسجد", "خانواده", "فضای مجازی", "محیط کار",
]

# Question/suggestion patterns (so "چیکار کنم تو مسجد؟" triggers CSV)
KONESH_QUESTION_PATTERNS = [
    "چیکار", "چه کار", "چه کاری", "چطور", "چگونه", "پیشنهاد", "بگو", "بگین",
    "می‌خوام", "میخوام", "می‌تونم", "میتونم", "شروع", "؟", "?",
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


def _is_about_konesh(message: str) -> bool:
    """
    Check if the user message is about کنش (actions) and should use CSV context.
    Works by: (1) exact/semantic keywords, or (2) context place + question pattern,
    so meaning-related questions trigger even without the word "کنش".
    """
    msg = message.strip()
    if not msg or len(msg) < 2:
        return False
    lower = msg.lower()
    # Direct keyword match (exact or meaning-related)
    if any(kw in lower for kw in KONESH_TOPIC_KEYWORDS):
        return True
    # Context place + question/suggestion: e.g. "چیکار کنم تو مسجد؟", "پیشنهاد برای مدرسه"
    has_place = any(place in lower for place in KONESH_CONTEXT_PLACES)
    has_question = any(p in lower for p in KONESH_QUESTION_PATTERNS)
    if has_place and (has_question or len(msg) > 15):
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
        konesh_csv_tool: Optional[Any] = None,
    ):
        """
        Args:
            agent_key: guest_faq, action_expert, journey_register, rewards_invite
            agent_config: Full agent config from YAML
            kb_tool: KnowledgeBaseTool instance
            konesh_tool: Optional KoneshQueryTool for action_expert
            konesh_csv_tool: Optional KoneshCSVTool for all agents (full کنش CSV)
        """
        self.agent_key = agent_key
        self.agent_config = agent_config
        self.kb_tool = kb_tool
        self.konesh_tool = konesh_tool
        self.konesh_csv_tool = konesh_csv_tool
        model_config = getattr(agent_config, "model_config", {}) or {}
        temp = model_config.get("temperature", 0.7)
        self.llm = _create_llm(temperature=temp)

    async def _retrieve_kb(self, user_message: str, history: List[Dict]) -> str:
        """Retrieve KB context for user message. Passes conversation_history to LightRAG for context-aware retrieval."""
        if _is_greeting(user_message):
            return ""
        conv = []
        if history:
            for m in history[-4:]:
                role = m.get("role", "user")
                content = m.get("content", "")
                if content:
                    conv.append({"role": role, "content": content[:500]})
        if conv:
            logger.debug(f"LightRAG query with conversation_history: {len(conv)} messages")
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

    async def _retrieve_konesh_csv(self, user_message: str) -> str:
        """
        Retrieve کنش context from full CSV for all agents when the question is about کنش.
        Uses vizhe=True when user asks for کنش ویژه. Optionally fetches LightRAG context
        using محتواهای مرتبط (motevali_for_kb).
        """
        if not self.konesh_csv_tool:
            return ""
        try:
            # Detect "کنش ویژه" to filter vizhe=True
            vizhe_filter = None
            if "کنش ویژه" in user_message or "کنش‌های ویژه" in user_message or "ویژه" in user_message:
                vizhe_filter = True
            raw = await self.konesh_csv_tool.execute(
                query=user_message,
                vizhe=vizhe_filter,
                limit=15,
            )
            if not raw or "error" in raw.lower():
                return ""
            data = json.loads(raw)
            results = data.get("results", [])
            motevali_for_kb = data.get("motevali_for_kb", [])
            if not results:
                return ""
            # Build context block (truncate if large)
            lines = ["[کنش‌های سفیران آیه‌ها - مرجع CSV]"]
            for i, r in enumerate(results[:10], 1):
                title = r.get("عنوان کنش", "")
                bestar = r.get("بستر انجام", "")
                sathe = r.get("سطح سختی", "")
                koneshgar = r.get("کنش‌گر", "")
                hashtag = r.get("هشتگ‌ها", "")
                motevali = r.get("محتواهای مرتبط", "")
                vizhe = r.get("ویژه", "")
                lines.append(f"{i}. {title} | بستر: {bestar} | سطح: {sathe} | کنش‌گر: {koneshgar} | ویژه: {vizhe}")
                if hashtag:
                    lines.append(f"   هشتگ‌ها: {hashtag}")
                if motevali:
                    lines.append(f"   محتواهای مرتبط (برای جستجو در پایگاه دانش): {motevali}")
                sharh = (r.get("شرح (خلاصه)") or "")[:300]
                if sharh:
                    lines.append(f"   شرح: {sharh}...")
            csv_context = "\n".join(lines)[:5000]
            # Optionally fetch KB with محتواهای مرتبط for LightRAG
            if motevali_for_kb and self.kb_tool:
                try:
                    kb_query = " ".join(motevali_for_kb[:3])
                    if len(kb_query) > 50:
                        kb_result = await self.kb_tool.execute(
                            query=kb_query,
                            mode="mix",
                            include_references=True,
                            only_need_context=True,
                            conversation_history=None,
                        )
                        if kb_result and "UNAVAILABLE" not in (kb_result or ""):
                            csv_context += "\n\n[پایگاه دانش - محتواهای مرتبط با کنش‌ها]\n" + (kb_result[:2500] or "")
                except Exception as e:
                    logger.debug(f"KB motevali fetch skipped: {e}")
            return csv_context
        except Exception as e:
            logger.warning(f"Konesh CSV retrieval failed: {e}")
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

        # Optional konesh (YAML) for action_expert
        konesh_context = ""
        if self.agent_key == "action_expert" and self.konesh_tool:
            konesh_context = await self._retrieve_konesh(user_message)
        if konesh_context:
            kb_context = (kb_context + "\n\n" + konesh_context) if kb_context else konesh_context

        # Full کنش CSV reference for all agents when question is about کنش
        if _is_about_konesh(user_message) and self.konesh_csv_tool:
            csv_context = await self._retrieve_konesh_csv(user_message)
            if csv_context:
                kb_context = (kb_context + "\n\n" + csv_context) if kb_context else csv_context

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

    async def run_stream(
        self,
        user_message: str,
        user_info: Dict[str, Any],
        last_user_messages: List[Dict[str, Any]],
        history: List[Dict],
        context_block: str = "",
    ):
        """
        Same as run() but streams LLM tokens as they are generated (async generator).
        Yields content chunks (str) so the client can display text in real time.
        """
        # Same context retrieval as run()
        kb_context = await self._retrieve_kb(user_message, history or [])
        if not kb_context:
            kb_context = ""
        konesh_context = ""
        if self.agent_key == "action_expert" and self.konesh_tool:
            konesh_context = await self._retrieve_konesh(user_message)
        if konesh_context:
            kb_context = (kb_context + "\n\n" + konesh_context) if kb_context else konesh_context
        if _is_about_konesh(user_message) and self.konesh_csv_tool:
            csv_context = await self._retrieve_konesh_csv(user_message)
            if csv_context:
                kb_context = (kb_context + "\n\n" + csv_context) if kb_context else csv_context
        if not kb_context:
            kb_context = "(No KB context retrieved - answer from general knowledge if needed.)"

        system_prompt = build_system_prompt(
            self.agent_config,
            user_info,
            last_user_messages,
            executor_mode="langchain_chain",
            agent_key=self.agent_key,
        )
        system_prompt += "\n\n[Context from Knowledge Base provided below. Use it to answer in your warm, natural tone. Never mention KB or database.]"

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

        async for chunk in self.llm.astream(messages):
            content = getattr(chunk, "content", None) if chunk else None
            if content is not None and isinstance(content, str):
                yield content
