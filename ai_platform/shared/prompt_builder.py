"""
Shared system prompt builder for both Pydantic AI and LangChain chain-based executors.
Ensures consistent context injection (user info, recent messages) across execution modes.
"""
from typing import Any, Dict, List, Optional


def get_dynamic_field_instructions(
    agent_config: Any,
    executor_mode: str = "pydantic_ai"
) -> str:
    """
    Build dynamic field extraction instructions based on enabled fields.

    For pydantic_ai: Instructions to use save_user_info tool.
    For langchain_chain: Entity extraction runs automatically; minimal instructions.
    """
    enabled_fields = agent_config.get_enabled_fields()
    if not enabled_fields:
        return ""

    if executor_mode == "langchain_chain":
        # Chain mode: entity extraction runs before generation
        field_names = [f.field_name for f in enabled_fields]
        return (
            "🔧 User data extraction runs automatically. "
            f"Focus on natural response. Extracted fields: {', '.join(field_names)}"
        )

    # Agentic mode: tool-based extraction
    lines = ["🔧 فیلدهای قابل ذخیره (از save_user_info استفاده کن):"]
    for f in enabled_fields:
        aliases_hint = f" یا {', '.join(f.aliases)}" if f.aliases else ""
        lines.append(f"  - {f.field_name}{aliases_hint} → save_user_info(field_name=\"{f.field_name}\", ...)")
    return "\n".join(lines)


def build_system_prompt(
    agent_config: Any,
    user_info: Dict[str, Any],
    last_user_messages: List[Dict[str, Any]],
    executor_mode: str = "pydantic_ai",
    agent_key: Optional[str] = None,
    session_state: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build context-aware system prompt using configuration.

    Shared between ChatAgent (Pydantic AI) and ChainExecutor (LangChain).

    Args:
        agent_config: Agent configuration with context_display, recent_messages_context,
                      user_data_fields, and get_complete_system_prompt(executor_mode)
        user_info: Shared context {normalized_name: {"value": ...}}
        last_user_messages: Recent messages [{"role": "user"|"assistant", "content": str}, ...]
        executor_mode: "pydantic_ai" or "langchain_chain" for prompt variant
        agent_key: Agent key for few-shot example selection (e.g. guest_faq, action_expert)
        session_state: Optional dict with user_mode ("guided" | "free") for Guided/Free prompt line

    Returns:
        Full system prompt string
    """
    parts = []

    # Get complete system prompt from config (includes executor_mode variant)
    if hasattr(agent_config, 'get_complete_system_prompt'):
        get_prompt = agent_config.get_complete_system_prompt
        import inspect
        sig = inspect.signature(get_prompt)
        if 'executor_mode' in sig.parameters:
            complete_prompt = get_prompt(executor_mode=executor_mode)
        else:
            complete_prompt = get_prompt()
    else:
        complete_prompt = getattr(agent_config, 'system_prompt', '') or ""

    if complete_prompt:
        parts.append(complete_prompt)

    # Add few-shot examples from 49 Q&A document (QA format alignment)
    if agent_key:
        try:
            from shared.qa_examples_loader import get_few_shot_examples
            few_shot = get_few_shot_examples(agent_key, max_examples=5)
            if few_shot:
                parts.append(few_shot)
        except Exception:
            pass

    # Add dynamic field instructions
    field_instructions = get_dynamic_field_instructions(agent_config, executor_mode)
    if field_instructions:
        parts.append(field_instructions)

    # Add user information context if enabled
    context_config = getattr(agent_config, 'context_display', {}) or {}
    if context_config.get('enabled', True) and user_info:
        context_lines = [context_config.get('header', '📋 User Information:')]
        field_labels = context_config.get('field_labels', {})
        language_names = context_config.get('language_names', {})

        for field_config in agent_config.user_data_fields:
            normalized_name = field_config.normalized_name
            if normalized_name not in user_info:
                continue

            value_data = user_info[normalized_name]
            value = value_data.get("value") if isinstance(value_data, dict) else value_data
            if not value:
                continue

            label = field_labels.get(normalized_name, normalized_name)
            if isinstance(value, list) and len(value) > 0:
                value_str = "، ".join(str(v) for v in value)
                context_lines.append(f"  • {label}: {value_str}")
            elif normalized_name == "preferred_language" and value in language_names:
                lang_display = language_names.get(value, value)
                context_lines.append(f"  • {label}: {lang_display}")
            else:
                context_lines.append(f"  • {label}: {value}")

        if len(context_lines) > 1:
            parts.append("\n".join(context_lines))

    # Add recent messages context if enabled
    recent_config = getattr(agent_config, 'recent_messages_context', {}) or {}
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
        # Mid-conversation: do not repeat full greeting so the reply feels natural
        parts.append(
            "⚠️ You are mid-conversation (there are recent messages above). "
            "Do NOT start your reply with a full greeting like «سلام [name]! چطور می‌تونم کمکت کنم؟» or «سلام X! چه خبر؟». "
            "Answer directly and naturally. Vary your openings: use ببین، راستی، خب، or go straight to the answer. "
            "Do NOT overuse «احسنت به این همت»—use it rarely; often start with ببین، راستی، or the main point."
        )

    # Always: vary openings and avoid repeating the same phrase every time
    parts.append(
        "🔄 Vary how you start replies. Do not start every answer with «احسنت به این همت». "
        "Use ببین، راستی، خب، یا مستقیم برو سراغ مطلب؛ فقط گاهی از احسنت استفاده کن."
    )

    # Guided vs Free mode: reduce bot-like behavior and prioritize user intent
    if session_state:
        user_mode = session_state.get("user_mode", "guided")
        if user_mode == "free":
            parts.append(
                "🎯 کاربر در گفتگوی آزاد است. مثل یک مکالمه طبیعی پاسخ بده؛ "
                "از اشاره مکرر به کنش/تگ/موضوع به‌صورت لیبل خودداری کن و به نیت کاربر اولویت بده."
            )
        else:
            parts.append(
                "🎯 کاربر در حالت راهنماست؛ پیشنهادها برای گرم کردن گفتگو هستند. پاسخ طبیعی بده."
            )

    return "\n\n".join(parts)


def build_context_summary(agent_config: Any, user_info: Dict[str, Any]) -> str:
    """
    Build a brief context summary for injecting into user message.
    Used for <internal_context> tag in agentic mode.
    """
    if not user_info:
        return ""

    context_display = getattr(agent_config, 'context_display', None) or {}
    field_labels = {}
    for field_config in agent_config.user_data_fields:
        label = context_display.get('field_labels', {}).get(
            field_config.normalized_name,
            field_config.field_name
        )
        field_labels[field_config.normalized_name] = label

    parts = []
    for key, data in user_info.items():
        value = data.get('value') if isinstance(data, dict) else data
        if value:
            label = field_labels.get(key, key)
            if isinstance(value, list):
                value = '، '.join(str(v) for v in value)
            parts.append(f"{label}: {value}")

    return '؛ '.join(parts) if parts else ""
