# پشتیبانی از پارامتر `from` در URL

## خلاصه

سیستم اکنون از پارامتر `from` در URL چت پشتیبانی می‌کند. این پارامتر نشان می‌دهد کاربر از کدام صفحه به چت آمده است.

## مثال استفاده

### سناریو

1. کاربر در حال دیدن صفحه `/actions/40` است (صفحه یک کنش خاص)
2. کاربر روی دکمه "چت هوشمند" کلیک می‌کند
3. URL چت می‌شود: `https://safiranayeha.ir/ai?from=%2Factions%2F40`
4. سیستم می‌داند کاربر از صفحه `/actions/40` آمده

### جریان

```
/actions/40 (صفحه کنش)
    ↓
کلیک روی "چت هوشمند"
    ↓
/ai?from=%2Factions%2F40
    ↓
Chat.html می‌خواند from parameter
    ↓
POST /chat/init { from_path: "/actions/40" }
    ↓
entry_path = "/actions/40" در context ذخیره می‌شود
    ↓
ایجنت می‌داند کاربر در حال دیدن کنش #40 است
```

## تغییرات انجام شده

### 1. Chat.html

**فایل**: `Chat.html`

```javascript
// Extract 'from' parameter
const urlParams = new URLSearchParams(window.location.search);
const fromParam = urlParams.get('from');

// Pass to init endpoint
body: JSON.stringify({
    encrypted_param: encryptedParam,
    from_path: fromParam ? decodeURIComponent(fromParam) : null
})
```

- خواندن پارامتر `from` از URL
- URL decode کردن مقدار (چون `%2Factions%2F40` = `/actions/40`)
- ارسال به endpoint به عنوان `from_path`

### 2. Gateway API

**فایل**: `services/gateway/main.py`

```python
class ChatInitRequest(BaseModel):
    encrypted_param: Optional[str] = None
    user_id: Optional[str] = None
    path: Optional[str] = None
    from_path: Optional[str] = None  # NEW: Page user came from
```

- افزودن فیلد `from_path` به request model

### 3. Chat Service

**فایل**: `services/chat-service/main.py`

```python
# Step 1.5: Use 'from_path' if provided
entry_path = request.from_path if request.from_path else path
if request.from_path:
    logging.info(f"User came from page: {request.from_path}")

# Save entry_path to context
normalized_user_data["entry_path"] = {"value": entry_path}
```

- استفاده از `from_path` به عنوان `entry_path` (اولویت بالاتر از `path`)
- ذخیره در context برای استفاده در پرامپت

### 4. Path Context Helper

**فایل**: `shared/path_context_helper.py`

```python
# Check if path contains action ID (e.g., /actions/40)
if "/actions/" in display_path:
    match = re.search(r'/actions/(\d+)', display_path)
    if match:
        action_id = match.group(1)
        context_text += f"\n⚠️ مهم: کاربر در حال دیدن کنش شماره {action_id} است."
```

- تشخیص ID کنش از path (مثلاً `/actions/40` → کنش #40)
- افزودن هشدار به context که کاربر در حال دیدن یک کنش خاص است

## مثال Context در پرامپت

### برای `/actions/40`:

```
📍 کاربر چت را از صفحه «سفیران آیه‌ها - فرم ثبت گزارش انجام اقدامات برای دریافت امتیاز.» (/actions/40) باز کرده است.
⚠️ مهم: کاربر در حال دیدن کنش شماره 40 است.
این یعنی کاربر احتمالاً در حال دیدن این صفحه است و ممکن است به محتوای این صفحه اشاره کند (مثلاً «همین کنش»، «این صفحه»، «اینجا»).
وقتی کاربر می‌گوید «همین» یا «این»، منظور او احتمالاً محتوای همین صفحه است.
```

### برای `/action-list`:

```
📍 کاربر چت را از صفحه «لیست کنش‌ها» (/action-list) باز کرده است.
این یعنی کاربر احتمالاً در حال دیدن این صفحه است و ممکن است به محتوای این صفحه اشاره کند (مثلاً «همین کنش»، «این صفحه»، «اینجا»).
وقتی کاربر می‌گوید «همین» یا «این»، منظور او احتمالاً محتوای همین صفحه است.
```

## اولویت

1. **`from_path`** (اگر موجود باشد) - دقیق‌ترین: صفحه‌ای که کاربر واقعاً از آن آمده
2. **`path` از encrypted_param** (fallback) - مسیر iframe

## تست

### تست دستی

1. باز کردن `/actions/40` در مرورگر
2. کلیک روی لینک به `/ai?from=/actions/40`
3. بررسی لاگ‌ها:
   ```
   INFO: User came from page: /actions/40 (iframe path was: /ai)
   INFO: Saved entry_path '/actions/40' to context
   ```
4. ارسال پیام: "همین کنش"
5. ایجنت باید بداند منظور کاربر کنش #40 است

### تست با curl

```bash
curl -X POST "http://localhost:8003/chat/init" \
  -H "Content-Type: application/json" \
  -d '{
    "encrypted_param": "...",
    "from_path": "/actions/40"
  }'
```

## فایل‌های تغییر یافته

1. ✅ `Chat.html` - خواندن `from` parameter
2. ✅ `services/gateway/main.py` - افزودن `from_path` به request model
3. ✅ `services/chat-service/main.py` - استفاده از `from_path` به عنوان `entry_path`
4. ✅ `shared/path_context_helper.py` - تشخیص action ID از path

## نتیجه

ایجنت‌ها اکنون:
- ✅ می‌دانند کاربر از کدام صفحه دقیق آمده (نه فقط مسیر iframe)
- ✅ می‌توانند تشخیص دهند کاربر در حال دیدن یک کنش خاص است (مثلاً کنش #40)
- ✅ می‌توانند به «همین کنش» پاسخ صحیح بدهند
