"""
Shared suggestion utilities for chain and agent executors.
Provides fallback suggestions and user-perspective conversion.
"""
import re
from typing import Optional


def convert_to_user_perspective(suggestion: str) -> str:
    """Convert AI-perspective suggestions to user perspective."""
    suggestion = suggestion.strip()

    # Pattern: "میخوای درباره X بدونی؟" → "درباره X بیشتر بدانم" or "X"
    suggestion = re.sub(
        r'میخوای\s+درباره\s+(.+?)\s+بیشتر\s+بدونی\?',
        r'درباره \1 بیشتر بدانم',
        suggestion,
        flags=re.IGNORECASE,
    )
    suggestion = re.sub(
        r'میخوای\s+درباره\s+(.+?)\s+بدونی\?',
        r'درباره \1 بیشتر بدانم',
        suggestion,
        flags=re.IGNORECASE,
    )
    suggestion = re.sub(
        r'آیا\s+می‌خوای\s+(.+?)\s+رو\s+ببینی\?',
        r'\1',
        suggestion,
        flags=re.IGNORECASE,
    )
    suggestion = re.sub(
        r'میخوای\s+(.+?)\s+رو\s+ببینی\?',
        r'\1',
        suggestion,
        flags=re.IGNORECASE,
    )

    # Pattern: "چطور می‌خوای X کنی؟" → "چطور X کنم؟"
    suggestion = re.sub(
        r'چطور\s+می‌خوای\s+(.+?)\s+کنی\?',
        r'چطور \1 کنم؟',
        suggestion,
        flags=re.IGNORECASE,
    )
    suggestion = re.sub(
        r'چطور\s+می‌خوای\s+(.+?)\s+شروع\s+کنی\?',
        r'چطور \1 را شروع کنم؟',
        suggestion,
        flags=re.IGNORECASE,
    )
    suggestion = re.sub(
        r'چطور\s+می‌خوای\s+یک\s+(.+?)\s+رو\s+شروع\s+کنی\?',
        r'چطور یک \1 را شروع کنم؟',
        suggestion,
        flags=re.IGNORECASE,
    )

    # Pattern: "میخوای X" → "X"
    suggestion = re.sub(
        r'^میخوای\s+(.+?)\?',
        r'\1',
        suggestion,
        flags=re.IGNORECASE,
    )

    # Pattern: "درباره نحوه انجام X به عنوان Y" → "نحوه انجام X به عنوان Y"
    suggestion = re.sub(
        r'درباره\s+نحوه\s+انجام\s+(.+?)\s+به\s+عنوان\s+(.+?)\s+بیشتر\s+بدونی\?',
        r'نحوه انجام \1 به عنوان \2',
        suggestion,
        flags=re.IGNORECASE,
    )

    suggestion = re.sub(r'\s+', ' ', suggestion).strip()
    return suggestion


def convert_suggestions_to_user_perspective(output: str) -> str:
    """Convert any AI-perspective suggestions in the output to user perspective."""
    suggestions_match = re.search(
        r'پیشنهادهای بعدی:\s*([\s\S]*?)(?:\n\n|$)',
        output,
    )
    if not suggestions_match:
        return output

    suggestions_text = suggestions_match.group(1)
    original_suggestions = suggestions_text.strip()

    suggestions = re.split(r'\n\s*\d+\)\s*', original_suggestions)
    suggestions = [s.strip() for s in suggestions if s.strip()]

    converted_suggestions = []
    for suggestion in suggestions:
        converted = convert_to_user_perspective(suggestion)
        converted_suggestions.append(converted)

    new_suggestions_text = "\n".join(
        [f"{i}) {s}" for i, s in enumerate(converted_suggestions, 1)]
    )
    new_output = (
        output[: suggestions_match.start(1)]
        + new_suggestions_text
        + output[suggestions_match.end(1) :]
    )
    return new_output


