# 🎯 آموزش کامل: ساخت Orchestrator Agent

## 📚 فهرست

1. [مفهوم Orchestrator](#مفهوم-orchestrator)
2. [فایل‌های ایجاد شده](#فایلهای-ایجاد-شده)
3. [مراحل پیاده‌سازی](#مراحل-پیادهسازی)
4. [تست و اجرا](#تست-و-اجرا)
5. [نمونه‌های کاربردی](#نمونههای-کاربردی)
6. [عیب‌یابی](#عیبیابی)

---

## 🎭 مفهوم Orchestrator

### چیه؟
Orchestrator یک عامل هوشمند هماهنگ‌کننده است که:
- پیام کاربر را **تحلیل** می‌کنه
- تشخیص میده کدوم متخصص باید جواب بده
- **خودکار** درخواست رو به متخصص مناسب ارجاع میده
- پاسخ متخصص رو به کاربر برمی‌گردونه

### چرا مفیده؟
✅ کاربر نیازی نداره بدونه کدوم Agent رو انتخاب کنه
✅ مسیریابی هوشمند و خودکار
✅ تجربه کاربری بهتر
✅ یک نقطه ورود برای همه درخواست‌ها

### معماری:

```
                    کاربر
                      ↓
              [Orchestrator Agent]
               (تحلیل و تصمیم)
                      ↓
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
    [Doctor]      [Tutor]      [Default]
    پزشکی         آموزشی        عمومی
```

---

## 📁 فایل‌های ایجاد شده

من برات این فایل‌ها رو ساختم:

### 1. **Config فایل Orchestrator**
```
ai_platform/services/chat-service/config/personalities/orchestrator.yaml
```
شامل:
- System prompt برای تحلیل پیام‌ها
- قوانین مسیریابی
- تنظیمات مدل (temperature: 0.3 برای تصمیم‌گیری ثابت)

### 2. **ابزار Routing**
```
ai_platform/services/chat-service/tools/agent_router.py
```
شامل:
- `AgentRouterTool`: ابزار اصلی مسیریابی
- `AgentRouterToolSync`: نسخه سینک برای سازگاری با pydantic-ai

### 3. **راهنمای یکپارچه‌سازی**
```
ai_platform/ORCHESTRATOR_SETUP.md
```
مستندات کامل انگلیسی

### 4. **نمونه کد کامل**
```
ai_platform/orchestrator_integration_example.py
```
کد دقیق تغییرات در main.py

### 5. **اسکریپت تست**
```
ai_platform/test_orchestrator.py
```
تست خودکار برای بررسی مسیریابی

---

## 🛠️ مراحل پیاده‌سازی

### قدم 1: بررسی فایل‌های ایجاد شده

همه فایل‌ها آماده هستند! فقط باید `main.py` رو تغییر بدی.

### قدم 2: تغییر main.py

باز کن:
```
ai_platform/services/chat-service/main.py
```

#### 2.1: اضافه کردن Import

در خط ~29 (بعد از import های tools):
```python
from tools.agent_router import AgentRouterToolSync
```

#### 2.2: اضافه کردن کلاس Wrapper

قبل از `@app.on_event("startup")` (حدود خط 180):
```python
class RouterToolWrapper:
    """Wrapper to make routing tool compatible with Tool interface"""

    def __init__(self, router):
        self.router = router
        self._enabled = True

    @property
    def name(self) -> str:
        return "route_to_agent"

    @property
    def description(self) -> str:
        return self.router.description

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "agent_key": {
                    "type": "string",
                    "description": "Specialist agent key",
                    "enum": ["doctor", "tutor", "professional", "default", "minimal"]
                },
                "user_message": {
                    "type": "string",
                    "description": "User's message to forward"
                }
            },
            "required": ["agent_key", "user_message"]
        }

    async def execute(self, agent_key: str, user_message: str, session_id: str = None) -> str:
        return self.router.run(agent_key, user_message, session_id)
```

#### 2.3: تغییر Startup Function

پیدا کن این خط (حدود 261):
```python
persona_configs = {
    "default": "agent_config.yaml",
    "tutor": "personalities/friendly_tutor.yaml",
    "professional": "personalities/professional_assistant.yaml",
    "minimal": "personalities/minimal_assistant.yaml",
}
```

تبدیل کن به:
```python
persona_configs = {
    "default": "agent_config.yaml",
    "tutor": "personalities/friendly_tutor.yaml",
    "professional": "personalities/professional_assistant.yaml",
    "minimal": "personalities/minimal_assistant.yaml",
    "orchestrator": "personalities/orchestrator.yaml",  # ✅ اضافه شد
}
```

#### 2.4: تغییر حلقه ثبت Agents

کل حلقه `for agent_key, config_path in persona_configs.items():` رو جایگزین کن با کد تو فایل:
```
orchestrator_integration_example.py
```

یا به صورت خلاصه:

```python
# PASS 1: ثبت Agents تخصصی (بدون orchestrator)
for agent_key, config_path in persona_configs.items():
    if agent_key == "orchestrator":  # رد کن
        continue

    # ... کد ثبت agent معمولی ...
    AGENTS[agent_key] = agent
    AGENT_CONFIGS[agent_key] = persona_config

# PASS 2: ثبت Orchestrator با ابزار routing
if "orchestrator" in persona_configs:
    # ساخت ابزار routing
    routing_tool_core = AgentRouterToolSync(AGENTS, context_manager)
    routing_tool = RouterToolWrapper(routing_tool_core)

    # ثبت orchestrator با این ابزار
    orchestrator_agent = ChatAgent(
        orchestrator_agent_config,
        context_manager,
        orchestrator_persona_config,
        custom_tools=[routing_tool]
    )

    await orchestrator_agent.initialize(http_client)
    AGENTS["orchestrator"] = orchestrator_agent
```

**مهم**: کد کامل رو از `orchestrator_integration_example.py` کپی کن!

---

## 🧪 تست و اجرا

### قدم 1: Build و راه‌اندازی

```bash
cd ai_platform
docker-compose down
docker-compose up -d --build
```

### قدم 2: چک کردن لاگ‌ها

```bash
docker-compose logs -f chat-service
```

باید ببینی:
```
✅ Registered 'default': Default Chat Agent with 3 tools
✅ Registered 'tutor': Friendly Tutor with 3 tools
✅ Registered 'professional': Professional Assistant with 4 tools
✅ Registered 'minimal': Minimal Assistant with 0 tools
✅ Registered orchestrator with routing to 4 specialists
```

### قدم 3: تست دستی

#### تست 1: پزشکی (باید به doctor برود)
```bash
curl -X POST http://localhost:8000/chat/orchestrator \
  -H "Content-Type: application/json" \
  -d '{
    "message": "سلام، سردرد دارم و تب کردم",
    "session_id": null
  }'
```

#### تست 2: آموزشی (باید به tutor برود)
```bash
curl -X POST http://localhost:8000/chat/orchestrator \
  -H "Content-Type: application/json" \
  -d '{
    "message": "می‌خوام ریاضی یاد بگیرم",
    "session_id": null
  }'
```

#### تست 3: قرآنی (باید به default برود)
```bash
curl -X POST http://localhost:8000/chat/orchestrator \
  -H "Content-Type: application/json" \
  -d '{
    "message": "درباره آیه 12 بگو",
    "session_id": null
  }'
```

### قدم 4: تست خودکار

```bash
cd ai_platform
python test_orchestrator.py
```

این اسکریپت:
- ✅ 9 سناریو مختلف رو تست می‌کنه
- ✅ چک می‌کنه routing درست کار می‌کنه
- ✅ گزارش کامل میده

---

## 💡 نمونه‌های کاربردی

### مثال 1: کاربر نمی‌دونه کجا بره

**قبل از Orchestrator:**
```
کاربر: "سردرد دارم" → به کدوم agent بفرستم؟ 🤔
→ اشتباهی به tutor می‌فرسته
→ tutor جواب نامرتبط میده ❌
```

**با Orchestrator:**
```
کاربر: "سردرد دارم" → به orchestrator می‌فرسته
→ Orchestrator تشخیص میده: موضوع پزشکی
→ خودکار به doctor ارجاع میده
→ Doctor جواب صحیح میده ✅
```

### مثال 2: مکالمه پیوسته

```
کاربر: "سلام، من علی هستم"
Orchestrator → Default Agent
پاسخ: "سلام علی! چطور می‌تونم کمکت کنم؟"

کاربر: "سردرد دارم"
Orchestrator → Doctor Agent
پاسخ: "سلام علی! خوب، بذار درباره سردردت صحبت کنیم..."
                ↑
            اسم رو یادش موند!
```

### مثال 3: موضوعات مختلف در یک session

```bash
# پیام 1: مذهبی
POST /chat/orchestrator
{"message": "آیه 12 چیه؟"}
→ Routes to: default

# پیام 2: پزشکی (همون session)
POST /chat/orchestrator
{"message": "سردرد دارم", "session_id": "..."}
→ Routes to: doctor

# پیام 3: آموزشی (همون session)
POST /chat/orchestrator
{"message": "ریاضی یاد بده", "session_id": "..."}
→ Routes to: tutor
```

همه در یک گفتگو! 🎉

---

## 🔍 عیب‌یابی

### مشکل 1: Orchestrator ثبت نمیشه

**علامت:**
```
❌ Failed to load orchestrator: ...
```

**راه‌حل:**
1. چک کن فایل وجود داره:
   ```bash
   ls -la ai_platform/services/chat-service/config/personalities/orchestrator.yaml
   ```

2. چک کن import درسته:
   ```bash
   docker-compose logs chat-service | grep "import"
   ```

### مشکل 2: routing_tool پیدا نمیشه

**علامت:**
```
NameError: name 'AgentRouterToolSync' is not defined
```

**راه‌حل:**
1. مطمئن شو import اضافه شده:
   ```python
   from tools.agent_router import AgentRouterToolSync
   ```

2. چک کن فایل وجود داره:
   ```bash
   ls -la ai_platform/services/chat-service/tools/agent_router.py
   ```

### مشکل 3: Routing اشتباه کار می‌کنه

**علامت:**
پیام پزشکی به tutor میره!

**راه‌حل:**
1. چک کن system prompt در `orchestrator.yaml`:
   ```yaml
   system_prompt: |
     # ... قوانین routing ...
   ```

2. Temperature رو کم کن:
   ```yaml
   model_config:
     temperature: 0.2  # از 0.3 کمتر کن
   ```

3. کلمات کلیدی بیشتر اضافه کن در system prompt

### مشکل 4: Context حفظ نمیشه

**علامت:**
Agent اسم کاربر رو فراموش می‌کنه

**راه‌حل:**
مطمئن شو `use_shared_context: true` در request:
```python
{
    "message": "...",
    "session_id": "...",
    "use_shared_context": true  # ✅ این رو اضافه کن
}
```

---

## 🎓 یادگیری بیشتر

### مسیریابی پیشرفته

می‌تونی قوانین routing رو پیچیده‌تر کنی:

```yaml
# در orchestrator.yaml
system_prompt: |
  🔍 Advanced Routing:

  1. بر اساس تاریخچه:
     - اگر قبلاً با doctor صحبت کرده → ادامه با doctor
     - اگر در حال یادگیری → tutor

  2. بر اساس احساسات:
     - پیام عصبانی → professional (رسمی‌تر)
     - پیام شاد → tutor (گرم‌تر)

  3. بر اساس ترجیحات:
     - اگر user.preferred_agent تنظیم شده → همون

  4. چند موضوعی:
     - اگر پیام شامل چند موضوع → بپرس کدوم اولویت داره
```

### Routing با ML

برای پیشرفته‌تر:
1. جمع‌آوری داده‌های routing
2. ساخت مدل ML برای تشخیص موضوع
3. یکپارچه‌سازی مدل به جای prompt-based routing

---

## 📊 خلاصه

### چی ساختیم؟
✅ Orchestrator Agent که خودکار مسیریابی می‌کنه
✅ Routing Tool برای ارتباط بین agents
✅ سیستم تست کامل
✅ مستندات جامع

### مزایا:
✨ UX بهتر: کاربر نمی‌دونه کدوم agent رو انتخاب کنه
✨ Scalable: راحت می‌تونی agent جدید اضافه کنی
✨ Maintainable: تمام منطق routing در یه جا
✨ Flexible: هنوز میشه مستقیم با agents کار کرد

### مراحل پیاده‌سازی:
1. ✅ فایل‌ها ساخته شدن
2. 🔧 main.py رو تغییر بده (کپی از orchestrator_integration_example.py)
3. 🚀 rebuild و restart کن
4. 🧪 تست کن با test_orchestrator.py
5. 🎉 استفاده کن!

---

**موفق باشی! 🚀**

سوالی داشتی بپرس!
