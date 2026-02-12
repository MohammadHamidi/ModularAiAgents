"""
Shared system prompt builder for both Pydantic AI and LangChain chain-based executors.
Ensures consistent context injection (user info, recent messages) across execution modes.
"""
from typing import Any, Dict, List, Optional


def get_dynamic_field_instructions(
    agent_config: Any,
    executor_mode: str = "langchain_chain"
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
    executor_mode: str = "langchain_chain",
    agent_key: Optional[str] = None,
) -> str:
    """
    Build context-aware system prompt using configuration.

    Shared by ChainExecutor (LangChain).

    Args:
        agent_config: Agent configuration with context_display, recent_messages_context,
                      user_data_fields, and get_complete_system_prompt(executor_mode)
        user_info: Shared context {normalized_name: {"value": ...}}
        last_user_messages: Recent messages [{"role": "user"|"assistant", "content": str}, ...]
        executor_mode: "pydantic_ai" or "langchain_chain" for prompt variant
        agent_key: Agent key for few-shot example selection (e.g. guest_faq, action_expert)

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

    # Entry path context - where user came from (CRITICAL for understanding user's context)
    if user_info:
        entry_path_data = user_info.get("entry_path")
        if entry_path_data:
            entry_path = entry_path_data.get("value") if isinstance(entry_path_data, dict) else entry_path_data
            if entry_path:
                try:
                    from shared.path_context_helper import format_entry_path_context
                    entry_ctx = format_entry_path_context(entry_path)
                    if entry_ctx:
                        parts.append(entry_ctx)
                except Exception:
                    # Fallback: simple path display
                    parts.append(f"📍 کاربر چت را از صفحه {entry_path} باز کرده است.")

    # Action details context from Safiran API (if available)
    if user_info:
        action_details_data = user_info.get("action_details")
        if action_details_data:
            action_details = action_details_data.get("value") if isinstance(action_details_data, dict) else action_details_data
            if isinstance(action_details, dict):
                # Handle both flat and nested payloads
                data_obj = action_details.get("data") if isinstance(action_details.get("data"), dict) else action_details
                title = data_obj.get("title") or data_obj.get("name") or action_details.get("title")
                desc = data_obj.get("description") or action_details.get("description")
                if title:
                    block = f"🧩 جزئیات کنش فعلی کاربر:\n- عنوان: {title}"
                    if desc:
                        desc_short = desc[:240] + ("..." if len(desc) > 240 else "")
                        block += f"\n- توضیح: {desc_short}"
                    parts.append(block)

    # User actions summary context from Profile/GetMyActions
    if user_info:
        my_actions_data = user_info.get("user_my_actions")
        if my_actions_data:
            my_actions_payload = my_actions_data.get("value") if isinstance(my_actions_data, dict) else my_actions_data
            total_count = None
            if isinstance(my_actions_payload, dict):
                # Try common count keys
                for key in ("total", "totalCount", "count"):
                    if isinstance(my_actions_payload.get(key), int):
                        total_count = my_actions_payload.get(key)
                        break
                if total_count is None:
                    # Try common list keys
                    for key in ("items", "data", "result", "myActions"):
                        val = my_actions_payload.get(key)
                        if isinstance(val, list):
                            total_count = len(val)
                            break
            elif isinstance(my_actions_payload, list):
                total_count = len(my_actions_payload)

            if isinstance(total_count, int):
                parts.append(
                    f"📈 وضعیت فعالیت کاربر:\n- تعداد کنش‌های کاربر در سیستم: {total_count}\n"
                    "در پاسخ‌ها از این زمینه برای پیشنهادهای شخصی‌سازی‌شده استفاده کن."
                )

    # Website routes context - for redirecting users to correct URLs
    try:
        from shared.website_routes_loader import get_website_routes_context
        routes_ctx = get_website_routes_context()
        if routes_ctx:
            parts.append(routes_ctx)
    except Exception:
        pass

    # Critical context awareness: User is already talking to YOU (the AI assistant)
    parts.append(
        "⚠️⚠️⚠️ CRITICAL - Context Awareness (YOU ARE THE AI ASSISTANT):\n"
        "- You ARE the AI assistant - the user is already talking to YOU right now\n"
        "- ❌ NEVER say: 'Let's use AI' or 'موافقی از هوش مصنوعی استفاده کنیم؟' - YOU ARE the AI\n"
        "- ❌ NEVER suggest: 'Let's choose a verse together' - YOU should directly help and create content\n"
        "- ✅ CORRECT: Provide direct help, create content directly, don't suggest meta-actions\n"
        "- ✅ CORRECT: Say 'بذار برات یه جمله کلیدی بسازم...' not 'موافقی یه جمله کلیدی بسازیم؟'\n"
        "- When user asks for help, YOU provide it directly - don't suggest using 'another AI' or 'the assistant'\n"
        "\n"
        "⚠️⚠️⚠️ CRITICAL - Initial Response Style (First Message After Conversation Starter):\n"
        "- When user clicks a conversation starter (first message in conversation), keep response SHORT and DIRECT\n"
        "- ❌ AVOID: 'بذار برات کامل بازش کنم' in initial responses (too verbose for first message)\n"
        "- ❌ AVOID: Repeating context user already knows (e.g., 'تو که الان توی صفحه... هستی')\n"
        "- ✅ CORRECT: Start directly with help. Example: 'این کنش برای پر کردن فاصله بین تلاوت و تدبر طراحی شده...'\n"
        "- ✅ CORRECT: Initial responses should be 3-5 sentences, direct and actionable\n"
        "- ✅ CORRECT: Use 'بذار برات کامل بازش کنم' only for follow-up responses, not initial ones\n"
    )

    # Output format: never include citation artifacts from KB/LightRAG
    parts.append(
        "⚠️ OUTPUT FORMAT - NEVER include in your response:\n"
        "- (Reference ID: N) or similar citation markers - these are internal KB artifacts, not for users\n"
        "- Do not copy or reproduce any (Reference ID: ...) text from the KB context into your answer\n"
        "- Use the knowledge content naturally but never include such citation artifacts"
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
            # Skip heavy payloads in inline context block (handled separately in system prompt)
            if key in {"action_details", "user_my_actions"}:
                if key == "action_details" and isinstance(value, dict):
                    nested = value.get("data") if isinstance(value.get("data"), dict) else {}
                    title = (
                        value.get("title")
                        or nested.get("title")
                    )
                    if title:
                        parts.append(f"کنش فعلی: {title}")
                elif key == "user_my_actions":
                    total = None
                    if isinstance(value, dict):
                        total = value.get("total") if isinstance(value.get("total"), int) else None
                        if total is None:
                            items = value.get("items")
                            if isinstance(items, list):
                                total = len(items)
                    elif isinstance(value, list):
                        total = len(value)
                    if isinstance(total, int):
                        parts.append(f"تعداد کنش‌های کاربر: {total}")
                continue
            label = field_labels.get(key, key)
            if isinstance(value, list):
                value = '، '.join(str(v) for v in value)
            parts.append(f"{label}: {value}")

    return '؛ '.join(parts) if parts else ""
