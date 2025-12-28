# Fix for Unwanted Extra Text in Agent Responses

## مشکل

Agent گاهی متن اضافی و غیرضروری به پاسخ اضافه می‌کند، مثل:
- "پرسش کلیدی و مهمی مطرح کردید..."
- "بر اساس تجربه نهضت..."
- "برای اینکه صحبت شما..."

این متن‌ها غیرضروری هستند و باید حذف شوند.

## راه حل

### 1. دستورالعمل‌های صریح در System Prompts

به همه فایل‌های personality اضافه شد:

```
⚠️⚠️⚠️ CRITICAL - NO EXTRA TEXT ⚠️⚠️⚠️:
هرگز متن اضافی، توضیح اضافی، یا پاراگراف اضافی بعد از پاسخ اصلی اضافه نکن!

❌ ممنوع:
- "پرسش کلیدی و مهمی مطرح کردید..."
- "بر اساس تجربه نهضت..."
- "برای اینکه صحبت شما..."
- هر توضیح اضافی یا پاراگراف اضافی بعد از پاسخ اصلی

✅ فقط این ساختار را رعایت کن:
1. پاسخ اصلی (کوتاه و مستقیم)
2. پیشنهادهای بعدی (فقط لیست)

هیچ چیز دیگری اضافه نکن!
```

### 2. Post-Processing Function

تابع `_remove_unwanted_extra_text()` در `chat_agent.py` اضافه شد که:
- الگوهای متن اضافی را شناسایی می‌کند
- آن‌ها را حذف می‌کند
- فاصله‌های اضافی را تمیز می‌کند

### فایل‌های به‌روزرسانی شده

1. ✅ `services/chat-service/config/agent_config.yaml`
2. ✅ `services/chat-service/config/personalities/friendly_tutor.yaml`
3. ✅ `services/chat-service/config/personalities/minimal_assistant.yaml`
4. ✅ `services/chat-service/config/personalities/professional_assistant.yaml`
5. ✅ `services/chat-service/config/personalities/konesh_expert.yaml`
6. ✅ `services/chat-service/agents/chat_agent.py` (تابع post-processing)

### تست

برای تست کردن:

```bash
# بعد از restart سرویس
curl -X POST http://localhost:8001/chat/default \
  -H "Content-Type: application/json" \
  -d '{"message": "به دختران روستایی چی بگم", "session_id": null}'
```

باید فقط پاسخ اصلی و پیشنهادهای بعدی را ببینید، بدون متن اضافی.

### برای اعمال تغییرات

```bash
docker-compose restart chat-service
```

