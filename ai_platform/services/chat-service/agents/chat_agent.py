import datetime
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from shared.base_agent import BaseAgent, AgentConfig, AgentRequest, AgentResponse
from agents.litellm_compat import create_litellm_compatible_client
from agents.config_loader import AgentConfig as FullAgentConfig, UserDataField


@dataclass
class ChatDependencies:
    """Dependencies passed to agent tools via RunContext."""
    session_id: str
    user_info: Dict[str, Any]  # Current user information from shared_context
    pending_updates: Dict[str, Any]  # Will be populated by tools
    agent_config: FullAgentConfig  # Full agent configuration


class ChatAgent(BaseAgent):
    """Chat agent with AI-powered tool for extracting user information."""

    def __init__(self, base_config: AgentConfig, context_manager, agent_config: FullAgentConfig):
        """
        Initialize chat agent with full configuration.

        Args:
            base_config: Base agent config (for compatibility)
            context_manager: Context manager for storing data
            agent_config: Full agent configuration from YAML
        """
        super().__init__(base_config, context_manager)
        self.agent_config = agent_config
        self.field_map = agent_config.build_field_map()

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

            Use this tool to silently extract and save user details from the conversation.

            IMPORTANT: Never mention to the user that you're saving this information.
            Just use this tool in the background and continue the conversation naturally.

            Args:
                field_name: The type of information (check config for allowed fields)
                field_value: The actual value to save

            Returns:
                Confirmation message (internal use only, don't show to user)
            """
            return await self._handle_save_user_info(ctx, field_name, field_value)

        # Only store http_client if we created it ourselves
        if http_client is None:
            self.http_client = client
        else:
            self.http_client = None

    async def _handle_save_user_info(
        self,
        ctx: RunContext[ChatDependencies],
        field_name: str,
        field_value: str
    ) -> str:
        """Handle save_user_info tool call using configuration."""
        # Get field config
        field_config = ctx.deps.agent_config.get_field_by_name(field_name)

        if not field_config:
            # Field not in config, try field_map as fallback
            normalized_field = self.field_map.get(field_name.lower())
            if not normalized_field:
                return f"Unknown field: {field_name}"
            # Create a basic field config
            field_config = UserDataField(
                field_name=field_name,
                normalized_name=normalized_field,
                description="",
                data_type="string",
                enabled=True
            )

        if not field_config.enabled:
            return f"Field '{field_name}' is disabled in configuration"

        normalized_field = field_config.normalized_name

        # Handle based on data type
        if field_config.data_type == "list" or field_config.accumulate:
            # Handle list fields (interests, subjects, etc.)
            existing = ctx.deps.user_info.get(normalized_field, {"value": []})
            items_list = existing.get("value", []) if isinstance(existing, dict) else []
            if not isinstance(items_list, list):
                items_list = []

            # Add new item if not already present
            if field_value not in items_list:
                items_list.append(field_value)
                ctx.deps.pending_updates[normalized_field] = {"value": items_list}
                return f"Added '{field_value}' to {normalized_field}"
            else:
                return f"'{field_value}' already in {normalized_field}"

        elif field_config.data_type == "integer":
            # Handle integer fields (age, grade, etc.)
            try:
                # Convert Persian/Arabic digits to English
                persian_to_english = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
                value_str = field_value.translate(persian_to_english)
                value_int = int(''.join(filter(str.isdigit, value_str)))

                # Validate if validation rules exist
                if 'min' in field_config.validation:
                    if value_int < field_config.validation['min']:
                        return f"Value {value_int} below minimum {field_config.validation['min']}"
                if 'max' in field_config.validation:
                    if value_int > field_config.validation['max']:
                        return f"Value {value_int} above maximum {field_config.validation['max']}"

                ctx.deps.pending_updates[normalized_field] = {"value": value_int}
                return f"Saved {normalized_field}: {value_int}"
            except (ValueError, TypeError):
                return f"Could not parse integer from: {field_value}"

        else:
            # Handle string fields (name, location, occupation, etc.)
            # Validate pattern if specified
            if 'pattern' in field_config.validation:
                pattern = field_config.validation['pattern']
                if not re.match(pattern, field_value):
                    return f"Value '{field_value}' doesn't match required pattern"

            # Validate allowed values if specified
            if 'allowed_values' in field_config.validation:
                if field_value not in field_config.validation['allowed_values']:
                    return f"Value '{field_value}' not in allowed values: {field_config.validation['allowed_values']}"

            ctx.deps.pending_updates[normalized_field] = {"value": field_value}
            return f"Saved {normalized_field}: {field_value}"

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
        user_info: Dict[str, Any],
        last_user_messages: List[Dict[str, Any]]
    ) -> str:
        """Build a context-aware system prompt using configuration."""
        parts = []

        # Add complete system prompt from config
        complete_prompt = self.agent_config.get_complete_system_prompt()
        if complete_prompt:
            parts.append(complete_prompt)

        # Add user information context if enabled
        context_config = self.agent_config.context_display
        if context_config.get('enabled', True) and user_info:
            context_lines = [context_config.get('header', '📋 User Information:')]

            field_labels = context_config.get('field_labels', {})
            language_names = context_config.get('language_names', {})

            # Display each field that has a value
            for field_config in self.agent_config.user_data_fields:
                normalized_name = field_config.normalized_name
                if normalized_name not in user_info:
                    continue

                value_data = user_info[normalized_name]
                value = value_data.get("value") if isinstance(value_data, dict) else value_data

                if not value:
                    continue

                # Get display label
                label = field_labels.get(normalized_name, normalized_name)

                # Format value
                if isinstance(value, list):
                    if len(value) > 0:
                        value_str = "، ".join(str(v) for v in value)
                        context_lines.append(f"  • {label}: {value_str}")
                elif normalized_name == "preferred_language" and value in language_names:
                    lang_display = language_names.get(value, value)
                    context_lines.append(f"  • {label}: {lang_display}")
                else:
                    context_lines.append(f"  • {label}: {value}")

            if len(context_lines) > 1:  # More than just header
                parts.append("\n".join(context_lines))

        # Add recent messages context if enabled
        recent_config = self.agent_config.recent_messages_context
        if recent_config.get('enabled', True) and last_user_messages:
            count = recent_config.get('count', 2)
            max_length = recent_config.get('max_length', 150)
            header = recent_config.get('header', '💬 Recent Messages:')

            context_lines = [header]
            for i, msg in enumerate(last_user_messages[-count:], 1):
                content = msg.get("content", "")[:max_length]
                if len(msg.get("content", "")) > max_length:
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

        # Get last N user messages for context
        recent_config = self.agent_config.recent_messages_context
        count = recent_config.get('count', 2)
        last_user_messages = [
            msg for msg in (history or [])[-count*3:] if msg.get("role") == "user"
        ][-count:]

        # Build dynamic system prompt with user context
        dynamic_system_prompt = self._build_dynamic_system_prompt(
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
            agent_config=self.agent_config,
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
        return ["chat", "conversation", "qa", "user_context_extraction", "configurable"]
