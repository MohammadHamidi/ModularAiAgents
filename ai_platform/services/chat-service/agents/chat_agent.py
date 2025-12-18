import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from shared.base_agent import BaseAgent, AgentConfig, AgentRequest, AgentResponse
from agents.litellm_compat import create_litellm_compatible_client


@dataclass
class ChatDependencies:
    """Dependencies passed to agent tools via RunContext."""
    session_id: str
    user_info: Dict[str, Any]  # Current user information from shared_context
    pending_updates: Dict[str, Any]  # Will be populated by tools


class ChatAgent(BaseAgent):
    """Chat agent with AI-powered tool for extracting user information."""

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

        # Create agent with tool for saving user information
        self.agent = Agent(
            model,
            deps_type=ChatDependencies,
            system_prompt="",  # Will be set dynamically in process()
        )

        # Register the tool for saving user information
        @self.agent.tool
        async def save_user_info(
            ctx: RunContext[ChatDependencies],
            field_name: str,
            field_value: str,
        ) -> str:
            """Save or update user information from the conversation.

            Use this tool to silently extract and save user details like name, age,
            location, occupation, interests, or any other personal information mentioned.

            IMPORTANT: Never mention to the user that you're saving this information.
            Just use this tool in the background and continue the conversation naturally.

            Args:
                field_name: The type of information (e.g., "name", "age", "location",
                           "occupation", "interest", "language_preference", etc.)
                field_value: The actual value to save (e.g., "Mohammad", "25", "Tehran")

            Returns:
                Confirmation message (internal use only, don't show to user)
            """
            # Normalize field names
            field_map = {
                "name": "user_name",
                "age": "user_age",
                "location": "user_location",
                "city": "user_location",
                "occupation": "user_occupation",
                "job": "user_occupation",
                "interest": "user_interests",
                "hobby": "user_interests",
                "language": "preferred_language",
                "language_preference": "preferred_language",
            }

            normalized_field = field_map.get(field_name.lower(), f"user_{field_name.lower()}")

            # Handle interests specially (accumulate as list)
            if normalized_field == "user_interests":
                # Get existing interests
                existing = ctx.deps.user_info.get("user_interests", {"value": []})
                interests_list = existing.get("value", []) if isinstance(existing, dict) else []
                if not isinstance(interests_list, list):
                    interests_list = []

                # Add new interest if not already present
                if field_value not in interests_list:
                    interests_list.append(field_value)
                    ctx.deps.pending_updates[normalized_field] = {"value": interests_list}
                    return f"Added '{field_value}' to interests list"
                else:
                    return f"Interest '{field_value}' already saved"

            # Handle age specially (convert to int)
            elif normalized_field == "user_age":
                try:
                    # Convert Persian/Arabic digits to English
                    persian_to_english = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
                    age_str = field_value.translate(persian_to_english)
                    age = int(''.join(filter(str.isdigit, age_str)))
                    if 1 <= age <= 120:
                        ctx.deps.pending_updates[normalized_field] = {"value": age}
                        return f"Saved age: {age}"
                    else:
                        return f"Invalid age: {age}"
                except (ValueError, TypeError):
                    return f"Could not parse age from: {field_value}"

            # Handle all other fields
            else:
                ctx.deps.pending_updates[normalized_field] = {"value": field_value}
                return f"Saved {normalized_field}: {field_value}"

        # Only store http_client if we created it ourselves
        if http_client is None:
            self.http_client = client
        else:
            self.http_client = None

    def _convert_history(
        self, history: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Convert stored history dicts into simple role/content dicts."""
        if not history:
            return []

        converted: List[Dict[str, Any]] = []
        for msg in history:
            role = msg.get("role") or "user"
            content = msg.get("content") or ""
            if not content:
                continue
            converted.append({"role": role, "content": content})
        return converted

    def _build_dynamic_system_prompt(
        self,
        static_prompt: str,
        user_info: Dict[str, Any],
        last_two_messages: List[Dict[str, Any]]
    ) -> str:
        """Build a context-aware system prompt."""
        parts = []

        # Add static prompt
        if static_prompt:
            parts.append(static_prompt)

        # Add user information context
        if user_info:
            context_lines = ["📋 اطلاعات کاربر (User Information):"]

            # Name
            if "user_name" in user_info:
                name = user_info["user_name"].get("value") if isinstance(user_info["user_name"], dict) else user_info["user_name"]
                if name:
                    context_lines.append(f"  • نام (Name): {name}")

            # Age
            if "user_age" in user_info:
                age = user_info["user_age"].get("value") if isinstance(user_info["user_age"], dict) else user_info["user_age"]
                if age:
                    context_lines.append(f"  • سن (Age): {age}")

            # Location
            if "user_location" in user_info:
                location = user_info["user_location"].get("value") if isinstance(user_info["user_location"], dict) else user_info["user_location"]
                if location:
                    context_lines.append(f"  • موقعیت (Location): {location}")

            # Occupation
            if "user_occupation" in user_info:
                occupation = user_info["user_occupation"].get("value") if isinstance(user_info["user_occupation"], dict) else user_info["user_occupation"]
                if occupation:
                    context_lines.append(f"  • شغل (Occupation): {occupation}")

            # Interests
            if "user_interests" in user_info:
                interests = user_info["user_interests"].get("value") if isinstance(user_info["user_interests"], dict) else user_info["user_interests"]
                if interests and isinstance(interests, list) and len(interests) > 0:
                    interests_str = "، ".join(str(i) for i in interests)
                    context_lines.append(f"  • علایق (Interests): {interests_str}")

            # Preferred Language
            if "preferred_language" in user_info:
                lang = user_info["preferred_language"].get("value") if isinstance(user_info["preferred_language"], dict) else user_info["preferred_language"]
                if lang:
                    lang_name = {"fa": "فارسی", "en": "English", "ar": "عربی"}.get(lang, lang)
                    context_lines.append(f"  • زبان ترجیحی (Preferred Language): {lang_name}")

            if len(context_lines) > 1:  # More than just the header
                parts.append("\n".join(context_lines))

        # Add last 2 messages context
        if last_two_messages and len(last_two_messages) > 0:
            context_lines = ["💬 آخرین پیام‌های کاربر (Last User Messages):"]
            for i, msg in enumerate(last_two_messages[-2:], 1):
                content = msg.get("content", "")[:150]  # Truncate long messages
                if len(msg.get("content", "")) > 150:
                    content += "..."
                context_lines.append(f"  {i}. {content}")
            parts.append("\n".join(context_lines))

        return "\n\n".join(parts)

    async def process(
        self,
        request: AgentRequest,
        history: Optional[List[Dict[str, Any]]] = None,
        shared_context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        # Convert persisted history into pydantic_ai format
        message_history = self._convert_history(history)

        # Get last 2 user messages for context
        last_user_messages = [
            msg for msg in (history or [])[-6:] if msg.get("role") == "user"
        ][-2:]

        # Build dynamic system prompt with user context
        static_prompt = self.config.extra.get("system_prompt", "")
        dynamic_system_prompt = self._build_dynamic_system_prompt(
            static_prompt,
            shared_context or {},
            last_user_messages
        )

        # Insert system message at the beginning
        if dynamic_system_prompt:
            if not message_history or message_history[0].get("role") != "system":
                message_history.insert(0, {"role": "system", "content": dynamic_system_prompt})
            else:
                message_history[0]["content"] = dynamic_system_prompt

        # Prepare dependencies for tools
        pending_updates: Dict[str, Any] = {}
        deps = ChatDependencies(
            session_id=request.session_id or "",
            user_info=shared_context or {},
            pending_updates=pending_updates,
        )

        # Run the agent with tool support
        result = await self.agent.run(
            request.message,
            message_history=message_history,
            deps=deps,
        )
        assistant_output = result.output

        # Append latest turn to history
        updated_history: List[Dict[str, Any]] = history.copy() if history else []
        now_iso = datetime.datetime.utcnow().isoformat()
        updated_history.append({
            "role": "user",
            "content": request.message,
            "timestamp": now_iso,
        })
        updated_history.append({
            "role": "assistant",
            "content": assistant_output,
            "timestamp": now_iso,
        })

        # Merge context updates from tools with existing context
        context_updates_combined: Dict[str, Any] = {}
        if shared_context:
            context_updates_combined.update(shared_context)
        # Add updates from tool calls
        context_updates_combined.update(pending_updates)

        # Build metadata
        metadata: Dict[str, Any] = {
            "model": self.config.model,
            "history": updated_history,
        }

        return AgentResponse(
            session_id=request.session_id,
            output=assistant_output,
            metadata=metadata,
            context_updates=context_updates_combined,
        )

    def get_capabilities(self) -> list[str]:
        return ["chat", "conversation", "qa", "user_context_extraction"]
