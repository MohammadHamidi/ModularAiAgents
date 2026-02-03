"""
Chain Executor - Implements process() interface compatible with ChatAgent.
Uses LangChain chains instead of Pydantic AI tool-calling.
"""
import asyncio
import datetime
import logging
import re
import time
from typing import Any, Dict, List, Optional

from shared.base_agent import AgentRequest, AgentResponse
from shared.prompt_builder import build_context_summary
from shared.suggestion_lifecycle import should_show_suggestions, get_updated_session_metadata

from chains.router_chain import RouterChain
from chains.specialist_chain import SpecialistChain
from chains.entity_extraction_chain import EntityExtractionChain

logger = logging.getLogger(__name__)

# Platform URL for suggestion links (open in browser instead of sending as message)
PLATFORM_BASE_URL = "https://safiranayeha.ir"


def _strip_redundant_mid_conversation_greeting(output: str, history: List) -> str:
    """
    When we're mid-conversation (history has prior messages), remove a leading
    redundant greeting like "سلام محمد! چطور می‌تونم کمکت کنم؟" so the response
    starts with the substantive part (e.g. "احسنت به این همت...") and feels natural.
    """
    if not output or not output.strip():
        return output
    if not history or len(history) < 2:
        return output
    text = output.strip()
    # Match: optional whitespace + "سلام" + name/word + ! or ؟ + optional space + greeting phrase + optional ؟!
    # Match full redundant greeting so we keep only the substantive part (e.g. احسنت به این همت...)
    patterns = [
        r"^\s*سلام\s+[^!؟\n]+[!؟]\s*چطور\s+می[‌'\s]*تونم\s+کمکت\s+کنم[؟!]?\s*",
        r"^\s*سلام\s+[^!؟\n]+[!؟]\s*چه\s+خبر\s*(امروز)?[؟!]?\s*",
    ]
    for pat in patterns:
        m = re.match(pat, text, re.IGNORECASE)
        if m:
            rest = text[m.end() :].strip()
            if rest:
                return rest.lstrip("\n").strip()
            break
    return output


def _format_numbered_list_newlines(text: str) -> str:
    """
    Insert newlines before numbered list items so "۱. ... ۲. ... ۳. ..." or "1) ... 2) ..."
    each appear on their own line. Handles Persian (۱۲۳...) and English digits.
    """
    if not text or not text.strip():
        return text
    # Persian digits: ۱ ۲ ۳ etc. – insert newline before " N." when preceded by non-newline
    text = re.sub(r"([^\n])\s+([۱۲۳۴۵۶۷۸۹۰]+[\.\)])\s+", r"\1\n\n\2 ", text)
    # English digits: 2) or 2. – insert newline before " N)" or " N."
    text = re.sub(r"([^\n])\s+(\d+)[\.\)]\s+", r"\1\n\n\2) ", text)
    return text


def _post_process_output(
    output: str,
    agent_key: str,
    agent_name: str,
    user_message: str,
) -> str:
    """
    Apply post-processing to chain output.
    Simplified version of chat_agent post-processing.
    """
    result = output

    # Konesh scope validation for action_expert
    if agent_key == "action_expert":
        konesh_keywords = ["کنش", "محفل", "صبحگاه", "فضاسازی", "مسجد", "مدرسه", "خانه"]
        if not any(kw in user_message.lower() for kw in konesh_keywords):
            return """من متخصص کنش‌های قرآنی سفیران آیه‌ها هستم و فقط می‌تونم در مورد انتخاب، طراحی و اجرای کنش‌ها کمکت کنم.
اگه می‌خوای برای این موقعیت یه کنش یا محفل قرآنی برگزار کنی، خوشحال می‌شم راهنماییت کنم!
پیشنهادهای بعدی:
1) بگو چه بستری در اختیار داری (خانه، مدرسه، مسجد، فضای مجازی)
2) بگو نقشت چیه (معلم، دانش‌آموز، والد، مبلغ)"""

    # Remove unwanted introductory phrases
    unwanted = [
        r"پرسش کلیدی و مهمی مطرح کردید[^\n]*",
        r"بر اساس تجربه نهضت[^\n]*",
        r"برای اینکه صحبت شما[^\n]*",
        r"بسیار عالی[^\n]*",
        r"سؤالی که مطرح کرده‌اید[^\n]*",
        r"یک دغدغه‌ی مهم[^\n]*",
        r"با توجه به نتایج جستجو[^\n]*",
        r"برای پاسخ به این سؤال[^\n]*",
    ]
    for pat in unwanted:
        result = re.sub(pat, "", result, flags=re.MULTILINE | re.IGNORECASE)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    # Put each numbered list item on its own line (Persian and English)
    result = _format_numbered_list_newlines(result)

    return result


