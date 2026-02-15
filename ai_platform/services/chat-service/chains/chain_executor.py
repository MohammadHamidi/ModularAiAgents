"""
Chain Executor - Implements process() interface compatible with ChatAgent.
Uses LangChain chains instead of Pydantic AI tool-calling.
"""
import asyncio
import datetime
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from shared.base_agent import AgentRequest, AgentResponse
from shared.prompt_builder import build_context_summary
from shared.suggestion_utils import (
    convert_suggestions_to_user_perspective,
    ensure_suggestions_section,
)

from chains.router_chain import RouterChain
from chains.specialist_chain import SpecialistChain
from chains.entity_extraction_chain import EntityExtractionChain
from monitoring import ExecutionTrace, trace_collector

logger = logging.getLogger(__name__)


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

    # Note: Scope validation removed - AI agents handle scope through their system prompts and context
    # This allows natural conversation flow without blocking valid follow-up messages

    # Remove LightRAG citation artifacts (Reference ID: N)
    result = re.sub(r"\s*\(Reference\s+ID:\s*\d+\)\s*", " ", result, flags=re.IGNORECASE)

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

    return result


class ChainExecutor:
    """
    Chain-based executor implementing same interface as ChatAgent.process().
    """

    def __init__(
        self,
        agent_configs: Dict[str, Any],
        kb_tool: Any,
        konesh_tool: Optional[Any] = None,
        local_knowledge_tool: Optional[Any] = None,
        safiran_content_tool: Optional[Any] = None,
        safiran_action_tool: Optional[Any] = None,
        log_service: Optional[Any] = None,
    ):
        """
        Args:
            agent_configs: {agent_key: AgentConfig} e.g. from AGENT_CONFIGS
            kb_tool: KnowledgeBaseTool instance
            konesh_tool: Optional KoneshQueryTool
            local_knowledge_tool: Optional LocalKnowledgeTool for verses/angareh/konesh type
            safiran_content_tool: Optional Safiran content tool
            safiran_action_tool: Optional Safiran action tool
            log_service: Optional LogService for persisting traces
        """
        self.agent_configs = agent_configs
        self.kb_tool = kb_tool
        self.konesh_tool = konesh_tool
        self.local_knowledge_tool = local_knowledge_tool
        self.safiran_content_tool = safiran_content_tool
        self.safiran_action_tool = safiran_action_tool
        self.log_service = log_service
        self.router = RouterChain()
        self._specialists: Dict[str, SpecialistChain] = {}

    def _get_specialist(self, agent_key: str) -> Optional[SpecialistChain]:
        """Get or create specialist chain for agent_key."""
        if agent_key in self._specialists:
            return self._specialists[agent_key]
        config = self.agent_configs.get(agent_key)
        if not config:
            return None
        # action_expert, content_generation_expert, konesh_expert use konesh_tool
        konesh = self.konesh_tool if agent_key in ("action_expert", "content_generation_expert", "konesh_expert") else None
        local_knowledge = self.local_knowledge_tool if agent_key in ("action_expert", "content_generation_expert", "konesh_expert") else None
        safiran_content = self.safiran_content_tool if agent_key == "content_generation_expert" else None
        safiran_action = self.safiran_action_tool if agent_key == "action_expert" else None
        chain = SpecialistChain(
            agent_key=agent_key,
            agent_config=config,
            kb_tool=self.kb_tool,
            konesh_tool=konesh,
            local_knowledge_tool=local_knowledge,
            safiran_content_tool=safiran_content,
            safiran_action_tool=safiran_action,
        )
        self._specialists[agent_key] = chain
        return chain

    async def process(
        self,
        request: AgentRequest,
        history: Optional[List[Dict[str, Any]]] = None,
        shared_context: Optional[Dict[str, Any]] = None,
        agent_key: str = "unknown",
        summary_block: str = "",
    ) -> AgentResponse:
        """
        Process request using chain-based pipeline.
        Same signature and return type as ChatAgent.process().
        """
        start = time.time()
        history = history or []
        shared_context = shared_context or {}
        routed_from_orchestrator = False
        original_agent_key = agent_key

        # Resolve agent_key via router if orchestrator
        if agent_key == "orchestrator":
            routed_from_orchestrator = True
            # Pass full conversation history to router for better context
            try:
                agent_key = await asyncio.to_thread(
                    self.router.invoke, request.message, history or []
                )
                logger.info(f"Router selected agent_key={agent_key}")
            except Exception as e:
                logger.error(f"Router chain failed: {e}", exc_info=True)
                # Default to guest_faq on router failure
                agent_key = "guest_faq"
                logger.info(f"Router failed, defaulting to guest_faq")

        # Get specialist chain
        specialist = self._get_specialist(agent_key)
        if not specialist:
            logger.warning(f"No config for agent_key={agent_key}, defaulting to guest_faq")
            agent_key = "guest_faq"
            specialist = self._get_specialist(agent_key)
        if not specialist:
            logger.error(f"CRITICAL: No specialist found for agent_key={agent_key} even after fallback to guest_faq")
            # Return a helpful message instead of generic error
            return AgentResponse(
                session_id=request.session_id or "",
                output=(
                    "ببخشید دوست خوبم، مشکلی در سیستم پیش اومده. "
                    "لطفاً دوباره تلاش کن یا با پشتیبانی تماس بگیر. "
                    "من اینجا هستم تا درباره کنش‌های قرآنی و نهضت زندگی با آیه‌ها کمکت کنم."
                ),
                metadata={"error": "no_specialist", "agent_key": agent_key},
                context_updates={},
            )

        config = self.agent_configs[agent_key]
        agent_name = getattr(config, "agent_name", agent_key)

        # Entity extraction -> context_updates (with conversation history for context)
        extractor = EntityExtractionChain(config)
        context_updates = await extractor.invoke(request.message, history=history)

        # Build context block for user message (includes optional summary)
        context_block = build_context_summary(config, shared_context)
        if summary_block:
            context_block = (context_block or "") + summary_block

        # Recent user messages
        recent_config = getattr(config, "recent_messages_context", {}) or {}
        count = recent_config.get("count", 2)
        last_user = [
            m for m in history[-count * 3 :]
            if m.get("role") == "user"
        ][-count:]

        # Run specialist chain with error handling
        try:
            run_result = await specialist.run(
                user_message=request.message,
                user_info=shared_context,
                last_user_messages=last_user,
                history=history,
                context_block=context_block,
            )
            output = run_result["output"]
            system_prompt = run_result.get("system_prompt", "")
            kb_context = run_result.get("kb_context", "")
            user_prompt = run_result.get("user_prompt", "")
        except Exception as e:
            logger.error(f"Specialist chain failed for {agent_key}: {e}", exc_info=True)
            # Return a polite scope refusal message instead of generic error
            # This handles cases where out-of-scope questions cause exceptions
            output = (
                "ببخشید دوست خوبم، این سوال خارج از حیطه کاری من هست. "
                "من اینجا هستم تا درباره کنش‌های قرآنی و نهضت زندگی با آیه‌ها کمکت کنم. "
                "می‌خوای ببینیم چه کنش‌هایی وجود داره یا چطور می‌تونی شروع کنی؟"
            )
            system_prompt = ""
            kb_context = ""
            user_prompt = ""

        # Post-process: unwanted text cleanup
        output = _post_process_output(
            output, agent_key, agent_name, request.message
        )

        # Post-process: suggestions
        post_processing_applied = []
        out_before_conv = output
        output = convert_suggestions_to_user_perspective(output)
        if output != out_before_conv:
            post_processing_applied.append("convert_suggestions_perspective")
        out_before_ensure = output
        output = ensure_suggestions_section(
            output, request.message, agent_key
        )
        if output != out_before_ensure:
            post_processing_applied.append("ensure_suggestions_section")

        # Build trace for monitoring
        elapsed_ms = (time.time() - start) * 1000
        trace = ExecutionTrace(
            session_id=request.session_id or "no-session",
            agent_key=agent_key,
            agent_name=agent_name,
            timestamp=datetime.datetime.now(),
            system_prompt=system_prompt,
            user_message_original=request.message,
            user_message_final=user_prompt[:500] if user_prompt else request.message,
            shared_context=shared_context,
            message_history_count=len(history),
            kb_queries=[{"query": request.message, "result_preview": kb_context[:500]}] if kb_context else [],
            kb_results=[{"preview": kb_context[:500]}] if kb_context else [],
            llm_input_full=user_prompt,
            llm_output_raw=run_result.get("output", ""),
            routing_decision={"routed": routed_from_orchestrator, "target_agent": agent_key} if routed_from_orchestrator else None,
            final_response=output,
            post_processing_applied=post_processing_applied,
            execution_time_ms=elapsed_ms,
        )
        trace_collector.add_trace(trace)

        # Persist trace to log service for log viewer
        if self.log_service:
            try:
                sid = None
                if request.session_id:
                    try:
                        sid = uuid.UUID(request.session_id)
                    except ValueError:
                        pass
                await self.log_service.append_log(
                    log_type="trace",
                    session_id=sid,
                    agent_key=agent_key,
                    metadata={
                        "agent_name": agent_name,
                        "execution_time_ms": elapsed_ms,
                        "routing_decision": trace.routing_decision,
                    },
                    duration_ms=elapsed_ms,
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Log service append failed: {e}")

        # Build updated history (with message_id for feedback)
        now = datetime.datetime.utcnow().isoformat()
        user_msg_id = str(uuid.uuid4())
        assistant_msg_id = str(uuid.uuid4())
        updated_history = list(history)
        updated_history.append({
            "role": "user",
            "content": request.message,
            "timestamp": now,
            "message_id": user_msg_id,
        })
        updated_history.append({
            "role": "assistant",
            "content": output,
            "timestamp": now,
            "message_id": assistant_msg_id,
        })

        model = getattr(config, "model_config", {}) or {}
        model_name = model.get("default_model") or "chain"
        logger.info(f"ChainExecutor completed in {elapsed_ms:.0f}ms for {agent_key}")

        return AgentResponse(
            session_id=request.session_id or "",
            output=output,
            metadata={
                "model": model_name,
                "history": updated_history,
                "agent_key": agent_key,
                "executor": "langchain_chain",
            },
            context_updates=context_updates,
        )
