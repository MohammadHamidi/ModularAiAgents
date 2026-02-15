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

    # Answer completeness
    parts.append("⚠️ استفاده از دانش: از اطلاعات پایگاه دانش برای پاسخ کامل و دقیق استفاده کن. پاسخ‌های خیلی کوتاه یا ناقص نده.")

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
            
            # Skip complex fields that are handled separately below
            if normalized_name in ("action_details", "user_my_actions", "entry_path"):
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
            # Add first-name hint for personalization when user_full_name exists
            full_name_data = user_info.get("user_full_name")
            full_name = full_name_data.get("value") if isinstance(full_name_data, dict) else full_name_data
            if full_name and isinstance(full_name, str) and full_name.strip():
                first_name = full_name.strip().split()[0] if full_name.strip().split() else full_name.strip()
                parts.append(f"✅ شخصی‌سازی: از نام «{first_name}» در متن پاسخ استفاده کن (نه در ابتدا به عنوان سلام). از اطلاعات کاربر برای شخصی‌سازی استفاده کن.")
        
        # User data usage instruction
        parts.append(
            "⚠️ استفاده از اطلاعات کاربر: فقط از اطلاعاتی استفاده کن که در بخش '📋 User Information' بالا وجود دارد. اطلاعاتی که در این بخش نیست را هرگز حدس نزن یا به کار نبر."
        )

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
    entry_path = None
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
    
    # Determine if user is registered/logged in
    is_registered = False
    if user_info:
        # Check for user_id (from Safiran API) - normalized as "user_id"
        user_id_data = user_info.get("user_id")
        if user_id_data:
            user_id_value = user_id_data.get("value") if isinstance(user_id_data, dict) else user_id_data
            if user_id_value:
                is_registered = True
        
        # Also check for phone_number (indicates registration) - normalized as "user_phone"
        phone_data = user_info.get("user_phone")
        if phone_data:
            phone_value = phone_data.get("value") if isinstance(phone_data, dict) else phone_data
            if phone_value:
                is_registered = True
        
        # Check for score or level (indicates registered user)
        score_data = user_info.get("user_score")
        if score_data:
            score_value = score_data.get("value") if isinstance(score_data, dict) else score_data
            if score_value is not None:
                is_registered = True
        
        # Check entry_path - /home indicates logged in user
        if entry_path:
            if entry_path == "/home" or entry_path.startswith("/my-profile"):
                is_registered = True
    
    # Registration status
    if is_registered:
        parts.append("✅ کاربر ثبت‌نام کرده - پیشنهاد ثبت‌نام نده. به استفاده از پلتفرم راهنماییش کن.")
    else:
        parts.append("⚠️ کاربر ثبت‌نام نکرده - در صورت نیاز می‌توانی پیشنهاد ثبت‌نام بدهی.")

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

                    # Action context instruction
                    parts.append(
                        f"⚠️ زمینه کنش: کاربر در حال دیدن کنش «{title}» است. وقتی می‌گوید «برای این کنش» یا «همین کنش»، همین کنش را مد نظر داشته باش و موضوع را عوض نکن."
                    )

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
            # URL usage instruction
            parts.append("⚠️ استفاده از آدرس‌ها: همیشه از آدرس‌های دقیق لیست بالا استفاده کن. آدرس حدسی یا عمومی نده.")
    except Exception:
        pass

    # Core conversation rules
    parts.append(
        "⚠️ قوانین مکالمه:\n"
        "• تو هوش مصنوعی هستی - کمک مستقیم ارائه کن. نگو «موافقی از هوش مصنوعی استفاده کنیم؟»\n"
        "• محدوده کاری: فقط درباره کنش‌های قرآنی، تولید محتوا و راهنمایی سفیران پاسخ بده. سوالات ریاضی، پزشکی یا عمومی را رد کن.\n"
        "• هرگز سلام دوباره نگو - پیام خوشامد قبلاً سلام کرده. مستقیم کمک کن.\n"
        "• پاسخ‌ها کوتاه و مستقیم باشد. زمینه‌ای که کاربر می‌داند را تکرار نکن.\n"
        "• از نام کاربر در متن پیام استفاده کن (نه در ابتدای پیام به عنوان سلام دوباره)."
    )

    # Output format
    parts.append("⚠️ فرمت خروجی: هرگز علائم مرجع داخلی مثل (Reference ID: N) را در پاسخ نیاور. از محتوای دانش به صورت طبیعی استفاده کن.")

    # Chain mode instructions
    if executor_mode == "langchain_chain":
        parts.append(
            "⚠️ دستورالعمل‌ها:\n"
            "• اطلاعات پایگاه دانش از قبل در پیام کاربر آماده شده. از آن استفاده کن و ابزارها را صدا نزن.\n"
            "• تاریخچه مکالمه را بخوان و از آن استفاده کن. اگر کاربر در پیام قبلی کنش خاصی را ذکر کرد، همان را ادامه بده."
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
