# راهنمای تطابق با وب‌سرویس AI سفیران

**تاریخ:** 2026-02-12  
**هدف:** مقایسه مستند رسمی سفیران با پیاده‌سازی فعلی و طرح Safiran API Integration

---

## خلاصه تطابق

| مورد | سند رسمی | پیاده‌سازی فعلی | وضعیت |
|------|----------|-----------------|--------|
| پارامتر رمز‌گذاری | URL با `{AES_JSON_QUERY_PARAM}` | `encrypted_param` در body/query | ✅ منطبق |
| فیلدهای JSON رمز‌گشایی | `UserId`, `Path` | `UserId`, `Path` | ✅ منطبق |
| الگوریتم AES | AES CBC | AES CBC | ✅ منطبق |
| Key | `DLwXJz9yzC7Kk2J1M0Brp7snLTUEY1Fg` | همین مقدار | ✅ منطبق |
| IV | `nqcWgiLLZWJaFkZi` | همین مقدار | ✅ منطبق |
| لاگین | **POST** با query params | GET, POST JSON, POST form, **POST query** | ⚠️ ترتیب: POST query چهارم است |
| GetAIUserData | GET با UserId + Bearer | GET با UserId + Bearer | ✅ منطبق |
| پارامتر اضافی | قابلیت اضافه کردن وجود دارد | `from_path` برای صفحه مبدا | ✅ گسترش منطقی |

---

## جزئیات تطابق

### 1. URL و پارامتر رمز‌گذاری

**سند رسمی:**
> ابتدا شما باید یک url که 1 پارامتر ورودی متنی دارد را برای ما ارسال نمایید.  
> مانند: https://sample.ir/{AES_JSON_QUERY_PARAM}

**پیاده‌سازی:**
- درخواست `POST /chat/init` با `encrypted_param` در body (یا query) پذیرفته می‌شود
- `encrypted_param` همان `AES_JSON_QUERY_PARAM` است
- فرمت URL سایت: `https://.../ai?encrypted_param={value}` یا ارسال در body

**وضعیت:** منطبق. تفاوت در نحوه ارسال (query vs body) که هر دو قابل پشتیبانی است.

---

### 2. فیلدهای JSON رمز‌گشایی شده

**سند رسمی:**
> پارامتر های json رمز شده ورودی:
> 1. UserId: شماره کاربری که روی لینک AI کلیک کرده
> 2. Path: مسیری که کاربر از انجا به سمت AI هدایت شده
> *تذکر: قابلیت اضافه کردن پارامترهای دیگر وجود دارد*

**پیاده‌سازی:**
- `decrypt_safiranayeha_param()` خروجی `{UserId, Path}` برمی‌گرداند
- `user_id = decrypted_data.get('UserId')`
- `path = decrypted_data.get('Path', '/')`
- پارامتر `from_path` به‌طور جداگانه از فرانت‌اند ارسال می‌شود (صفحه‌ای که کاربر واقعاً از آنجا آمده، مثلاً `/actions/40`)

**وضعیت:** منطبق. استفاده از `from_path` گسترش مجاز سند است.

---

### 3. رمز‌گشایی AES

**سند رسمی:**
> - الگوریتم: AES  
> - Key: "DLwXJz9yzC7Kk2J1M0Brp7snLTUEY1Fg"  
> - IV: "nqcWgiLLZWJaFkZi"  
> - URL decode → Base64 decode → AES decrypt → JSON parse

**پیاده‌سازی** ([utils/crypto.py](services/chat-service/utils/crypto.py)):
- Key و IV عیناً مطابق سند
- مراحل: `unquote()` → `base64.b64decode()` → `AES.new(..., MODE_CBC)` → `unpad()` → `json.loads()`

**وضعیت:** منطبق.

---

### 4. لاگین

**سند رسمی:**
> جهت لاگین از سرویس زیر استفاده شود (**متد POST**)  
> https://api.safiranayeha.ir/api/AI/AILogin?username={your_username}&password={your_pass}  
> مقدار بازگشتی: JWT token

**پیاده‌سازی** ([integrations/safiranayeha_client.py](services/chat-service/integrations/safiranayeha_client.py)):
- ترتیب تلاش‌ها: 1) GET query, 2) POST JSON, 3) POST form, 4) **POST query**
- سند فقط POST با query params را ذکر کرده؛ در کد POST query چهارمین گزینه است.
- Swagger API نشان می‌داد متد PATCH، اما سند رسمی **POST** را می‌گوید.

**توصیه:** ترتیب را طوری تغییر دهید که **اول POST با query params** امتحان شود تا با سند رسمی هم‌خوان باشد.

---

### 5. GetAIUserData

**سند رسمی:**
> - متد GET  
> - https://api.safiranayeha.ir/api/AI/GetAIUserData?UserId={user_id}  
> - توکن در هدر: Authorization=bearer {your token}

**پیاده‌سازی:**
- `GET` با `params={"UserId": user_id}`
- هدر: `Authorization: Bearer {token}`

**وضعیت:** منطبق.

---

## نکات برای طرح Safiran API Integration

### 1. اصلاح طرح: لاگین PATCH نیست

در طرح قبلی گفته شده بود:
> Swagger shows AILogin uses **PATCH**, not GET/POST  
> Add PATCH to login_methods

**سند رسمی** صریحاً **POST** با query params را مشخص می‌کند. بنابراین:
- PATCH اضافه نکنید
- به‌جای آن **اول POST با query params** را امتحان کنید

### 2. سایر endpointها (GetOneAction، GetMyActions، GetContentList)

سند فقط AILogin و GetAIUserData را شرح می‌دهد. endpointهای دیگر از Swagger API استخراج شده‌اند و احتمالاً:
- همان توکن Bearer را نیاز دارند
- همان base URL (`https://api.safiranayeha.ir`) را استفاده می‌کنند

### 3. نوع UserId

- سند: `UserId` به‌صورت عدد کاربری
- Swagger GetAIUserData: `UserId` از نوع `int64`
- در `get_user_data` ما `params={"UserId": user_id}` ارسال می‌کنیم

اگر API نوع عددی انتظار دارد، ممکن است لازم باشد `user_id` را به `int` تبدیل کنیم. فعلاً به‌صورت string ارسال می‌شود؛ در صورت خطا باید تبدیل نوع اضافه شود.

---

## خلاصه تغییرات پیشنهادی

1. **ترتیب login_methods:**  
   POST با query params را **اولین** روش امتحان کنید (مطابق سند رسمی).

2. **حذف PATCH:**  
   در طرح Safiran API Integration، بخش «Fix Authentication» را طوری به‌روز کنید که PATCH حذف شده و به‌جای آن اولویت با POST query params باشد.

3. **باقی طرح:**  
   بدون تغییر. رمز‌گشایی، GetAIUserData، و پارامترهای اضافی (مثل `from_path`) با سند هم‌خوان هستند.
