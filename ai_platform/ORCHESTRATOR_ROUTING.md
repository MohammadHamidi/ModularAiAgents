# Orchestrator Default Routing Implementation

## تغییرات انجام شده

همه درخواست‌ها به‌صورت پیش‌فرض از طریق Orchestrator route می‌شوند.

### نحوه کار

1. **درخواست از Chat.html**: کاربر یک agent را از dropdown انتخاب می‌کند (default, tutor, professional, minimal)

2. **در Backend (main.py)**:
   - اگر `agent_key == "orchestrator"`: درخواست مستقیماً به Orchestrator می‌رود
   - اگر `agent_key` دیگری باشد:
     - درخواست ابتدا به Orchestrator می‌رود
     - یک hint به پیام اضافه می‌شود: `[REQUESTED_AGENT: {agent_key}]`
     - Orchestrator این hint را می‌بیند و تصمیم می‌گیرد:
       - آیا به agent انتخاب‌شده route کند (اگر مناسب باشد)
       - یا به agent بهتری route کند (بر اساس محتوای پیام)

3. **Orchestrator (orchestrator.yaml)**:
   - hint `[REQUESTED_AGENT: ...]` را می‌خواند
   - آن را به‌عنوان ترجیح کاربر در نظر می‌گیرد
   - اما هنوز محتوای پیام را تحلیل می‌کند
   - اگر agent انتخاب‌شده مناسب باشد → از آن استفاده می‌کند
   - اگر پیام نیاز به agent دیگری داشته باشد → به agent بهتری route می‌کند

4. **Agent Router Tool (agent_router.py)**:
   - هنگام route کردن به agent نهایی، prefix `[REQUESTED_AGENT: ...]` را حذف می‌کند
   - پیام تمیز به agent نهایی ارسال می‌شود

### مزایا

✅ **Routing هوشمند**: Orchestrator می‌تواند درخواست را به agent مناسب‌تر route کند حتی اگر کاربر agent دیگری انتخاب کرده باشد

✅ **احترام به انتخاب کاربر**: اگر agent انتخاب‌شده مناسب باشد، Orchestrator از آن استفاده می‌کند

✅ **Fallback**: اگر Orchestrator در دسترس نباشد، سیستم به حالت قبلی (direct routing) برمی‌گردد

✅ **شفافیت**: کاربر می‌تواند agent خاصی را انتخاب کند، اما Orchestrator تصمیم نهایی را می‌گیرد

### فایل‌های تغییر یافته

1. **services/chat-service/main.py**:
   - منطق routing اضافه شد
   - همه درخواست‌ها (به جز orchestrator) از طریق Orchestrator route می‌شوند
   - Hint `[REQUESTED_AGENT: ...]` به پیام اضافه می‌شود

2. **services/chat-service/config/personalities/orchestrator.yaml**:
   - دستورالعمل‌های routing به‌روزرسانی شد
   - منطق پردازش hint `[REQUESTED_AGENT: ...]` اضافه شد

3. **services/chat-service/tools/agent_router.py**:
   - منطق حذف prefix `[REQUESTED_AGENT: ...]` اضافه شد
   - پیام تمیز به agent نهایی ارسال می‌شود

### تست

برای تست کردن:

```bash
# تست با agent پیش‌فرض (باید از طریق orchestrator route شود)
curl -X POST http://localhost:8001/chat/default \
  -H "Content-Type: application/json" \
  -d '{"message": "سلام، می‌خوام درباره کنش‌های مدرسه بدانم", "session_id": null}'

# تست با agent tutor (باید از طریق orchestrator route شود)
curl -X POST http://localhost:8001/chat/tutor \
  -H "Content-Type: application/json" \
  -d '{"message": "سلام، من یک معلم هستم", "session_id": null}'

# تست مستقیم با orchestrator
curl -X POST http://localhost:8001/chat/orchestrator \
  -H "Content-Type: application/json" \
  -d '{"message": "سلام", "session_id": null}'
```

### نکات مهم

⚠️ **Orchestrator باید در دسترس باشد**: اگر Orchestrator load نشود، سیستم به حالت fallback (direct routing) می‌رود

⚠️ **Performance**: یک لایه اضافی routing اضافه شده است، اما این تأثیر کمی دارد چون Orchestrator فقط تصمیم می‌گیرد و route می‌کند

⚠️ **Session Management**: Session ID و context به درستی به agent نهایی منتقل می‌شوند

### مثال سناریو

1. کاربر در Chat.html، agent "tutor" را انتخاب می‌کند
2. پیام: "سلام، می‌خوام درباره کنش‌های مدرسه بدانم"
3. Backend پیام را به `[REQUESTED_AGENT: tutor] سلام، می‌خوام درباره کنش‌های مدرسه بدانم` تبدیل می‌کند
4. Orchestrator می‌بیند:
   - کاربر "tutor" را انتخاب کرده
   - اما پیام درباره "کنش‌های مدرسه" است
   - Orchestrator تصمیم می‌گیرد: "konesh_expert" مناسب‌تر است
5. Orchestrator به "konesh_expert" route می‌کند (با حذف prefix)
6. "konesh_expert" پاسخ می‌دهد

