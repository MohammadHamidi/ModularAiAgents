# استفاده ساده از دستیار تولید محتوا (بدون ورود)

## 🚀 سریع‌ترین روش

فقط کافی است این کد را در صفحه خود قرار دهید:

```html
<iframe
    src="https://safrainai.pish.run/ui?path=/content-generator"
    style="width: 100%; height: 700px; border: none;"
    allow="microphone; camera">
</iframe>
```

## ✅ تمام!

این کد:
- از همان `Chat.html` موجود استفاده می‌کند
- **بدون نیاز به user ID** کار می‌کند
- **هیچ کد JavaScript اضافه‌ای** نیاز ندارد
- **هیچ API call دستی** نیاز ندارد
- مستقیماً به **Content Generator** متصل می‌شود

---

## 📝 مثال‌های کاربردی

### 1. صفحه HTML ساده

```html
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>دستیار تولید محتوا</title>
</head>
<body>
    <h1>دستیار تولید محتوای قرآنی</h1>
    
    <iframe
        src="https://safrainai.pish.run/ui?path=/content-generator"
        style="width: 100%; height: 700px; border: none;">
    </iframe>
</body>
</html>
```

### 2. WordPress / CMS

```html
<!-- Shortcode یا HTML Block -->
<div style="max-width: 1200px; margin: 0 auto;">
    <iframe
        src="https://safrainai.pish.run/ui?path=/content-generator"
        style="width: 100%; height: 700px; border: none; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
    </iframe>
</div>
```

### 3. React Component

```jsx
function ContentGenerator() {
  return (
    <div className="content-generator">
      <h1>دستیار تولید محتوا</h1>
      <iframe
        src="https://safrainai.pish.run/ui?path=/content-generator"
        style={{
          width: '100%',
          height: '700px',
          border: 'none',
          borderRadius: '15px'
        }}
        allow="microphone; camera"
        title="دستیار تولید محتوای قرآنی"
      />
    </div>
  );
}
```

---

## 🎯 تفاوت با روش معمولی

| ویژگی | روش معمولی (با ورود) | روش عمومی (بدون ورود) |
|------|---------------------|----------------------|
| URL | `/ui?encrypted_param=...` | `/ui?path=/content-generator` |
| User ID | ✅ لازم | ❌ لازم نیست |
| Encrypted Param | ✅ لازم | ❌ لازم نیست |
| API Call | ✅ لازم | ❌ لازم نیست |
| شخصی‌سازی | ✅ دارد | ❌ ندارد |
| دسترسی به تاریخچه | ✅ دارد | ❌ ندارد |

---

## ⚙️ تنظیمات اختیاری

### تغییر ارتفاع

```html
<iframe
    src="https://safrainai.pish.run/ui?path=/content-generator"
    style="width: 100%; height: 800px; border: none;">
</iframe>
```

### اضافه کردن استایل

```html
<iframe
    src="https://safrainai.pish.run/ui?path=/content-generator"
    style="
        width: 100%;
        height: 700px;
        border: none;
        border-radius: 20px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
    ">
</iframe>
```

### Responsive (موبایل)

```html
<iframe
    src="https://safrainai.pish.run/ui?path=/content-generator"
    style="
        width: 100%;
        height: 90vh;
        min-height: 500px;
        border: none;
    ">
</iframe>
```

---

## 🔗 مسیرهای جایگزین

اگر می‌خواهید از مسیر دیگری استفاده کنید:

```html
<!-- مسیر 1 -->
<iframe src="https://safrainai.pish.run/ui?path=/content-generator"></iframe>

<!-- مسیر 2 (جایگزین) -->
<iframe src="https://safrainai.pish.run/ui?path=/ai-content"></iframe>
```

**هر دو مسیر یکسان کار می‌کنند!**

---

## 💡 نکات مهم

1. **بدون نیاز به کد پیچیده**: فقط یک iframe ساده
2. **بدون نیاز به user ID**: مسیر `/content-generator` عمومی است
3. **استفاده از Chat.html موجود**: نیازی به فایل جدید نیست
4. **کاملاً امن**: تمام بررسی‌های امنیتی در backend انجام می‌شود

---

## 🆘 عیب‌یابی

### مشکل: iframe خالی است

**حل:**
- بررسی کنید URL صحیح باشد
- مطمئن شوید `path=/content-generator` در URL وجود دارد
- Console مرورگر را بررسی کنید

### مشکل: CORS error

**حل:**
- مطمئن شوید از HTTPS استفاده می‌کنید
- backend باید CORS را برای domain شما enable کرده باشد

---

## 📞 پشتیبانی

در صورت بروز مشکل:
- بررسی Console مرورگر
- بررسی Network tab در Developer Tools
- تماس با تیم فنی سفیران آیه‌ها

---

**© 2026 سفیران آیه‌ها**
