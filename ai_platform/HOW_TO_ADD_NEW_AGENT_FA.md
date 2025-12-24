# راهنمای افزودن عامل هوش مصنوعی جدید

این راهنما به شما نشان می‌دهد که چگونه یک عامل هوش مصنوعی جدید به سیستم اضافه کنید و آن را در ارکستر ثبت کنید تا به درستی درخواست‌ها را هدایت کند.

## 📋 فهرست مطالب

1. [نمای کلی](#نمای-کلی)
2. [مراحل افزودن عامل جدید](#مراحل-افزودن-عامل-جدید)
3. [مثال عملی: افزودن عامل متخصص پزشکی](#مثال-عملی-افزودن-عامل-متخصص-پزشکی)
4. [افزودن ابزارهای سفارشی](#افزودن-ابزارهای-سفارشی)
5. [به‌روزرسانی ارکستر](#به‌روزرسانی-ارکستر)
6. [تست و بررسی](#تست-و-بررسی)

---

## نمای کلی

سیستم از سه بخش اصلی تشکیل شده است:

1. **فایل پیکربندی YAML**: تعریف شخصیت، دستورالعمل‌ها و ویژگی‌های عامل
2. **ثبت در `main.py`**: افزودن عامل به سیستم و تعریف ابزارهایش
3. **به‌روزرسانی ارکستر**: آموزش ارکستر برای هدایت درخواست‌ها به عامل جدید

---

## مراحل افزودن عامل جدید

### مرحله ۱: ایجاد فایل پیکربندی YAML

در پوشه `services/chat-service/config/personalities/` یک فایل YAML جدید با نام مناسب ایجاد کنید.

**نام فایل**: `your_agent_name.yaml`

**ساختار پایه:**

```yaml
# نام عامل
agent_name: "نام عامل به فارسی"
agent_version: "1.0"
description: "توضیح کوتاه از نقش و وظیفه عامل"

system_prompt: |
  تو یک [نقش عامل] هستی.
  
  🎯 مأموریت تو:
  - [وظیفه ۱]
  - [وظیفه ۲]
  - [وظیفه ۳]
  
  📚 دانش و تخصص تو:
  [توضیح دانش تخصصی عامل]
  
  💡 نحوه پاسخ‌دهی:
  [دستورالعمل‌های نحوه پاسخ دادن]
  
  🌐 زبان:
  - پاسخ‌ها به فارسی (مگر کاربر انگلیسی بخواد)
  - [سایر دستورالعمل‌های زبانی]

silent_operation_instructions: |
  ⚠️ دستورالعمل‌های عملیاتی:
  - [دستورالعمل ۱]
  - [دستورالعمل ۲]

tool_usage_instructions: |
  🔧 نحوه استفاده از ابزارها:
  [توضیح نحوه استفاده از ابزارها]

# فیلدهای داده کاربر (اختیاری)
user_data_fields:
  - field_name: field_name
    normalized_name: normalized_field_name
    description: "توضیح فیلد"
    examples: ["مثال ۱", "مثال ۲"]
    data_type: string
    enabled: true

# نمایش زمینه کاربر (اختیاری)
context_display:
  enabled: true
  header: "📋 اطلاعات کاربر:"
  format: "bullet"
  field_labels:
    normalized_field_name: "برچسب نمایشی"

# پیام‌های اخیر (اختیاری)
recent_messages_context:
  enabled: true
  count: 2
  max_length: 150
  header: "💬 آخرین پیام‌ها:"

# تنظیمات مدل
model_config:
  default_model: "gemini-2.5-flash-lite-preview-09-2025"
  temperature: 0.7
  max_turns: 12
  max_tokens: null

# حریم خصوصی
privacy:
  data_ttl: 14400
  auto_delete_sensitive_fields: false
```

---

### مرحله ۲: ثبت عامل در `main.py`

فایل `services/chat-service/main.py` را باز کنید و مراحل زیر را انجام دهید:

#### ۲.۱: افزودن به `persona_configs`

در تابع `startup()`, در بخش `persona_configs`، عامل جدید را اضافه کنید:

```python
persona_configs = {
    "default": "agent_config.yaml",
    "tutor": "personalities/friendly_tutor.yaml",
    "professional": "personalities/professional_assistant.yaml",
    "minimal": "personalities/minimal_assistant.yaml",
    "konesh_expert": "personalities/konesh_expert.yaml",
    "orchestrator": "personalities/orchestrator.yaml",
    "your_agent_key": "personalities/your_agent_name.yaml",  # ← اضافه کنید
}
```

#### ۲.۲: تعریف ابزارهای عامل (اختیاری)

اگر عامل به ابزارهای خاصی نیاز دارد، در بخش `persona_tool_assignments` اضافه کنید:

```python
persona_tool_assignments = {
    "default": ["knowledge_base_query", "calculator", "get_weather"],
    "tutor": ["knowledge_base_query", "calculator", "get_learning_resource"],
    "professional": ["knowledge_base_query", "web_search", "get_company_info", "calculator"],
    "minimal": [],
    "konesh_expert": ["query_konesh", "knowledge_base_query"],
    "orchestrator": ["route_to_agent"],
    "your_agent_key": ["tool_name_1", "tool_name_2"],  # ← اضافه کنید
}
```

**نکته**: ابزارهای موجود در سیستم:
- `knowledge_base_query`: جستجو در پایگاه دانش
- `calculator`: ماشین حساب
- `get_weather`: اطلاعات آب و هوا
- `web_search`: جستجو در وب
- `get_company_info`: اطلاعات شرکت
- `query_konesh`: جستجو در پایگاه کنش‌ها
- `route_to_agent`: هدایت به عامل دیگر (فقط برای ارکستر)

---

### مرحله ۳: به‌روزرسانی ارکستر

برای اینکه ارکستر بتواند درخواست‌ها را به عامل جدید هدایت کند، فایل `services/chat-service/config/personalities/orchestrator.yaml` را به‌روزرسانی کنید.

#### ۳.۱: افزودن به فهرست عوامل متخصص

در بخش `📋 Available Specialist Agents`, عامل جدید را اضافه کنید:

```yaml
system_prompt: |
  ...
  
  📋 Available Specialist Agents:
  
  1. **doctor** - Medical Assistant
     Topics: health, medical conditions, symptoms, medications
     Keywords: دکتر, پزشک, بیماری, دارو, سلامتی, health, medicine
  
  2. **tutor** - Educational Tutor
     Topics: learning, education, teaching, homework
     Keywords: یادگیری, درس, مدرسه, معلم, study, learn
  
  3. **konesh_expert** - Quranic Actions Expert
     Topics: Quranic actions, action selection, action design
     Keywords: کنش, کنش‌ها, کنش قرآنی, action, actions
  
  4. **your_agent_key** - [توضیح نقش عامل]  # ← اضافه کنید
     Topics: [موضوعات مرتبط]
     Keywords: [کلمات کلیدی فارسی و انگلیسی]
  
  ...
```

#### ۳.۲: افزودن قوانین هدایت

در بخش `🔍 Routing Rules`, قانون هدایت را اضافه کنید:

```yaml
  🔍 Routing Rules:

  - If message contains medical/health keywords → route to "doctor"
  - If message contains educational/learning keywords → route to "tutor"
  - If message contains Quranic actions keywords → route to "konesh_expert"
  - If message contains [keywords for your agent] → route to "your_agent_key"  # ← اضافه کنید
  - If message contains Quranic/religious keywords (but not about actions) → route to "default"
  - If unclear or general greeting → route to "default"
```

#### ۳.۳: به‌روزرسانی ابزار `route_to_agent`

در فایل `services/chat-service/tools/agent_router.py`, فهرست عوامل موجود را به‌روزرسانی کنید:

```python
description: |
  ...
  Parameters:
  - agent_key (str, required): The key of the specialist agent to route to.
    Available agents: 'doctor', 'tutor', 'professional', 'default', 'minimal', 'konesh_expert', 'your_agent_key'
  ...
```

---

## مثال عملی: افزودن عامل متخصص پزشکی

بیایید یک مثال کامل را از ابتدا تا انتها انجام دهیم:

### مرحله ۱: ایجاد فایل `doctor.yaml`

```yaml
# متخصص پزشکی
agent_name: "متخصص پزشکی"
agent_version: "1.0"
description: "متخصص در مسائل پزشکی و سلامتی - ارائه راهنمایی و اطلاعات پزشکی"

system_prompt: |
  تو یک متخصص پزشکی و سلامتی هستی.

  🎯 مأموریت تو:
  - ارائه اطلاعات پزشکی دقیق و قابل اعتماد
  - راهنمایی درباره علائم بیماری‌ها
  - توصیه‌های پیشگیرانه برای سلامتی
  - هشدار درباره موارد اضطراری و نیاز به مراجعه به پزشک

  ⚠️ محدودیت‌های مهم:
  - تو نمی‌توانی تشخیص قطعی بیماری بدهی
  - در صورت علائم جدی، همیشه توصیه کن که به پزشک مراجعه کنند
  - از تجویز دارو بدون نسخه پزشک خودداری کن

  🌐 زبان:
  - پاسخ‌ها به فارسی (مگر کاربر انگلیسی بخواد)
  - ساده، واضح و قابل فهم

model_config:
  default_model: "gemini-2.5-flash-lite-preview-09-2025"
  temperature: 0.7
  max_turns: 15
  max_tokens: null

privacy:
  data_ttl: 14400
  auto_delete_sensitive_fields: true
```

### مرحله ۲: ثبت در `main.py`

```python
persona_configs = {
    # ... سایر عوامل
    "doctor": "personalities/doctor.yaml",  # ← اضافه کنید
}

persona_tool_assignments = {
    # ... سایر عوامل
    "doctor": ["knowledge_base_query"],  # ← ابزارهای لازم
}
```

### مرحله ۳: به‌روزرسانی ارکستر

در `orchestrator.yaml`:

```yaml
  1. **doctor** - Medical Assistant
     Topics: health, medical conditions, symptoms, medications, allergies, diseases, doctors, hospitals
     Keywords: دکتر, پزشک, بیماری, دارو, علائم, سلامتی, health, medicine, symptom, doctor
```

و در قوانین هدایت:

```yaml
  - If message contains medical/health keywords → route to "doctor"
```

---

## افزودن ابزارهای سفارشی

اگر عامل جدید به ابزار خاصی نیاز دارد که در سیستم وجود ندارد:

### مرحله ۱: ایجاد کلاس ابزار

یک فایل جدید در `services/chat-service/tools/` ایجاد کنید، مثلاً `custom_tool.py`:

```python
"""
Custom Tool - توضیح ابزار
"""
from tools.registry import Tool
from typing import Dict, Any, Optional

class CustomTool(Tool):
    """توضیح ابزار"""

    def __init__(self):
        super().__init__(
            name="custom_tool_name",
            description="""
            توضیح کامل ابزار و نحوه استفاده از آن.
            
            Parameters:
            - param1 (str, required): توضیح پارامتر
            - param2 (int, optional): توضیح پارامتر دیگر
            
            Returns: توضیح خروجی
            """,
            parameters={
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "توضیح پارامتر"
                    },
                    "param2": {
                        "type": "integer",
                        "description": "توضیح پارامتر"
                    }
                },
                "required": ["param1"]
            }
        )
    
    async def execute(self, param1: str, param2: Optional[int] = None) -> str:
        """
        اجرای ابزار
        
        Args:
            param1: پارامتر اول
            param2: پارامتر دوم (اختیاری)
        
        Returns:
            نتیجه به صورت JSON string
        """
        # منطق ابزار
        result = {
            "status": "success",
            "data": f"Processed {param1}"
        }
        
        import json
        return json.dumps(result, ensure_ascii=False, indent=2)
```

### مرحله ۲: ثبت ابزار در `main.py`

```python
from tools.custom_tool import CustomTool

# در تابع startup(), در بخش ثبت ابزارها:
ToolRegistry.register_tool(CustomTool())
```

### مرحله ۳: افزودن handler در `chat_agent.py`

اگر ابزار پارامترهای پیچیده‌ای دارد، در `services/chat-service/agents/chat_agent.py` یک handler اضافه کنید:

```python
elif tool.name == "custom_tool_name":
    async def custom_tool_handler(
        ctx: RunContext[ChatDependencies],
        param1: str,
        param2: Optional[int] = None
    ) -> str:
        """توضیح کوتاه."""
        result = await tool_ref.execute(param1=param1, param2=param2)
        ctx.deps.tool_results[tool_ref.name] = result
        return result
    custom_tool_handler.__doc__ = full_doc
    self.agent.tool(custom_tool_handler)
```

---

## تست و بررسی

### مرحله ۱: ساخت و راه‌اندازی مجدد

```bash
cd /path/to/ai_platform
docker-compose build chat-service
docker-compose up -d chat-service
```

### مرحله ۲: بررسی ثبت عامل

```bash
# بررسی فهرست عوامل
curl http://localhost:8001/agents | python3 -m json.tool

# بررسی فهرست personas
curl http://localhost:8001/personas | python3 -m json.tool

# بررسی سلامت سرویس
curl http://localhost:8001/health
```

### مرحله ۳: تست مستقیم عامل

```bash
curl -X POST http://localhost:8001/chat/your_agent_key \
  -H "Content-Type: application/json" \
  -d '{"message": "پیام تست"}'
```

### مرحله ۴: تست هدایت از طریق ارکستر

```bash
curl -X POST http://localhost:8001/chat/orchestrator \
  -H "Content-Type: application/json" \
  -d '{"message": "پیامی که باید به عامل جدید هدایت شود"}'
```

### مرحله ۵: بررسی لاگ‌ها

```bash
docker-compose logs chat-service | grep -E "your_agent_key|Routing|Registered agent"
```

---

## نکات مهم

### ✅ بهترین روش‌ها

1. **نام‌گذاری**: از نام‌های واضح و توصیفی استفاده کنید
   - ✅ خوب: `doctor`, `konesh_expert`, `financial_advisor`
   - ❌ بد: `agent1`, `helper`, `bot`

2. **کلمات کلیدی**: کلمات کلیدی متنوع و مرتبط انتخاب کنید
   - هم فارسی و هم انگلیسی
   - هم مترادف‌ها را در نظر بگیرید

3. **دستورالعمل‌ها**: دستورالعمل‌های سیستم را واضح و دقیق بنویسید
   - محدودیت‌ها را مشخص کنید
   - نحوه استفاده از ابزارها را توضیح دهید

4. **ابزارها**: فقط ابزارهای لازم را اضافه کنید
   - هر ابزار اضافی پیچیدگی و هزینه را افزایش می‌دهد

### ⚠️ هشدارها

1. **حریم خصوصی**: برای داده‌های حساس، `auto_delete_sensitive_fields: true` تنظیم کنید

2. **مدل**: از مدل مناسب برای کار استفاده کنید
   - برای کارهای پیچیده: `gemini-2.5-flash-preview`
   - برای پاسخ‌های سریع: `gemini-2.5-flash-lite-preview`

3. **Temperature**: 
   - برای پاسخ‌های دقیق: `0.3-0.5`
   - برای پاسخ‌های خلاقانه: `0.7-0.9`

4. **تست**: همیشه بعد از افزودن عامل جدید، تست کامل انجام دهید

---

## رفع مشکلات رایج

### مشکل ۱: عامل ثبت نمی‌شود

**علت**: خطا در فایل YAML یا مسیر فایل

**راه حل**:
- بررسی فرمت YAML با یک YAML validator
- بررسی مسیر فایل در `persona_configs`
- بررسی لاگ‌ها برای خطاهای خاص

### مشکل ۲: ارکستر عامل را پیدا نمی‌کند

**علت**: عامل در فهرست `route_to_agent` یا قوانین هدایت نیست

**راه حل**:
- بررسی `orchestrator.yaml` برای وجود عامل در فهرست
- بررسی کلمات کلیدی در قوانین هدایت
- تست مستقیم عامل (بدون ارکستر)

### مشکل ۳: ابزار کار نمی‌کند

**علت**: ابزار به درستی ثبت نشده یا handler وجود ندارد

**راه حل**:
- بررسی ثبت ابزار در `ToolRegistry`
- بررسی وجود handler در `chat_agent.py`
- بررسی لاگ‌ها برای خطاهای ابزار

### مشکل ۴: عامل پاسخ نمی‌دهد

**علت**: مشکل در API key یا مدل

**راه حل**:
- بررسی `LITELLM_API_KEY` در environment variables
- بررسی لاگ‌ها برای خطاهای API
- تست با عامل دیگر برای اطمینان از کارکرد کلی سیستم

---

## خلاصه مراحل

1. ✅ ایجاد فایل YAML در `config/personalities/`
2. ✅ افزودن به `persona_configs` در `main.py`
3. ✅ تعریف ابزارها در `persona_tool_assignments` (اگر نیاز است)
4. ✅ به‌روزرسانی `orchestrator.yaml`:
   - افزودن به فهرست عوامل متخصص
   - افزودن قوانین هدایت
   - به‌روزرسانی `route_to_agent` tool description
5. ✅ ساخت و راه‌اندازی مجدد
6. ✅ تست و بررسی

---

## منابع و مراجع

- **فایل‌های نمونه**:
  - `services/chat-service/config/personalities/konesh_expert.yaml`
  - `services/chat-service/config/personalities/orchestrator.yaml`
  
- **کدهای مرجع**:
  - `services/chat-service/main.py` - ثبت عوامل
  - `services/chat-service/tools/konesh_query.py` - مثال ابزار سفارشی
  - `services/chat-service/tools/agent_router.py` - هدایت درخواست‌ها

---

## سوالات متداول

**سوال**: آیا می‌توانم چندین ابزار برای یک عامل تعریف کنم؟
**پاسخ**: بله، در `persona_tool_assignments` یک لیست از نام ابزارها قرار دهید.

**سوال**: آیا باید همه عوامل را در ارکستر ثبت کنم؟
**پاسخ**: فقط عوامل متخصص را که می‌خواهید ارکستر بتواند به آن‌ها هدایت کند.

**سوال**: آیا می‌توانم یک عامل را از ارکستر حذف کنم؟
**پاسخ**: بله، فقط آن را از `orchestrator.yaml` حذف کنید.

**سوال**: آیا باید بعد از هر تغییر کانتینر را rebuild کنم؟
**پاسخ**: برای تغییرات در کد Python یا فایل‌های YAML، بله. برای تغییرات فقط در environment variables، restart کافی است.

---

**نویسنده**: AI Platform Development Team  
**تاریخ به‌روزرسانی**: ۱۴۰۳/۱۰/۰۴  
**نسخه**: 1.0

