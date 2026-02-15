# راهنمای دستیار تولید محتوای عمومی (بدون نیاز به ورود)
# Public Content Generator Guide (No Login Required)

تاریخ: 1404/11/26 (2026-02-15)

---

## 📋 خلاصه

این راهنما نحوه استفاده از دستیار تولید محتوای قرآنی **بدون نیاز به ورود کاربر** را توضیح می‌دهد.

### ویژگی‌های کلیدی:
- ✅ بدون نیاز به ثبت‌نام یا ورود
- ✅ استفاده از همان Chat.html موجود
- ✅ دسترسی عمومی به تولید محتوا
- ✅ استفاده ساده با iframe
- ✅ مناسب برای نمایش در صفحات عمومی

---

## 🔗 URL های دسترسی عمومی

از همان `Chat.html` موجود استفاده می‌شود، با مسیرهای خاص:

### روش 1: مسیر اختصاصی تولید محتوا
```
https://safrainai.pish.run/ui?path=/content-generator
```

### روش 2: مسیر جایگزین
```
https://safrainai.pish.run/ui?path=/ai-content
```

### روش 3: فایل HTML Wrapper (اختیاری)
از فایل `ContentGenerator_Iframe.html` استفاده کنید که در پوشه `ai_platform/` موجود است.

---

## 🎯 نحوه استفاده

### روش A: Iframe مستقیم (ساده‌ترین روش) ⭐ توصیه می‌شود

```html
<!-- دسترسی عمومی به Content Generator - استفاده از Chat.html موجود -->
<iframe
    src="https://safrainai.pish.run/ui?path=/content-generator"
    style="width: 100%; height: 700px; border: none; border-radius: 15px;"
    allow="microphone; camera"
    title="دستیار تولید محتوای قرآنی">
</iframe>
```

**مزایا:**
- ✅ نیازی به کد اضافه نیست
- ✅ از همان Chat.html موجود استفاده می‌کند
- ✅ بدون نیاز به user ID کار می‌کند
- ✅ مستقیماً به content_generation_expert متصل می‌شود

### روش B: صفحه Wrapper (اختیاری)

اگر می‌خواهید یک صفحه زیباتر با header و styling داشته باشید:

1. از فایل `ContentGenerator_Iframe.html` استفاده کنید
2. در صورت نیاز، URL سرور را در iframe به‌روزرسانی کنید
3. آپلود در سرور خود

---

## 🔧 تنظیمات فنی

### 1. مسیرهای پشتیبانی‌شده

در فایل `config/path_agent_mapping.yaml`:

```yaml
- path: "/content-generator"
  agent: "content_generation_expert"
  description: "Public content generator - تولید محتوای عمومی (بدون نیاز به ورود)"

- path: "/ai-content"
  agent: "content_generation_expert"
  description: "AI content creation - دستیار تولید محتوا (دسترسی عمومی)"
```

### 2. مسیرهای عمومی در Backend

مسیرهای زیر نیازی به `user_id` ندارند:
- `/content-generator`
- `/ai-content`

کد در `main.py`:
```python
# Allow missing user_id for public content generator paths
public_paths = ['/content-generator', '/ai-content']
is_public_path = any(path.startswith(p) for p in public_paths)

if not user_id and not is_public_path:
    raise HTTPException(400, "Either encrypted_param or user_id must be provided")
```

### 3. نحوه کار در پشت صحنه

وقتی از `Chat.html` با `path=/content-generator` استفاده می‌کنید:

#### مرحله 1: Chat.html بارگذاری می‌شود
- فایل `Chat.html` موجود بارگذاری می‌شود (بدون نیاز به فایل جدید)
- از URL، path را استخراج می‌کند: `/content-generator`

#### مرحله 2: Initialize Session (بدون user_id)

```javascript
POST /chat/init
Content-Type: application/json

{
  "path": "/content-generator"
  // Note: No user_id or encrypted_param needed!
}
```

**Backend:**
- مسیر `/content-generator` را بررسی می‌کند
- تشخیص می‌دهد که این مسیر عمومی است (نیازی به user_id ندارد)
- به `content_generation_expert` متصل می‌شود

**پاسخ:**
```json
{
  "session_id": "uuid-here",
  "agent_key": "content_generation_expert",
  "user_data": {},
  "welcome_message": "سلام! من دستیار تولید محتوای قرآنی هستم..."
}
```

#### مرحله 3: ارسال پیام

```javascript
POST /chat/content_generation_expert/stream
Content-Type: application/json

{
  "message": "برای محفل خانگی محتوا تولید کن",
  "session_id": "session_id_from_init",
  "use_shared_context": true
}
```

**پاسخ:**
```
data: {"chunk": "محتوای", "session_id": "..."}
data: {"chunk": " تولید", "session_id": "..."}
data: {"chunk": " شده...", "session_id": "..."}
data: [DONE]
```

