# Direct & Practical Response Instructions

## Problem

The AI agents were giving formal, academic responses with:
- Meta-commentary like "برای پاسخ به این سؤال، ابتدا بستر و مخاطب را دقیقاً مشخص می‌کنم..."
- Formal structures with numbered sections and academic headings
- Too much explanation about methodology instead of direct answers
- Not casual and guiding enough

## Solution

Added explicit instructions to all personality configs to:
1. **Go directly to the answer** - no meta-commentary
2. **Use practical, actionable responses** - not academic structures
3. **Be casual and guiding** - like a friend helping out
4. **Avoid formal numbered structures** - use natural, simple formatting

## What Was Added

### New Section: `⚠️⚠️⚠️ CRITICAL - DIRECT & PRACTICAL RESPONSES ⚠️⚠️⚠️`

**❌ Forbidden:**
- "برای پاسخ به این سؤال، ابتدا بستر و مخاطب را دقیقاً مشخص می‌کنم..."
- "برای رساندن پیام، نه تنها چه چیزی بگویید، بلکه چگونه بگویید..."
- Formal structures with numbering and academic headings
- Meta-commentary about how to answer
- Starting with "بسیار عالی است که..." or "برای پاسخ به این سؤال..."

**✅ Required:**
- Go directly to the answer - no introductory text
- Give practical, actionable answers
- Use simple, natural structures (not formal numbering)
- Talk like a friend giving guidance
- Give concrete, everyday examples
- Keep answers short and direct

### Example Good Response:
```
برای دختران روستایی، بهتره از مثال‌های طبیعی و ملموس استفاده کنی. 
مثلاً وقتی درباره صبر حرف می‌زنی، از کشاورزی مثال بزن که چطور باید 
صبر کنه تا محصول برسه.

موضوعات مهم براشون: عزت نفس، کار و تلاش، روابط خانوادگی، و امید به آینده. 
می‌تونی آیات مرتبط با این موضوعات رو پیدا کنی و به زبان ساده توضیح بدی.

مهم اینه که از زبان صمیمی و محاوره‌ای استفاده کنی، نه رسمی. 
جلسات رو هم در فضای صمیمی برگزار کنی، نه کلاس خشک.
```

### Example Bad Response (Don't Do):
```
برای پاسخ به این سؤال، ابتدا بستر و مخاطب را دقیقاً مشخص می‌کنم...

۱. اصل محوری: «زندگی با آیه‌ها»
۲. چه بگویید (محتوای کانونی):
۳. چگونه بگویید (روش‌های مؤثر):
```

## Files Updated

1. ✅ `services/chat-service/config/agent_config.yaml`
2. ✅ `services/chat-service/config/personalities/friendly_tutor.yaml`
3. ✅ `services/chat-service/config/personalities/konesh_expert.yaml`
4. ✅ `services/chat-service/config/personalities/minimal_assistant.yaml`
5. ✅ `services/chat-service/config/personalities/professional_assistant.yaml`

## Post-Processing Enhancement

Also updated `_remove_unwanted_extra_text()` function to catch:
- "برای پاسخ به این سؤال..."
- "ابتدا بستر و مخاطب را..."
- "برای رساندن پیام..."
- "نه تنها چه چیزی بگویید..."
- "بلکه چگونه بگویید..."
- "اهمیت حیاتی دارد..."
- "اصل محوری..."
- "محتوای کانونی..."
- "روش‌های مؤثر..."

## To Apply Changes

```bash
docker-compose restart chat-service
```

After restart, all agents will give direct, practical, casual responses without formal structures or meta-commentary.