def ensure_suggestions_section(
    output: str,
    user_message: str,
    agent_key: str = "unknown",
) -> str:
    """
    Ensure the output always includes a suggestions section.
    If missing, generate contextual suggestions based on output and user query.
    Skips entirely for action_expert (config forbids formal suggestions section).
    """
    if agent_key == "action_expert":
        return output

    suggestions_patterns = [
        r"پیشنهادهای بعدی:",
        r"Next actions:",
        r"پیشنهادهای بعدی\s*:",
        r"Next actions\s*:",
    ]
    has_suggestions = any(
        re.search(pattern, output, re.IGNORECASE) for pattern in suggestions_patterns
    )
    if has_suggestions:
        return output

    suggestions = []
    output_lower = output.lower()
    user_lower = user_message.lower()

    # Use output (KB-grounded response) for content analysis
    if "کنش" in output_lower:
        action_types_in_response = []
        if "مدرسه" in output_lower:
            action_types_in_response.append("مدرسه")
        if "خانه" in output_lower or "خانگی" in output_lower:
            action_types_in_response.append("خانه")
        if "مسجد" in output_lower:
            action_types_in_response.append("مسجد")
        if "محفل" in output_lower:
            action_types_in_response.append("محفل")
        if "فضای مجازی" in output_lower or "مجازی" in output_lower:
            action_types_in_response.append("فضای مجازی")

        if action_types_in_response:
            first_type = action_types_in_response[0]
            if first_type == "محفل":
                suggestions.append("نحوه برگزاری محفل خانگی")
                suggestions.append("آیه‌های مناسب برای محفل")
            elif first_type == "مدرسه":
                suggestions.append("نحوه اجرای کنش در مدرسه")
                if "معرفی" in output_lower or "تبلیغ" in output_lower:
                    suggestions.append("راهکارهای تبلیغ در محیط مدرسه")
            elif first_type == "خانه":
                suggestions.append("ایده‌های کنش خانگی")
                suggestions.append("درگیر کردن خانواده در کنش‌ها")
            elif first_type == "مسجد":
                suggestions.append("هماهنگی با مسئولین مسجد")
            elif first_type == "فضای مجازی":
                suggestions.append("ایده‌های محتوای مجازی")
                suggestions.append("پلتفرم‌های مناسب برای تبلیغ")

    if "سفیر" in output_lower:
        if any(w in output_lower for w in ["نقش", "وظیفه", "مسئولیت"]):
            suggestions.append("چالش‌های سفیران")
            suggestions.append("حمایت‌های سازمان از سفیران")
        elif "شروع" in user_lower or "فعالیت" in output_lower:
            suggestions.append("اولین قدم‌های یک سفیر")
            suggestions.append("دریافت پشتیبانی و آموزش")

    verse_numbers = re.findall(r'آیه\s*(\d+)', output_lower)
    if verse_numbers:
        suggestions.append(f"تفسیر آیه {verse_numbers[0]}")
        if len(verse_numbers) > 1:
            suggestions.append(
                f"ارتباط آیه {verse_numbers[0]} با آیه {verse_numbers[1]}"
            )

    if "ثبت" in output_lower and "گزارش" in output_lower:
        suggestions.append("نحوه ثبت گزارش کنش")
    if "امتیاز" in output_lower or "پاداش" in output_lower:
        suggestions.append("سیستم امتیازدهی سفیران")
    if "تیم" in output_lower or "گروه" in output_lower:
        suggestions.append("همکاری تیمی در انجام کنش‌ها")
    if "پیگیری" in output_lower or "ارزیابی" in output_lower:
        suggestions.append("بررسی نتایج و اثرگذاری کنش‌ها")

    if len(suggestions) < 2:
        if any(word in user_lower for word in ["چطور", "چگونه", "نحوه"]):
            if "گزارش" in output_lower:
                suggestions.append("نمونه گزارش موفق")
            if "کنش" in output_lower:
                suggestions.append("تجربیات سفیران دیگر")
        elif any(word in user_lower for word in ["چیست", "چیه", "یعنی چی", "منظور"]):
            if "سفیر" in output_lower:
                suggestions.append("تفاوت سفیر با سایر نقش‌ها")
            if "کنش" in output_lower:
                suggestions.append("انواع مختلف کنش‌ها")

    if len(suggestions) == 0:
        if "سفیر" in output_lower:
            suggestions.append("سوالات بیشتر درباره نقش سفیران")
        elif "کنش" in output_lower:
            suggestions.append("سوالات بیشتر درباره کنش‌ها")
        else:
            suggestions.append("ادامه مطلب")

    suggestions = suggestions[:4]
    if len(suggestions) == 0:
        return output

    converted_suggestions = [
        convert_to_user_perspective(s) for s in suggestions
    ]
    suggestions_text = "\n\nپیشنهادهای بعدی:\n"
    for i, suggestion in enumerate(converted_suggestions, 1):
        suggestions_text += f"{i}) {suggestion}\n"

    return output + suggestions_text
