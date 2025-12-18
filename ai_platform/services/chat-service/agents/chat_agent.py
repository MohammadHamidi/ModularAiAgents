import datetime
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

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
    tool_results: Dict[str, Any] = field(default_factory=dict)  # Results from tool calls


class ChatAgent(BaseAgent):
    """Chat agent with AI-powered tool for extracting user information."""

    def __init__(self, base_config: AgentConfig, context_manager, agent_config: FullAgentConfig, custom_tools: List[Any] = None):
        """
        Initialize chat agent with full configuration.

        Args:
            base_config: Base agent config (for compatibility)
            context_manager: Context manager for storing data
            agent_config: Full agent configuration from YAML
            custom_tools: List of custom Tool objects for this agent
        """
        super().__init__(base_config, context_manager)
        self.agent_config = agent_config
        self.field_map = agent_config.build_field_map()
        self.custom_tools = custom_tools or []

    def _build_dynamic_tool_description(self) -> str:
        """Build tool description dynamically based on enabled fields."""
        enabled_fields = self.agent_config.get_enabled_fields()
        
        # Build field list for documentation
        field_lines = []
        field_names = []
        for f in enabled_fields:
            field_names.append(f.field_name)
            example = f.examples[0] if f.examples else f"<{f.field_name}>"
            aliases_str = f" (aliases: {', '.join(f.aliases)})" if f.aliases else ""
            field_lines.append(f"- {f.description}{aliases_str} → field_name=\"{f.field_name}\", field_value=\"{example}\"")
        
        return f'''MANDATORY: Extract and save user information from messages.

YOU MUST call this tool whenever the user mentions ANY of these:
{chr(10).join(field_lines)}

Examples:
- User says "من علی هستم" → call save_user_info(field_name="name", field_value="علی")
- User says "از شیراز هستم" → call save_user_info(field_name="location", field_value="شیراز")
- User says "25 سالمه" → call save_user_info(field_name="age", field_value="25")

IMPORTANT: Call this tool SILENTLY - never tell the user you're saving info.
You can call this multiple times in one response for multiple pieces of info.

Args:
    field_name: One of: {', '.join(field_names)}
    field_value: The extracted value from user's message

Returns:
    Confirmation (internal only - don't show to user)
'''

    async def initialize(self, http_client: httpx.AsyncClient | None = None):
        # Use provided http_client or create a new one
        client = http_client or create_litellm_compatible_client()
        
        # Store the client reference for reinitialization
        self._stored_http_client = client

        await self._build_agent(client)

        # Only store http_client if we created it ourselves
        if http_client is None:
            self.http_client = client
        else:
            self.http_client = None
    
    async def _build_agent(self, client: httpx.AsyncClient):
        """Build/rebuild the agent with current field configuration."""
        openai_client = AsyncOpenAI(
            api_key=self.config.extra.get("api_key"),
            base_url=self.config.extra.get("base_url"),
            http_client=client,
        )
        provider = OpenAIProvider(openai_client=openai_client)
        model = OpenAIChatModel(self.config.model, provider=provider)

        # Build dynamic tool description BEFORE creating agent
        tool_doc = self._build_dynamic_tool_description()
        
        # Create the tool function with dynamic docstring
        async def save_user_info_impl(
            ctx: RunContext[ChatDependencies],
            field_name: str,
            field_value: str,
        ) -> str:
            return await self._handle_save_user_info(ctx, field_name, field_value)
        
        # Set docstring BEFORE registration
        save_user_info_impl.__doc__ = tool_doc
        save_user_info_impl.__name__ = "save_user_info"

        # Create agent with tool for saving user information
        self.agent = Agent(
            model,
            deps_type=ChatDependencies,
            system_prompt="",  # Will be set dynamically in process()
        )

        # Register the save_user_info tool
        self.agent.tool(save_user_info_impl)
        
        # Register custom tools for this persona
        await self._register_custom_tools()
    
    async def reinitialize_tools(self):
        """Reinitialize the agent with updated field configuration."""
        if hasattr(self, '_stored_http_client'):
            await self._build_agent(self._stored_http_client)
            return True
        return False
    
    async def _register_custom_tools(self):
        """Register custom tools for this persona."""
        for tool in self.custom_tools:
            if not tool.enabled:
                continue
            
            # Register each tool with explicit parameter handling
            self._register_tool_explicit(tool)
    
    def _register_tool_explicit(self, tool):
        """Register a tool with explicit parameter definitions."""
        tool_ref = tool  # Capture for closure
        params = tool.parameters.get("properties", {})
        
        # Build comprehensive docstring
        doc_parts = [tool.description, "\n\nParameters:"]
        for param_name, param_info in params.items():
            param_desc = param_info.get("description", "No description")
            doc_parts.append(f"    {param_name}: {param_desc}")
        full_doc = "\n".join(doc_parts)
        
        # Create wrapper based on tool type (handles common tool patterns)
        if tool.name == "calculator":
            async def calc_tool(ctx: RunContext[ChatDependencies], expression: str) -> str:
                """Perform mathematical calculations."""
                result = await tool_ref.execute(expression=expression)
                ctx.deps.tool_results[tool_ref.name] = result
                return result
            calc_tool.__doc__ = full_doc
            self.agent.tool(calc_tool)
            
        elif tool.name == "knowledge_base_search":
            async def kb_tool(ctx: RunContext[ChatDependencies], query: str, category: str = None) -> str:
                """Search the knowledge base."""
                result = await tool_ref.execute(query=query, category=category)
                ctx.deps.tool_results[tool_ref.name] = result
                return result
            kb_tool.__doc__ = full_doc
            self.agent.tool(kb_tool)
            
        elif tool.name == "get_weather":
            async def weather_tool(ctx: RunContext[ChatDependencies], city: str) -> str:
                """Get weather for a city."""
                result = await tool_ref.execute(city=city)
                ctx.deps.tool_results[tool_ref.name] = result
                return result
            weather_tool.__doc__ = full_doc
            self.agent.tool(weather_tool)
            
        elif tool.name == "get_learning_resource":
            async def learning_tool(ctx: RunContext[ChatDependencies], topic: str, level: str = "beginner") -> str:
                """Get learning resources."""
                result = await tool_ref.execute(topic=topic, level=level)
                ctx.deps.tool_results[tool_ref.name] = result
                return result
            learning_tool.__doc__ = full_doc
            self.agent.tool(learning_tool)
            
        elif tool.name == "web_search":
            async def web_tool(ctx: RunContext[ChatDependencies], query: str) -> str:
                """Search the web."""
                result = await tool_ref.execute(query=query)
                ctx.deps.tool_results[tool_ref.name] = result
                return result
            web_tool.__doc__ = full_doc
            self.agent.tool(web_tool)
            
        elif tool.name == "get_company_info":
            async def company_tool(ctx: RunContext[ChatDependencies], company_name: str, info_type: str = "overview") -> str:
                """Get company information."""
                result = await tool_ref.execute(company_name=company_name, info_type=info_type)
                ctx.deps.tool_results[tool_ref.name] = result
                return result
            company_tool.__doc__ = full_doc
            self.agent.tool(company_tool)
            
        else:
            # Generic fallback - single string query parameter
            async def generic_tool(ctx: RunContext[ChatDependencies], query: str) -> str:
                """Execute tool with query."""
                result = await tool_ref.execute(query=query)
                ctx.deps.tool_results[tool_ref.name] = result
                return result
            generic_tool.__name__ = tool.name
            generic_tool.__doc__ = full_doc
            self.agent.tool(generic_tool)
    
    def add_custom_tool(self, tool):
        """Add a custom tool to this agent."""
        self.custom_tools.append(tool)

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

    def _build_context_summary(self, user_info: Dict[str, Any]) -> str:
        """Build a brief context summary for injecting into user message."""
        if not user_info:
            return ""
        
        parts = []
        
        # Build field labels dynamically from config
        field_labels = {}
        for field_config in self.agent_config.user_data_fields:
            # Use field_labels from context_display config if available
            label = self.agent_config.context_display.get('field_labels', {}).get(
                field_config.normalized_name,
                field_config.field_name  # Fallback to field_name
            )
            field_labels[field_config.normalized_name] = label
        
        for key, data in user_info.items():
            value = data.get('value') if isinstance(data, dict) else data
            if value:
                label = field_labels.get(key, key)
                if isinstance(value, list):
                    value = '، '.join(str(v) for v in value)
                parts.append(f"{label}: {value}")
        
        return '؛ '.join(parts) if parts else ""

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

    def _get_dynamic_field_instructions(self) -> str:
        """Build dynamic field extraction instructions based on enabled fields."""
        enabled_fields = self.agent_config.get_enabled_fields()
        lines = ["🔧 فیلدهای قابل ذخیره (از save_user_info استفاده کن):"]
        for f in enabled_fields:
            aliases_hint = f" یا {', '.join(f.aliases)}" if f.aliases else ""
            lines.append(f"  - {f.field_name}{aliases_hint} → save_user_info(field_name=\"{f.field_name}\", ...)")
        return "\n".join(lines)

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
        
        # Add dynamic field instructions (so agent knows all available fields)
        parts.append(self._get_dynamic_field_instructions())

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

        # Build user message with context prepended for better recall
        # Use a format that's clearly internal and won't be repeated by the model
        user_message = request.message
        if shared_context:
            context_summary = self._build_context_summary(shared_context)
            if context_summary:
                # Format: Hidden context that model should use but NEVER repeat
                user_message = f"<internal_context>{context_summary}</internal_context>\n{request.message}"
        
        # Run the agent with tool support
        result = await self.agent.run(
            user_message,
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
