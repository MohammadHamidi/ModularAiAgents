# Tone Update: More Casual and Friendly

## Changes Made

All personality configurations have been updated to use a more casual and friendly tone.

### Key Changes:

1. **Formal to Informal Address**:
   - Changed from "شما" (formal you) to "تو" (informal you)
   - Makes conversations feel more like talking to a close friend

2. **Friendlier Language**:
   - Emphasized "like a close friend" (مثل یه دوست صمیمی)
   - More relaxed, less formal
   - More casual expressions

3. **Emoji Permission**:
   - Added permission to use emojis when appropriate (but not overdo it)
   - Makes responses feel more modern and friendly

4. **Tone Guidelines**:
   - "خودمونی، بی‌استرس، صمیمی" (casual, stress-free, intimate)
   - Not like a teacher, expert, or formal consultant
   - Like a close friend helping out

### Files Updated:

1. ✅ `services/chat-service/config/agent_config.yaml`
2. ✅ `services/chat-service/config/personalities/friendly_tutor.yaml`
3. ✅ `services/chat-service/config/personalities/minimal_assistant.yaml`
4. ✅ `services/chat-service/config/personalities/professional_assistant.yaml`
5. ✅ `services/chat-service/config/personalities/konesh_expert.yaml`
6. ✅ `services/chat-service/config/personalities/orchestrator.yaml`

### Example Changes:

**Before:**
- "از «شما» استفاده کن ولی خیلی رسمی نباش"
- "مثل یه دوست باتجربه که داره کمک می‌کنه"

**After:**
- "از «تو» استفاده کن (نه «شما») - خیلی خودمونی‌تر و دوستانه‌تر"
- "مثل یه دوست صمیمی که داره کمک می‌کنه"
- "می‌تونی از emoji استفاده کنی اگه مناسب بود (ولی زیاده‌روی نکن)"

### To Apply Changes:

```bash
docker-compose restart chat-service
```

After restart, all agents will use a more casual, friendly tone with informal "تو" instead of formal "شما".

