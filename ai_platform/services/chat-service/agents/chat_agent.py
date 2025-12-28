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
            
        elif tool.name == "knowledge_base_query":
            async def kb_tool(
            ctx: RunContext[ChatDependencies],
                query: str,
                mode: str = "mix",
                include_references: bool = True,
                include_chunk_content: bool = False,
                response_type: str = "Multiple Paragraphs",
                top_k: int = 10,
                chunk_top_k: int = 8,
                max_total_tokens: int = 6000,
                conversation_history: list = None
        ) -> str:
                """Query the LightRAG knowledge base."""
                result = await tool_ref.execute(
                    query=query,
                    mode=mode,
                    include_references=include_references,
                    include_chunk_content=include_chunk_content,
                    response_type=response_type,
                    top_k=top_k,
                    chunk_top_k=chunk_top_k,
                    max_total_tokens=max_total_tokens,
                    conversation_history=conversation_history
                )
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
            
        elif tool.name == "query_konesh":
            async def konesh_tool(
                ctx: RunContext[ChatDependencies],
                query: str,
                category: Optional[str] = None,
                is_primary: Optional[bool] = None,
                limit: int = 10
            ) -> str:
                """Query the کنش (Quranic Actions) database."""
                result = await tool_ref.execute(
                    query=query,
                    category=category,
                    is_primary=is_primary,
                    limit=limit
                )
                ctx.deps.tool_results[tool_ref.name] = result
                return result
            konesh_tool.__doc__ = full_doc
            self.agent.tool(konesh_tool)
            
        elif tool.name == "route_to_agent":
            # AgentRouterTool uses run() method, not execute()
            async def route_tool(
                ctx: RunContext[ChatDependencies],
                agent_key: str,
                user_message: str,
                session_id: Optional[str] = None
            ) -> str:
                """Route a user request to a specialist agent."""
                # Use run() method for AgentRouterTool
                if hasattr(tool_ref, 'run'):
                    result = await tool_ref.run(
                        agent_key=agent_key,
                        user_message=user_message,
                        session_id=session_id or ctx.deps.session_id
                    )
                else:
                    # Fallback to execute if available
                    result = await tool_ref.execute(
                        agent_key=agent_key,
                        user_message=user_message,
                        session_id=session_id or ctx.deps.session_id
                    )
                ctx.deps.tool_results[tool_ref.name] = result
                return result
            route_tool.__doc__ = full_doc
            self.agent.tool(route_tool)
            
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
    
    def _remove_unwanted_extra_text(self, output: str) -> str:
        """
        Remove unwanted extra explanatory text/paragraphs that LLM sometimes adds.
        These are generic phrases that don't add value and should be removed.
        """
        import re
        
        # Find the suggestions section to preserve it
        suggestions_match = re.search(r'(پیشنهادهای بعدی:|Next actions:)[\s\S]*$', output, re.IGNORECASE)
        suggestions_section = suggestions_match.group(0) if suggestions_match else None
        main_content = output[:suggestions_match.start()] if suggestions_match else output
        
        # Patterns of unwanted text that should be removed (before suggestions section)
        unwanted_patterns = [
            # Generic introductory phrases
            r'پرسش کلیدی و مهمی مطرح کردید[^\n]*',
            r'پرسش[^\n]*مهمی[^\n]*مطرح[^\n]*',
            r'بر اساس تجربه نهضت[^\n]*',
            r'برای اینکه صحبت شما[^\n]*',
            r'این یک سوال مهم است[^\n]*',
            r'لازم است محتوای انتخابی شما[^\n]*',
            r'اصول تربیت[^\n]*',
            r'موارد زیر می‌توانند[^\n]*',
            # New patterns from user feedback
            r'بسیار عالی[^\n]*',
            r'سؤالی که مطرح کرده‌اید[^\n]*',
            r'یک دغدغه‌ی مهم[^\n]*',
            r'با توجه به نتایج جستجو[^\n]*',
            r'رویکردهای کلی را معرفی می‌کند[^\n]*',
            r'برای ارتباط موثر[^\n]*',
            r'باید روی[^\n]*تمرکز کنید[^\n]*',
            # Formal meta-commentary patterns
            r'برای پاسخ به این سؤال[^\n]*',
            r'ابتدا بستر و مخاطب را[^\n]*',
            r'برای رساندن پیام[^\n]*',
            r'نه تنها چه چیزی بگویید[^\n]*',
            r'بلکه چگونه بگویید[^\n]*',
            r'اهمیت حیاتی دارد[^\n]*',
            r'اصل محوری[^\n]*',
            r'محتوای کانونی[^\n]*',
            r'روش‌های مؤثر[^\n]*',
            # Remove entire paragraphs that start with these phrases
            r'\n\s*پرسش[^\n]*مهم[^\n]*مطرح[^\n]*\s*\n+',
            r'\n\s*بر اساس تجربه[^\n]*\s*\n+',
            r'\n\s*برای اینکه[^\n]*تأثیرگذار[^\n]*\s*\n+',
            r'\n\s*لازم است[^\n]*\s*\n+',
            r'\n\s*بسیار عالی[^\n]*\s*\n+',
            r'\n\s*سؤالی که مطرح کرده‌اید[^\n]*\s*\n+',
            r'\n\s*یک دغدغه‌ی مهم[^\n]*\s*\n+',
            r'\n\s*با توجه به نتایج[^\n]*\s*\n+',
            r'\n\s*برای پاسخ به این سؤال[^\n]*\s*\n+',
            r'\n\s*ابتدا بستر و مخاطب[^\n]*\s*\n+',
            # Remove verbose introductory sentences
            r'^بسیار عالی[^\n]*\n+',
            r'^سؤالی که مطرح کرده‌اید[^\n]*\n+',
            r'^یک دغدغه‌ی مهم[^\n]*\n+',
            r'^برای پاسخ به این سؤال[^\n]*\n+',
        ]
        
        cleaned = main_content
        for pattern in unwanted_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)
        
        # Remove multiple consecutive newlines (clean up spacing)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        
        # Trim whitespace
        cleaned = cleaned.strip()
        
        # Reattach suggestions section if it existed
        if suggestions_section:
            cleaned = cleaned + '\n\n' + suggestions_section
        
        return cleaned
    
    def _validate_konesh_scope(self, user_message: str, output: str) -> str:
        """
        Validate that konesh_expert responses are within scope.
        If out of scope detected, return rejection message.
        """
        # Only apply to konesh_expert agent
        if not hasattr(self, 'agent_config') or not self.agent_config:
            return output
        
        agent_name = getattr(self.agent_config, 'agent_name', '')
        if agent_name != "متخصص کنش‌های قرآنی سفیران آیه‌ها":
            return output  # Only applies to konesh_expert
        
        # Check if query contains konesh-related keywords
        konesh_keywords = ["کنش", "محفل", "صبحگاه", "فضاسازی", "مسجد", "مدرسه", "خانه"]
        query_lower = user_message.lower()
        
        has_konesh_context = any(kw in query_lower for kw in konesh_keywords)
        
        # If no konesh context, return rejection
        if not has_konesh_context:
            return """من متخصص کنش‌های قرآنی سفیران آیه‌ها هستم و فقط می‌تونم در مورد انتخاب، طراحی و اجرای کنش‌ها کمکت کنم.

اگه می‌خوای برای این موقعیت یه کنش یا محفل قرآنی برگزار کنی، خوشحال می‌شم راهنماییت کنم! 😊

پیشنهادهای بعدی:
1) بگو چه بستری در اختیار داری (خانه، مدرسه، مسجد، فضای مجازی)
2) بگو نقشت چیه (معلم، دانش‌آموز، والد، مبلغ)"""
        
        return output
    
    def _convert_suggestions_to_user_perspective(self, output: str) -> str:
        """Convert any AI-perspective suggestions in the output to user perspective."""
        # Find the suggestions section
        suggestions_match = re.search(r'پیشنهادهای بعدی:\s*([\s\S]*?)(?:\n\n|$)', output)
        if not suggestions_match:
            return output
        
        suggestions_text = suggestions_match.group(1)
        original_suggestions = suggestions_text.strip()
        
        # Split into individual suggestions (numbered)
        suggestions = re.split(r'\n\s*\d+\)\s*', original_suggestions)
        suggestions = [s.strip() for s in suggestions if s.strip()]
        
        # Convert each suggestion
        converted_suggestions = []
        for suggestion in suggestions:
            converted = self._convert_to_user_perspective(suggestion)
            converted_suggestions.append(converted)
        
        # Rebuild the suggestions section
        new_suggestions_text = "\n".join([f"{i}) {s}" for i, s in enumerate(converted_suggestions, 1)])
        
        # Replace in output
        new_output = output[:suggestions_match.start(1)] + new_suggestions_text + output[suggestions_match.end(1):]
        
        return new_output
    
    def _is_greeting(self, message: str) -> bool:
        """Check if message is a simple greeting that doesn't need KB query."""
        greetings = ["سلام", "خداحافظ", "خدا حافظ", "hi", "hello", "bye", "goodbye", "صبح بخیر", "عصر بخیر", "شب بخیر"]
        message_lower = message.strip().lower()
        # Check if message is exactly a greeting or starts with one
        if message_lower in greetings:
            return True
        # Check if message starts with a greeting followed by punctuation or space
        for greeting in greetings:
            if message_lower.startswith(greeting) and len(message_lower) <= len(greeting) + 2:
                return True
        return False

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
        
        # Add KB instruction for ALL questions (except greetings)
        # KB-first approach: Always query KB first for every question
        if not self._is_greeting(user_message):
            kb_instruction = "\n<system_note>این سوال کاربر است. حتماً ابتدا از knowledge_base_query استفاده کن و سپس بر اساس نتایج KB پاسخ بده. اگر KB نتیجه نداد، آنگاه پاسخ عمومی بده.</system_note>"
            user_message = user_message + kb_instruction
        
        if shared_context:
            context_summary = self._build_context_summary(shared_context)
            if context_summary:
                # Format: Hidden context that model should use but NEVER repeat
                user_message = f"<internal_context>{context_summary}</internal_context>\n{user_message}"

        # Run the agent with tool support
        result = await self.agent.run(
            user_message,
            message_history=message_history,
            deps=deps,
        )
        assistant_output = result.output
        
        # Post-process: Validate konesh scope (must be before other post-processing)
        assistant_output = self._validate_konesh_scope(request.message, assistant_output)
        
        # Post-process: Remove unwanted extra text/paragraphs
        assistant_output = self._remove_unwanted_extra_text(assistant_output)
        
        # Post-process: Convert AI-perspective suggestions to user perspective
        assistant_output = self._convert_suggestions_to_user_perspective(assistant_output)
        
        # Post-process: Ensure suggestions section is always present
        assistant_output = self._ensure_suggestions_section(
            assistant_output,
            deps.tool_results,
            request.message
        )

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

    def _ensure_suggestions_section(
        self,
        output: str,
        tool_results: Dict[str, Any],
        user_message: str
    ) -> str:
        """
        Ensure the output always includes a suggestions section.
        If missing, generate contextual suggestions based on KB content or user query.
        """
        # Check if suggestions section already exists
        suggestions_patterns = [
            r"پیشنهادهای بعدی:",
            r"Next actions:",
            r"پیشنهادهای بعدی\s*:",
            r"Next actions\s*:",
        ]
        
        has_suggestions = any(re.search(pattern, output, re.IGNORECASE) for pattern in suggestions_patterns)
        
        if has_suggestions:
            return output
        
        # Generate contextual suggestions
        suggestions = []
        
        # Check if KB was queried
        kb_result = tool_results.get("knowledge_base_query")
        if kb_result:
            # Extract concepts from KB result to generate contextual suggestions
            kb_text = str(kb_result).lower()
            
            # Extract specific topics mentioned in KB
            mentioned_topics = []
            if "کنش" in kb_text:
                # Extract specific action types mentioned
                if "مدرسه" in kb_text:
                    mentioned_topics.append("کنش‌های مدرسه")
                if "خانه" in kb_text or "خانگی" in kb_text:
                    mentioned_topics.append("کنش‌های خانه")
                if "مسجد" in kb_text:
                    mentioned_topics.append("کنش‌های مسجد")
                if "فضای مجازی" in kb_text or "مجازی" in kb_text:
                    mentioned_topics.append("کنش‌های فضای مجازی")
            
            # Generate specific suggestions based on what was mentioned (from user's perspective)
            if mentioned_topics:
                # Suggest topics that weren't mentioned (user perspective)
                all_topics = ["کنش‌های مدرسه", "کنش‌های خانه", "کنش‌های مسجد", "کنش‌های فضای مجازی"]
                unmentioned = [t for t in all_topics if t not in mentioned_topics]
                if unmentioned:
                    suggestions.append(f"درباره {unmentioned[0]} بیشتر بدانم")
            
            # If actions were mentioned, suggest starting one (user perspective)
            if "کنش" in kb_text:
                suggestions.append("چطور یک کنش رو شروع کنم؟")
            
            # If verses were mentioned, suggest related verses (user perspective)
            if "آیه" in kb_text:
                # Try to extract verse numbers if mentioned
                verse_numbers = re.findall(r'آیه\s*(\d+)', kb_text)
                if verse_numbers:
                    suggestions.append(f"درباره آیه {verse_numbers[0]} بیشتر بدانم")
                else:
                    suggestions.append("آیه‌های مرتبط")
            
            # If ambassador role was mentioned, suggest action details (user perspective)
            if "سفیر" in kb_text:
                suggestions.append("نحوه انجام کنش‌ها به عنوان سفیر")
            
            # Generic KB-based suggestions if we don't have enough (user perspective)
            if len(suggestions) < 2:
                # Extract any key terms from KB
                key_terms = []
                if "محفل" in kb_text:
                    key_terms.append("محافل")
                if "کلیپ" in kb_text:
                    key_terms.append("کلیپ آیه")
                if "گزارش" in kb_text:
                    key_terms.append("ثبت گزارش کنش")
                
                if key_terms:
                    suggestions.append(f"درباره {key_terms[0]} بیشتر بدانم")
                else:
                    suggestions.append("موضوعات مرتبط")
        
        # Add default suggestions if we don't have enough KB-based ones (user perspective)
        if len(suggestions) < 2:
            # Analyze user message for topic
            user_lower = user_message.lower()
            if "آیه" in user_lower:
                suggestions.append("آیه‌های مرتبط")
                suggestions.append("شروع کنش مرتبط")
            elif "کنش" in user_lower:
                suggestions.append("آیه‌های مرتبط با این کنش‌ها")
                suggestions.append("چطور این کنش رو انجام دهم؟")
            else:
                suggestions.append("موضوعات مرتبط")
                suggestions.append("ادامه")
        
        # Ensure we have 2-4 suggestions (user perspective)
        while len(suggestions) < 2:
            suggestions.append("سوالات بیشتر")
        
        # Limit to 4 suggestions
        suggestions = suggestions[:4]
        
        # Convert any AI-perspective suggestions to user perspective
        converted_suggestions = []
        for suggestion in suggestions:
            converted = self._convert_to_user_perspective(suggestion)
            converted_suggestions.append(converted)
        
        # Format suggestions section
        suggestions_text = "\n\nپیشنهادهای بعدی:\n"
        for i, suggestion in enumerate(converted_suggestions, 1):
            suggestions_text += f"{i}) {suggestion}\n"
        
        return output + suggestions_text
    
    def _convert_to_user_perspective(self, suggestion: str) -> str:
        """Convert AI-perspective suggestions to user perspective."""
        # Remove AI-perspective phrases
        suggestion = suggestion.strip()
        
        # Pattern: "میخوای درباره X بدونی؟" → "درباره X بیشتر بدانم" or "X"
        suggestion = re.sub(r'میخوای\s+درباره\s+(.+?)\s+بیشتر\s+بدونی\?', r'درباره \1 بیشتر بدانم', suggestion, flags=re.IGNORECASE)
        suggestion = re.sub(r'میخوای\s+درباره\s+(.+?)\s+بدونی\?', r'درباره \1 بیشتر بدانم', suggestion, flags=re.IGNORECASE)
        suggestion = re.sub(r'آیا\s+می‌خوای\s+(.+?)\s+رو\s+ببینی\?', r'\1', suggestion, flags=re.IGNORECASE)
        suggestion = re.sub(r'میخوای\s+(.+?)\s+رو\s+ببینی\?', r'\1', suggestion, flags=re.IGNORECASE)
        
        # Pattern: "چطور می‌خوای X کنی؟" → "چطور X کنم؟"
        suggestion = re.sub(r'چطور\s+می‌خوای\s+(.+?)\s+کنی\?', r'چطور \1 کنم؟', suggestion, flags=re.IGNORECASE)
        suggestion = re.sub(r'چطور\s+می‌خوای\s+(.+?)\s+شروع\s+کنی\?', r'چطور \1 را شروع کنم؟', suggestion, flags=re.IGNORECASE)
        suggestion = re.sub(r'چطور\s+می‌خوای\s+یک\s+(.+?)\s+رو\s+شروع\s+کنی\?', r'چطور یک \1 را شروع کنم؟', suggestion, flags=re.IGNORECASE)
        
        # Pattern: "میخوای X" → "X"
        suggestion = re.sub(r'^میخوای\s+(.+?)\?', r'\1', suggestion, flags=re.IGNORECASE)
        
        # Pattern: "درباره نحوه انجام X به عنوان Y" → "نحوه انجام X به عنوان Y"
        suggestion = re.sub(r'درباره\s+نحوه\s+انجام\s+(.+?)\s+به\s+عنوان\s+(.+?)\s+بیشتر\s+بدونی\?', r'نحوه انجام \1 به عنوان \2', suggestion, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        suggestion = re.sub(r'\s+', ' ', suggestion).strip()
        
        return suggestion

    def get_capabilities(self) -> list[str]:
        return ["chat", "conversation", "qa", "user_context_extraction", "configurable"]
