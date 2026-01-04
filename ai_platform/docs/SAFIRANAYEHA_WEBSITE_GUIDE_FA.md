# راهنمای استفاده از چت هوشمند در وب‌سایت سفیران آیه‌ها

## مقدمه

این راهنما نحوه استفاده از چت هوشمند را در وب‌سایت سفیران آیه‌ها توضیح می‌دهد. با استفاده از این راهنما می‌توانید چت هوشمند را در صفحات مختلف وب‌سایت خود به صورت iframe قرار دهید.

---

## آدرس Endpoint چت

```text
https://safrainai.pish.run/ui
```

این endpoint **هم با پارامتر رمزگذاری‌شده** و **هم بدون پارامتر** قابل استفاده است.

---

## مراحل استفاده

### 1. رمزگذاری اطلاعات کاربر (اختیاری)

برای استفاده از چت با کانتکست کاربر و انتخاب هوشمند عامل، باید اطلاعات کاربر را رمزگذاری کنید:

#### اطلاعات مورد نیاز:

- **UserId**: شناسه کاربر
- **Path**: مسیر صفحه فعلی (مثلاً `/konesh/list`)

#### مثال رمزگذاری در C#:

```csharp
using System;
using System.Security.Cryptography;
using System.Text;
using System.Web;
using System.Text.Json;

public class SafiranayehaEncryption
{
    private static readonly string Key = "DLwXJz9yzC7Kk2J1M0Brp7snLTUEY1Fg";
    private static readonly string IV = "nqcWgiLLZWJaFkZi";

    public static string EncryptUserData(string userId, string path)
    {
        // ساخت JSON از اطلاعات
        var data = new
        {
            UserId = userId,
            Path = path
        };

        string json = JsonSerializer.Serialize(data);

        // رمزگذاری با AES-256-CBC
        using (var aes = Aes.Create())
        {
            aes.Key = Encoding.UTF8.GetBytes(Key);
            aes.IV = Encoding.UTF8.GetBytes(IV);
            aes.Mode = CipherMode.CBC;
            aes.Padding = PaddingMode.PKCS7;

            using (var encryptor = aes.CreateEncryptor())
            {
                byte[] encrypted = encryptor.TransformFinalBlock(
                    Encoding.UTF8.GetBytes(json),
                    0,
                    Encoding.UTF8.GetBytes(json).Length
                );

                // تبدیل به Base64 و سپس URL Encode
                string base64 = Convert.ToBase64String(encrypted);
                return HttpUtility.UrlEncode(base64);
            }
        }
    }
}
```

#### استفاده:

```csharp
string userId = "12345"; // شناسه کاربر از سیستم
string currentPath = "/konesh/list"; // مسیر صفحه فعلی
string encryptedParam = SafiranayehaEncryption.EncryptUserData(userId, currentPath);
```

---

### 2. قرار دادن چت در صفحه

چت را به صورت iframe در صفحه قرار دهید. سه روش مختلف برای این کار وجود دارد:

#### روش 1: استفاده بدون پارامتر (حالت عمومی / مهمان)

در این حالت چت بدون کانتکست کاربر و مسیر صفحه باز می‌شود (معمولاً با agent پیش‌فرض مثل `guest_faq` یا `orchestrator`):

```html
<iframe
  src="https://safrainai.pish.run/ui"
  width="100%"
  height="600px"
  frameborder="0"
  style="border: none; border-radius: 8px;"
  allow="microphone; camera"
>
</iframe>
```

**موارد استفاده پیشنهادی:**

- صفحات عمومی
- لندینگ پیج
- حالت تست
- کاربران مهمان

#### روش 2: استفاده از Query Parameter (پیشنهادی برای تولید)

در این حالت اطلاعات کاربر و مسیر صفحه به صورت رمزگذاری‌شده ارسال می‌شود و agent مناسب **هوشمندانه انتخاب می‌گردد**:

```html
<iframe
  src="https://safrainai.pish.run/ui?encrypted_param=@encryptedParam"
  width="100%"
  height="600px"
  frameborder="0"
  style="border: none; border-radius: 8px;"
  allow="microphone; camera"
>
</iframe>
```

✅ **این روش Recommended است** چون:

- کانتکست صفحه حفظ می‌شود
- agent درست انتخاب می‌شود
- تجربه کاربری دقیق‌تر است

#### روش 3: استفاده از Path Parameter (اختیاری)

```html
<iframe
  src="https://safrainai.pish.run/ui/@encryptedParam"
  width="100%"
  height="600px"
  frameborder="0"
  style="border: none; border-radius: 8px;"
  allow="microphone; camera"
>
</iframe>
```

