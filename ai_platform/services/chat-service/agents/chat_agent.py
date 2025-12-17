import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.messages import ModelMessage as PydanticChatMessage

from shared.base_agent import BaseAgent, AgentConfig, AgentRequest, AgentResponse
from agents.litellm_compat import create_litellm_compatible_client


class ChatAgent(BaseAgent):
    """Chat agent implementation with hybrid session memory support."""

    async def initialize(self, http_client: httpx.AsyncClient | None = None):
        # Use provided http_client or create a new one
        client = http_client or create_litellm_compatible_client()

        openai_client = AsyncOpenAI(
            api_key=self.config.extra.get("api_key"),
            base_url=self.config.extra.get("base_url"),
            http_client=client,
        )
        provider = OpenAIProvider(openai_client=openai_client)
        model = OpenAIChatModel(self.config.model, provider=provider)

        # Don't set static system_prompt here - we'll create dynamic system messages
        # in process() that combine the static prompt with session context
        self.agent = Agent(model)
        # Only store http_client if we created it ourselves
        if http_client is None:
            self.http_client = client
        else:
            self.http_client = None

    def _convert_history(
        self, history: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Convert stored history dicts into simple role/content dicts.

        Stored messages are simple dicts: {\"role\": ..., \"content\": ..., \"timestamp\": ...}.
        """
        if not history:
            return []

        converted: List[Dict[str, Any]] = []
        for msg in history:
            role = msg.get("role") or "user"
            content = msg.get("content") or ""
            if not content:
                continue

            # pydantic_ai Agent accepts message_history as list of role/content-like items;
            # we keep this as plain dicts to avoid tight coupling to internal message classes.
            converted.append({"role": role, "content": content})
        return converted

    def _extract_user_signals(
        self, message: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Extract simple structured signals (name, language, prefs) from user message.

        Returns (context_updates, user_prefs_updates) dictionaries.
        This is intentionally simple/regex-based for now.
        """
        context_updates: Dict[str, Any] = {}
        prefs_updates: Dict[str, Any] = {}

        text = message.strip()

        # Very simple Persian and English patterns for name
        lowered = text.lower()
        if "من " in text and ("هستم" in text or "ام" in text):
            # e.g. "من محمد هستم" / "من محمدم"
            try:
                after_man = text.split("من", 1)[1].strip()
                # remove trailing punctuation
                after_man = (
                    after_man.replace("هستم", "")
                    .replace("ام", "")
                    .replace(".", "")
                    .strip()
                )
                if after_man:
                    context_updates["user_name"] = {"value": after_man}
            except Exception:
                pass

        if "اسم من" in text:
            # e.g. "اسم من محمد است"
            try:
                after_esme = text.split("اسم من", 1)[1].strip()
                after_esme = (
                    after_esme.replace("است", "")
                    .replace("هست", "")
                    .replace(".", "")
                    .strip()
                )
                if after_esme:
                    context_updates["user_name"] = {"value": after_esme}
            except Exception:
                pass

        if "my name is" in lowered:
            try:
                after = lowered.split("my name is", 1)[1].strip()
                # take first token as simple name
                name = after.split()[0]
                if name:
                    context_updates["user_name"] = {"value": name}
            except Exception:
                pass

        if lowered.startswith("i am "):
            try:
                name = lowered.split("i am ", 1)[1].strip().split()[0]
                if name:
                    context_updates["user_name"] = {"value": name}
            except Exception:
                pass

        # Preferred language (very simple signals)
        if "با من فارسی حرف بزن" in text or "فارسی صحبت کن" in text:
            context_updates["preferred_language"] = {"value": "fa"}

        if "speak english" in lowered or "talk to me in english" in lowered:
            context_updates["preferred_language"] = {"value": "en"}

        if context_updates:
            prefs_updates["user_prefs"] = context_updates

        return context_updates, prefs_updates

    async def process(
        self,
        request: AgentRequest,
        history: Optional[List[Dict[str, Any]]] = None,
        shared_context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        # Convert persisted history into pydantic_ai format
        message_history = self._convert_history(history)

        # Extract structured signals from latest user message
        context_updates, prefs_updates = self._extract_user_signals(request.message)

        # Build context-aware view by merging existing context
        merged_context: Dict[str, Any] = {}
        if shared_context:
            merged_context.update(shared_context)
        merged_context.update(context_updates)
        merged_context.update(prefs_updates)

        # Helper: extract plain user_name from merged context (if any)
        def _extract_name_from_context(ctx: Dict[str, Any]) -> Optional[str]:
            if "user_name" not in ctx:
                return None
            raw = ctx["user_name"]
            if isinstance(raw, dict):
                return (raw.get("value") or "").strip() or None
            return str(raw).strip() or None

        user_name_value = _extract_name_from_context(merged_context)

        # Helper: detect "what is my name / who am I" style questions
        lowered = request.message.strip().lower()
        is_name_question = any(
            phrase in lowered
            for phrase in [
                "اسم من چیه",
                "اسم من چیست",
                "من کی هستم",
                "what is my name",
                "who am i",
            ]
        )

        # If we already know the user's name in session context and the user
        # explicitly asks for it, answer deterministically from context instead
        # of delegating to the LLM (to avoid hallucination / forgetting).
        if user_name_value and is_name_question:
            assistant_output = f"اسم شما {user_name_value} است."
        else:
            # Build a combined system message that includes:
            # 1. The static system prompt from config
            # 2. Dynamic session context (user name, language preference, etc.)

            # Start with the static system prompt
            static_prompt = self.config.extra.get("system_prompt", "")

            # Build dynamic context information
            context_info: List[str] = []
            if user_name_value:
                context_info.append(f"نام کاربر: {user_name_value}")

            preferred_lang = merged_context.get("preferred_language")
            if preferred_lang:
                if isinstance(preferred_lang, dict):
                    lang_value = (preferred_lang.get("value") or "").strip()
                else:
                    lang_value = str(preferred_lang).strip()
                if lang_value:
                    context_info.append(f"زبان ترجیحی: {lang_value}")

            # Combine static prompt with dynamic context
            system_parts = []
            if static_prompt:
                system_parts.append(static_prompt)
            if context_info:
                system_parts.append("اطلاعات سشن فعلی:\n" + "\n".join(context_info))

            # Create the combined system message
            if system_parts:
                combined_system_message = "\n\n".join(system_parts)
                # Insert or update system message at the beginning of history
                if not message_history or message_history[0].get("role") != "system":
                    message_history.insert(
                        0, {"role": "system", "content": combined_system_message}
                    )
                else:
                    # Update existing system message
                    message_history[0]["content"] = combined_system_message

            result = await self.agent.run(
                request.message,
                message_history=message_history,
            )
            assistant_output = result.output

        # Append latest turn to history so caller can persist it
        updated_history: List[Dict[str, Any]] = history.copy() if history else []
        now_iso = datetime.datetime.utcnow().isoformat()
        updated_history.append(
            {
                "role": "user",
                "content": request.message,
                "timestamp": now_iso,
            }
        )
        updated_history.append(
            {
                "role": "assistant",
                "content": assistant_output,
                "timestamp": now_iso,
            }
        )

        # Merge all metadata/context updates so caller can persist them
        metadata: Dict[str, Any] = {
            "model": self.config.model,
            "history": updated_history,
        }

        context_updates_combined: Dict[str, Any] = {}
        if shared_context:
            context_updates_combined.update(shared_context)
        # context_updates are fine-grained keys like user_name, preferred_language
        context_updates_combined.update(context_updates)
        # prefs_updates can be a higher-level aggregation under user_prefs
        context_updates_combined.update(prefs_updates)

        return AgentResponse(
            session_id=request.session_id,
            output=assistant_output,
            metadata=metadata,
            context_updates=context_updates_combined,
        )

    def get_capabilities(self) -> list[str]:
        return ["chat", "conversation", "qa"]