def _has_valid_suggestions_block(output: str) -> bool:
    """True only if output has 'پیشنهادهای بعدی:' (or Next actions:) AND at least one numbered line (1) or ۱))."""
    if not output or not output.strip():
        return False
    header = re.search(r"پیشنهادهای بعدی\s*:|Next actions\s*:", output, re.IGNORECASE)
    if not header:
        return False
    after = output[header.end():].strip()
    # Must have at least one line like "1) ..." or "۱) ..."
    return bool(re.search(r"^[\d۱۲۳۴۵۶۷۸۹۰]+\s*\)", after, re.MULTILINE))


def _ensure_suggestions_section(output: str, user_message: str) -> str:
    """
    Append "پیشنهادهای بعدی:" block when missing so the UI can show follow-up buttons.
    Only skip if there is already a valid block (header + numbered list). Otherwise strip any
    broken "پیشنهادهای بعدی:" with no list and append our block.
    """
    if _has_valid_suggestions_block(output):
        return output

    # Strip trailing "پیشنهادهای بعدی:" (or "Next actions:") that has no numbered list, so we don't duplicate
    strip_header = re.search(r"\n\s*پیشنهادهای بعدی\s*:.*$|\n\s*Next actions\s*:.*$", output, re.IGNORECASE | re.DOTALL)
    if strip_header and not re.search(r"[\d۱۲۳۴۵۶۷۸۹۰]+\s*\)", strip_header.group(0)):
        output = output[: strip_header.start()].rstrip()

    out_lower = output.lower()
    user_lower = user_message.lower()
    suggestions: List[str] = []

    # From response content
    if "کنش" in out_lower or "کنش" in user_lower:
        if "ویژه" in out_lower or "ویژه" in user_lower:
            suggestions.extend(["کنش‌های ویژه خانه", "کنش‌های ویژه فضای مجازی", "کنش‌های ویژه مسجد و مدرسه"])
        if "خانه" in out_lower or "خانگی" in out_lower:
            suggestions.append("کنش‌های ویژه خانگی")
        if "مدرسه" in out_lower:
            suggestions.append("نحوه اجرای کنش در مدرسه")
        if "مسجد" in out_lower:
            suggestions.append("کنش‌های مسجد")
        if "محفل" in out_lower:
            suggestions.append("نحوه برگزاری محفل خانگی")
        if "فضای مجازی" in out_lower or "مجازی" in out_lower:
            suggestions.append("کنش‌های فضای مجازی")
        if not suggestions:
            suggestions.extend(["لیست کنش‌های ویژه", "کنش‌های خانه", "کنش‌های مدرسه"])

    if "پلتفرم" in out_lower or "safiranayeha" in out_lower:
        suggestions.append("بریم پلتفرم و لیست کنش‌ها رو ببینم")
    if "محتوا" in out_lower or "استوری" in out_lower or "ثبت‌نام" in out_lower or "کپشن" in out_lower:
        suggestions.append("بریم پلتفرم و لیست کنش‌ها رو ببینم")
        if "لیست کنش" not in " ".join(suggestions):
            suggestions.append("لیست کنش‌های ویژه")

    if "نهضت" in out_lower or "زندگی با آیه" in out_lower:
        if "فلسفه" in out_lower or "داستان" in user_lower:
            suggestions.append("درباره فلسفه نهضت بیشتر بدانم")
        if "سفیر" in out_lower:
            suggestions.append("سفیر آیه‌ها یعنی چی؟")

    if "ثبت" in out_lower or "گزارش" in out_lower:
        suggestions.append("نحوه ثبت گزارش کنش")
    if "امتیاز" in out_lower:
        suggestions.append("سیستم امتیازدهی سفیران")

    # Dedupe and limit
    seen = set()
    unique = []
    for s in suggestions:
        s_clean = s.strip()
        if s_clean and s_clean not in seen and len(unique) < 4:
            seen.add(s_clean)
            unique.append(s_clean)

    if not unique:
        if "کنش" in out_lower:
            unique = ["لیست کنش‌های ویژه", "بریم پلتفرم"]
        else:
            unique = ["درباره نهضت بیشتر بدانم", "کنش‌های موجود"]

    def _suggestion_line(label: str) -> str:
        """Append platform URL for 'go to platform' suggestions so UI can render as link."""
        if "بریم پلتفرم" in label or "لیست کنش" in label:
            return f"{label} | {PLATFORM_BASE_URL}/"
        return label

    block = "\n\nپیشنهادهای بعدی:\n"
    for i, s in enumerate(unique, 1):
        block += f"{i}) {_suggestion_line(s)}\n"
    return output.rstrip() + block