⚠️ فقط در صورتی استفاده شود که routing سمت سرور برای path فعال باشد.

---

### جمع‌بندی سریع روش‌ها

| حالت           | URL                                                 | کاربرد                  |
| -------------- | --------------------------------------------------- | ----------------------- |
| بدون پارامتر   | `https://safrainai.pish.run/ui`                     | تست، مهمان، صفحات عمومی |
| با Query Param | `https://safrainai.pish.run/ui?encrypted_param=...` | **پیشنهادی / تولیدی**   |
| با Path Param  | `https://safrainai.pish.run/ui/{encrypted}`         | اختیاری                 |

**نکته مهم:** اگر `encrypted_param` ارسال نشود → سیستم به‌صورت امن fallback می‌کند و هیچ خطایی رخ نمی‌دهد.

---

### 3. مثال کامل در Razor (ASP.NET Core)

#### مثال با پارامتر (پیشنهادی):

```razor
@{
    string userId = User.Identity.Name; // یا از جلسه کاربر
    string currentPath = Context.Request.Path.Value;
    string encryptedParam = SafiranayehaEncryption.EncryptUserData(userId, currentPath);
}

<div class="chat-container">
    <iframe
        src="https://safrainai.pish.run/ui?encrypted_param=@encryptedParam"
        width="100%"
        height="600px"
        frameborder="0"
        style="border: none; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"
        allow="microphone; camera">
    </iframe>
</div>
```

#### مثال بدون پارامتر (برای صفحات عمومی):

```razor
<div class="chat-container">
    <iframe
        src="https://safrainai.pish.run/ui"
        width="100%"
        height="600px"
        frameborder="0"
        style="border: none; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"
        allow="microphone; camera">
    </iframe>
</div>
```

---

## استایل‌های پیشنهادی

برای نمایش بهتر چت در صفحه، می‌توانید از استایل‌های زیر استفاده کنید:

```css
.chat-container {
  width: 100%;
  max-width: 1200px;
  margin: 20px auto;
  padding: 20px;
}

.chat-container iframe {
  width: 100%;
  height: 600px;
  border: none;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* برای صفحات موبایل */
@media (max-width: 768px) {
  .chat-container iframe {
    height: 500px;
  }
}
```

---

## مسیرهای مختلف و عامل هوشمند

سیستم به صورت خودکار بر اساس مسیر صفحه، عامل هوشمند مناسب را انتخاب می‌کند:

| مسیر صفحه                      | عامل هوشمند        | توضیحات                         |
| ------------------------------ | ------------------ | ------------------------------- |
| `/`                            | `guest_faq`        | صفحه اصلی - راهنمای تازه‌واردان |
| `/faq`, `/help`, `/about`      | `guest_faq`        | صفحات اطلاعات عمومی             |
| `/konesh/*`, `/actions/*`      | `action_expert`    | صفحات کنش‌ها - تولید محتوا      |
| `/محفل/*`                      | `action_expert`    | صفحات محفل                      |
| `/profile/*`, `/register`      | `journey_register` | صفحات پروفایل و ثبت‌نام         |
| `/onboarding/*`, `/journey/*`  | `journey_register` | صفحات سفر کاربری                |
| `/rewards/*`, `/points/*`      | `rewards_invite`   | صفحات امتیازات                  |
| `/invite/*`, `/achievements/*` | `rewards_invite`   | صفحات دعوت و دستاوردها          |
| (سایر مسیرها)                  | `orchestrator`     | عامل پیش‌فرض                    |

**نکته مهم:** مسیر را به درستی در تابع رمزگذاری ارسال کنید تا عامل مناسب انتخاب شود.

---

## مثال‌های عملی

### مثال 1: صفحه لیست کنش‌ها

```csharp
// در صفحه /konesh/list
string userId = GetCurrentUserId();
string path = "/konesh/list";
string encrypted = EncryptUserData(userId, path);

// در HTML
<iframe src="https://safrainai.pish.run/ui?encrypted_param=@encrypted"></iframe>
```

**نتیجه:** چت با عامل `action_expert` باز می‌شود که برای تولید محتوای کنش‌ها تخصص دارد.

### مثال 2: صفحه پروفایل

```csharp
// در صفحه /profile/complete
string userId = GetCurrentUserId();
string path = "/profile/complete";
string encrypted = EncryptUserData(userId, path);

// در HTML
<iframe src="https://safrainai.pish.run/ui?encrypted_param=@encrypted"></iframe>
```