---

## 📊 مقایسه: دسترسی عمومی vs احراز هویت شده

| ویژگی | دسترسی عمومی | احراز هویت شده |
|------|-------------|---------------|
| نیاز به ورود | ❌ خیر | ✅ بله |
| User ID | ❌ ندارد | ✅ دارد |
| شخصی‌سازی | محدود | کامل |
| دسترسی به تاریخچه | ❌ خیر | ✅ بله |
| ذخیره محتوا | ❌ خیر | ✅ بله |
| امتیازدهی | ❌ خیر | ✅ بله |

---

## 🎨 مثال‌های کاربردی

### مثال 1: قرار دادن در صفحه معرفی

```html
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>دستیار تولید محتوا - سفیران آیه‌ها</title>
</head>
<body>
    <div class="container">
        <h1>🌟 دستیار هوشمند تولید محتوای قرآنی</h1>
        <p>تولید محتوا برای کنش‌های سفیران آیه‌ها، بدون نیاز به ثبت‌نام</p>
        
        <!-- Content Generator Iframe -->
        <iframe
            src="https://safrainai.pish.run/ui?path=/content-generator"
            style="width: 100%; height: 700px; border: none; border-radius: 15px;"
            allow="microphone; camera">
        </iframe>
    </div>
</body>
</html>
```

### مثال 2: استفاده در CMS (WordPress, Joomla, etc.)

```html
<!-- Shortcode برای WordPress -->
[iframe src="https://safrainai.pish.run/ui?path=/content-generator" 
        width="100%" 
        height="700" 
        allow="microphone; camera"]
```

### مثال 3: Embed در صفحات Notion یا Wiki

```markdown
<iframe 
  src="https://safrainai.pish.run/ui?path=/content-generator" 
  width="100%" 
  height="700px" 
  frameborder="0">
</iframe>
```

---

## 🔐 امنیت و محدودیت‌ها

### محدودیت‌های دسترسی عمومی:
1. **هر Session مستقل است** - تاریخچه گفتگو ذخیره نمی‌شود
2. **بدون شخصی‌سازی** - اطلاعات کاربر در دسترس نیست
3. **محدودیت Rate Limit** - برای جلوگیری از سوء استفاده
4. **عدم دسترسی به API های خصوصی** - مثل ذخیره محتوا، امتیازات

### توصیه‌های امنیتی:
- استفاده از HTTPS اجباری است
- Rate limiting برای جلوگیری از spam
- Monitoring استفاده عمومی

---

## 🚀 تست و عیب‌یابی

### چک کردن دسترسی:

```bash
# تست init endpoint بدون user_id
curl -X POST https://safrainai.pish.run/chat/init \
  -H "Content-Type: application/json" \
  -d '{"path": "/content-generator"}'

# باید session_id برگرداند بدون خطا
```

### خطاهای رایج:

1. **Error 400: user_id required**
   - **حل:** مطمئن شوید path به درستی تنظیم شده (`/content-generator`)

2. **No welcome message**
   - **حل:** نرمال است، پیام خوش‌آمدگویی اختیاری است

3. **CORS error در مرورگر**
   - **حل:** بررسی تنظیمات CORS در backend

---

## 📞 پشتیبانی

در صورت بروز مشکل:
1. بررسی Console مرورگر برای خطاها
2. تست endpoint با `curl` یا Postman
3. بررسی لاگ‌های سرور
4. تماس با تیم فنی سفیران آیه‌ها

---

## 📝 تغییرات نسخه

### نسخه 1.0 (1404/11/26)
- ✅ اضافه شدن دسترسی عمومی به Content Generator
- ✅ مسیرهای `/content-generator` و `/ai-content`
- ✅ فایل مثال HTML مستقل
- ✅ پشتیبانی از session های بدون user_id

---

## 🌟 نمونه کد کامل JavaScript

```javascript
// Initialize public content generator
async function initPublicContentGenerator() {
    const API_BASE = 'https://safrainai.pish.run';
    
    try {
        // Step 1: Initialize session (no user_id)
        const initResponse = await fetch(`${API_BASE}/chat/init`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: '/content-generator' })
        });
        
        const { session_id, welcome_message } = await initResponse.json();
        console.log('Session:', session_id);
        console.log('Welcome:', welcome_message);
        
        // Step 2: Send a message
        const chatResponse = await fetch(`${API_BASE}/chat/content_generation_expert`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: 'برای محفل خانگی محتوا تولید کن',
                session_id: session_id,
                use_shared_context: true
            })
        });
        
        const { output } = await chatResponse.json();
        console.log('Response:', output);
        
    } catch (error) {
        console.error('Error:', error);
    }
}

// Run it
initPublicContentGenerator();
```

---

**© 2026 سفیران آیه‌ها - تمام حقوق محفوظ است**