class ChainExecutor:
    """
    Chain-based executor implementing same interface as ChatAgent.process().
    """

    def __init__(
        self,
        agent_configs: Dict[str, Any],
        kb_tool: Any,
        konesh_tool: Optional[Any] = None,
        konesh_csv_tool: Optional[Any] = None,
    ):
        """
        Args:
            agent_configs: {agent_key: AgentConfig} e.g. from AGENT_CONFIGS
            kb_tool: KnowledgeBaseTool instance
            konesh_tool: Optional KoneshQueryTool (action_expert)
            konesh_csv_tool: Optional KoneshCSVTool (full کنش CSV for all agents)
        """
        self.agent_configs = agent_configs
        self.kb_tool = kb_tool
        self.konesh_tool = konesh_tool
        self.konesh_csv_tool = konesh_csv_tool
        self.router = RouterChain()
        self._specialists: Dict[str, SpecialistChain] = {}

    def _get_specialist(self, agent_key: str) -> Optional[SpecialistChain]:
        """Get or create specialist chain for agent_key."""
        if agent_key in self._specialists:
            return self._specialists[agent_key]
        config = self.agent_configs.get(agent_key)
        if not config:
            return None
        konesh = self.konesh_tool if agent_key == "action_expert" else None
        chain = SpecialistChain(
            agent_key=agent_key,
            agent_config=config,
            kb_tool=self.kb_tool,
            konesh_tool=konesh,
            konesh_csv_tool=self.konesh_csv_tool,
        )
        self._specialists[agent_key] = chain
        return chain

    async def process(
        self,
        request: AgentRequest,
        history: Optional[List[Dict[str, Any]]] = None,
        shared_context: Optional[Dict[str, Any]] = None,
        agent_key: str = "unknown",
        session_state: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """
        Process request using chain-based pipeline.
        Same signature and return type as ChatAgent.process().
        """
        start = time.time()
        history = history or []
        shared_context = shared_context or {}
        session_state = session_state or {}
        chat_ui_config = session_state.get("_chat_ui_config") or {}

        # Resolve agent_key via router if orchestrator
        if agent_key == "orchestrator":
            hist_summary = ""
            if history:
                last = history[-2:] if len(history) >= 2 else history
                hist_summary = " | ".join(
                    m.get("content", "")[:80] for m in last if m.get("content")
                )
            agent_key = await asyncio.to_thread(
                self.router.invoke, request.message, hist_summary
            )
            logger.info(f"Router selected agent_key={agent_key}")

        # Get specialist chain
        specialist = self._get_specialist(agent_key)
        if not specialist:
            logger.warning(f"No config for agent_key={agent_key}, defaulting to guest_faq")
            agent_key = "guest_faq"
            specialist = self._get_specialist(agent_key)
        if not specialist:
            return AgentResponse(
                session_id=request.session_id or "",
                output="متأسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید.",
                metadata={"error": "no_specialist", "agent_key": agent_key},
                context_updates={},
            )

        config = self.agent_configs[agent_key]
        agent_name = getattr(config, "agent_name", agent_key)

        # Entity extraction -> context_updates
        extractor = EntityExtractionChain(config)
        context_updates = await extractor.invoke(request.message)

        # Build context block for user message
        context_block = build_context_summary(config, shared_context)

        # Recent user messages
        recent_config = getattr(config, "recent_messages_context", {}) or {}
        count = recent_config.get("count", 2)
        last_user = [
            m for m in history[-count * 3 :]
            if m.get("role") == "user"
        ][-count:]

        # Run specialist chain
        output = await specialist.run(
            user_message=request.message,
            user_info=shared_context,
            last_user_messages=last_user,
            history=history,
            context_block=context_block,
        )

        # Strip redundant mid-conversation greeting so reply starts with substantive content
        output = _strip_redundant_mid_conversation_greeting(output, history)

        # Post-process
        output = _post_process_output(
            output, agent_key, agent_name, request.message
        )

        # Suggestion lifecycle: show suggestions only in guided mode within limits
        show_suggestions, transition_message, switch_to_free = should_show_suggestions(
            session_state, history, chat_ui_config
        )
        if transition_message and (transition_message not in output):
            output = output.rstrip() + "\n\n" + transition_message
        if show_suggestions:
            output = _ensure_suggestions_section(output, request.message)
        session_meta = get_updated_session_metadata(session_state, switch_to_free)

        # Build updated history
        now = datetime.datetime.utcnow().isoformat()
        updated_history = list(history)
        updated_history.append({
            "role": "user",
            "content": request.message,
            "timestamp": now,
        })
        updated_history.append({
            "role": "assistant",
            "content": output,
            "timestamp": now,
        })

        model = getattr(config, "model_config", {}) or {}
        model_name = model.get("default_model") or "chain"
        elapsed_ms = (time.time() - start) * 1000
        logger.info(f"ChainExecutor completed in {elapsed_ms:.0f}ms for {agent_key}")

        return AgentResponse(
            session_id=request.session_id or "",
            output=output,
            metadata={
                "model": model_name,
                "history": updated_history,
                "agent_key": agent_key,
                "executor": "langchain_chain",
                **session_meta,
            },
            context_updates=context_updates,
        )

    async def process_stream(
        self,
        request: AgentRequest,
        history: Optional[List[Dict[str, Any]]] = None,
        shared_context: Optional[Dict[str, Any]] = None,
        agent_key: str = "unknown",
        session_state: Optional[Dict[str, Any]] = None,
    ):
        """
        Process request with real LLM streaming (async generator).
        Yields: {"type": "chunk", "content": str} then {"type": "done", "output": str, "metadata": dict}.
        Only supported when using chain executor (EXECUTOR_MODE=langchain_chain).
        """
        history = history or []
        shared_context = shared_context or {}
        session_state = session_state or {}
        chat_ui_config = session_state.get("_chat_ui_config") or {}

        if agent_key == "orchestrator":
            hist_summary = ""
            if history:
                last = history[-2:] if len(history) >= 2 else history
                hist_summary = " | ".join(
                    m.get("content", "")[:80] for m in last if m.get("content")
                )
            agent_key = await asyncio.to_thread(
                self.router.invoke, request.message, hist_summary
            )
            logger.info(f"Router selected agent_key={agent_key} for stream")

        specialist = self._get_specialist(agent_key)
        if not specialist:
            agent_key = "guest_faq"
            specialist = self._get_specialist(agent_key)
        if not specialist:
            err_msg = "متأسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید."
            yield {"type": "chunk", "content": err_msg}
            yield {
                "type": "done",
                "output": err_msg,
                "metadata": {"error": "no_specialist", "agent_key": agent_key, "history": history},
            }
            return

        config = self.agent_configs[agent_key]
        agent_name = getattr(config, "agent_name", agent_key)
        extractor = EntityExtractionChain(config)
        context_updates = await extractor.invoke(request.message)
        context_block = build_context_summary(config, shared_context)
        recent_config = getattr(config, "recent_messages_context", {}) or {}
        count = recent_config.get("count", 2)
        last_user = [
            m for m in history[-count * 3 :]
            if m.get("role") == "user"
        ][-count:]

        full_output = ""
        try:
            async for chunk in specialist.run_stream(
                user_message=request.message,
                user_info=shared_context,
                last_user_messages=last_user,
                history=history,
                context_block=context_block,
            ):
                full_output += chunk
                yield {"type": "chunk", "content": chunk}
        except Exception as e:
            logger.exception(f"Stream generation failed: {e}")
            full_output = full_output or f"خطا در تولید پاسخ: {str(e)}"
            yield {"type": "chunk", "content": full_output}

        full_output = _strip_redundant_mid_conversation_greeting(full_output, history)
        output = _post_process_output(
            full_output, agent_key, agent_name, request.message
        )
        show_suggestions, transition_message, switch_to_free = should_show_suggestions(
            session_state, history, chat_ui_config
        )
        if transition_message and (transition_message not in output):
            output = output.rstrip() + "\n\n" + transition_message
        if show_suggestions:
            output = _ensure_suggestions_section(output, request.message)
        session_meta = get_updated_session_metadata(session_state, switch_to_free)

        if len(output) > len(full_output):
            yield {"type": "chunk", "content": output[len(full_output):]}

        now = datetime.datetime.utcnow().isoformat()
        updated_history = list(history)
        updated_history.append({
            "role": "user",
            "content": request.message,
            "timestamp": now,
        })
        updated_history.append({
            "role": "assistant",
            "content": output,
            "timestamp": now,
        })
        model = getattr(config, "model_config", {}) or {}
        model_name = model.get("default_model") or "chain"
        yield {
            "type": "done",
            "output": output,
            "metadata": {
                "model": model_name,
                "history": updated_history,
                "agent_key": agent_key,
                "executor": "langchain_chain",
                **session_meta,
            },
            "context_updates": context_updates,
        }