**نتیجه:** چت با عامل `journey_register` باز می‌شود که برای تکمیل پروفایل کمک می‌کند.

### مثال 3: صفحه اصلی

```csharp
// در صفحه اصلی
string userId = GetCurrentUserId(); // یا null برای کاربر مهمان
string path = "/";
string encrypted = EncryptUserData(userId, path);

// در HTML
<iframe src="https://safrainai.pish.run/ui?encrypted_param=@encrypted"></iframe>
```

**نتیجه:** چت با عامل `guest_faq` باز می‌شود که برای راهنمایی تازه‌واردان مناسب است.

---

## تست و عیب‌یابی

### 1. تست رمزگذاری

برای تست رمزگذاری، می‌توانید از endpoint زیر استفاده کنید:

```bash
curl -X POST "https://safrainai.pish.run/safiranayeha/test-decrypt" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "encrypted_param=YOUR_ENCRYPTED_STRING"
```

### 2. تست مستقیم با user_id و path

اگر می‌خواهید بدون رمزگذاری تست کنید:

```bash
curl -X POST "https://safrainai.pish.run/chat/init" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "path": "/konesh/list"}'
```

### 3. بررسی مسیرهای موجود

برای مشاهده تمام مسیرها و عامل‌های مربوطه:

```bash
curl "https://safrainai.pish.run/safiranayeha/path-mappings"
```

### 4. تست حالت بدون پارامتر

برای تست چت بدون پارامتر:

```bash
curl "https://safrainai.pish.run/ui"
```

---

## مشکلات رایج و راه‌حل

### مشکل 1: چت باز نمی‌شود

**علت:** ممکن است URL رمزگذاری شده به درستی encode نشده باشد.

**راه‌حل:**

- مطمئن شوید که از `HttpUtility.UrlEncode` استفاده می‌کنید
- بررسی کنید که `encrypted_param` در URL به درستی قرار گرفته است

### مشکل 2: عامل اشتباه انتخاب می‌شود

**علت:** مسیر (Path) به درستی ارسال نشده است.

**راه‌حل:**

- مطمئن شوید که مسیر با `/` شروع می‌شود (مثلاً `/konesh/list`)
- مسیر را دقیقاً همان‌طور که در URL صفحه است ارسال کنید

### مشکل 3: اطلاعات کاربر نمایش داده نمی‌شود

**علت:** ممکن است `UserId` به درستی ارسال نشده باشد.

**راه‌حل:**

- بررسی کنید که `UserId` در سیستم شما معتبر است
- مطمئن شوید که کاربر در سیستم Safiranayeha ثبت‌نام کرده است

---

## پشتیبانی

در صورت بروز مشکل یا نیاز به راهنمایی بیشتر:

- **مستندات کامل:** `/docs/SAFIRANAYEHA_INTEGRATION.md`
- **API Documentation:** `https://safrainai.pish.run/doc`
- **Health Check:** `https://safrainai.pish.run/health`

---

## خلاصه سریع

### حالت با پارامتر (پیشنهادی):

```csharp
// 1. رمزگذاری
string encrypted = EncryptUserData(userId, currentPath);

// 2. قرار دادن در HTML
<iframe src="https://safrainai.pish.run/ui?encrypted_param=@encrypted"></iframe>

// تمام! چت به صورت خودکار با عامل مناسب باز می‌شود.
```

### حالت بدون پارامتر (برای صفحات عمومی):

```html
<!-- بدون نیاز به رمزگذاری -->
<iframe src="https://safrainai.pish.run/ui"></iframe>

// تمام! چت با عامل پیش‌فرض باز می‌شود.
```

**نکته:** سیستم به صورت خودکار تشخیص می‌دهد که پارامتر وجود دارد یا نه و به‌صورت امن fallback می‌کند.

---

---

## ✨ نکات مهم

1. **Fallback امن:** اگر `encrypted_param` ارسال نشود، سیستم به‌صورت امن fallback می‌کند و هیچ خطایی رخ نمی‌دهد
2. **انتخاب هوشمند:** اگر پارامتر ارسال شود، routing و agent selection دقیق انجام می‌شود
3. **امنیت:** همیشه از HTTPS استفاده کنید
4. **ارتفاع iframe:** حداقل ارتفاع 500px پیشنهاد می‌شود
5. **عرض iframe:** می‌توانید از 100% عرض استفاده کنید
6. **Responsive:** چت به صورت خودکار با اندازه صفحه سازگار می‌شود
7. **مسیر:** همیشه مسیر کامل صفحه را ارسال کنید (با `/` شروع شود)

---

**آخرین به‌روزرسانی:** 2026-01-04
