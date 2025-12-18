# Tool-Based Memory System

## Overview

The chat agent now uses an **AI-powered tool** (`save_user_info`) to intelligently extract and save user information during natural conversations. This approach is superior to regex-based extraction because:

1. **🤖 AI-Driven:** The LLM decides what information is relevant
2. **🔇 Silent Operation:** No mention of data saving to the user
3. **💬 Natural Conversations:** Extraction happens during normal dialog
4. **📝 Last 2 Messages:** Recent context included for better understanding
5. **🧠 Intelligent:** Handles variations, typos, and complex sentences

---

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  User: "سلام! من محمد هستم و ۲۵ سالمه"            │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│  LLM Agent (with access to save_user_info tool)    │
│                                                     │
│  1. Understands user message                       │
│  2. Identifies: name=محمد, age=25                  │
│  3. Calls save_user_info() in background          │
│  4. Generates natural response                     │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│  save_user_info Tool                                │
│                                                     │
│  • Normalizes field names                          │
│  • Handles special cases (interests=list, age=int) │
│  • Updates pending_updates dict                    │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│  Context Manager (PostgreSQL)                       │
│                                                     │
│  • Merges with existing context                    │
│  • Persists to agent_context table                 │
│  • Sets TTL (4 hours default)                      │
└─────────────────────────────────────────────────────┘
```

### Key Components

#### 1. ChatDependencies (chat_agent.py:15-20)

```python
@dataclass
class ChatDependencies:
    session_id: str
    user_info: Dict[str, Any]      # Current context from DB
    pending_updates: Dict[str, Any] # New data from tools
```

Passed to tools via `RunContext` for state management.

#### 2. save_user_info Tool (chat_agent.py:46-118)

The core tool that the LLM calls to save user data:

```python
@self.agent.tool
async def save_user_info(
    ctx: RunContext[ChatDependencies],
    field_name: str,
    field_value: str,
) -> str:
    """Save or update user information from the conversation."""
```

**Supported Fields:**
- `name` → `user_name`
- `age` → `user_age` (converts to int)
- `location`, `city` → `user_location`
- `occupation`, `job` → `user_occupation`
- `interest`, `hobby` → `user_interests` (accumulates as list)
- `language`, `language_preference` → `preferred_language`

**Special Handling:**
- **Interests:** Accumulates into a list (no duplicates)
- **Age:** Converts Persian/Arabic digits to English, validates range (1-120)
- **Other fields:** Stored as-is

#### 3. Dynamic System Prompt (chat_agent.py:142-210)

Builds a context-rich system prompt with:
- **Static Instructions:** From config
- **User Information:** Name, age, location, occupation, interests, language
- **Last 2 User Messages:** For conversational context

Example output:
```
تو یک چت‌بات مفید، دقیق و با حافظه هستی...

📋 اطلاعات کاربر (User Information):
  • نام (Name): محمد
  • سن (Age): 25
  • موقعیت (Location): تهران
  • شغل (Occupation): برنامه‌نویس
  • علایق (Interests): فوتبال، کتاب خواندن

💬 آخرین پیام‌های کاربر (Last User Messages):
  1. من برنامه‌نویسم
  2. I like playing football
```

#### 4. Process Flow (chat_agent.py:212-289)

```python
async def process(request, history, shared_context):
    # 1. Get last 2 user messages
    last_user_messages = [...][-2:]

    # 2. Build dynamic system prompt
    dynamic_system_prompt = self._build_dynamic_system_prompt(...)

    # 3. Prepare dependencies
    deps = ChatDependencies(
        session_id=request.session_id,
        user_info=shared_context,
        pending_updates={}  # Populated by tools
    )

    # 4. Run agent (LLM may call save_user_info)
    result = await self.agent.run(request.message, deps=deps)

    # 5. Merge updates from tools with existing context
    context_updates_combined = {**shared_context, **pending_updates}

    # 6. Return response
    return AgentResponse(context_updates=context_updates_combined)
```

---

## System Prompt Strategy

The system prompt in `main.py:83-110` instructs the agent:

### Key Instructions

1. **Use the tool silently:**
   ```
   "⚠️ مهم: هرگز به کاربر نگو که اطلاعاتش را ذخیره کردی!"
   "IMPORTANT: Never tell the user you saved their information!"
   ```

2. **Extract proactively:**
   ```
   "هر وقت کاربر اطلاعاتی درباره خودش می‌گوید، بلافاصله آن را ذخیره کن"
   "Whenever the user mentions personal information, immediately save it"
   ```

3. **Natural responses:**
   ```
   مثال غلط: «باشه! اسمت رو ذخیره کردم» ❌
   مثال صحیح: «سلام محمد! چطور می‌تونم کمکت کنم؟» ✅
   ```

4. **Tool usage examples:**
   ```
   - برای نام: save_user_info(field_name='name', field_value='محمد')
   - برای سن: save_user_info(field_name='age', field_value='25')
   - برای شهر: save_user_info(field_name='location', field_value='تهران')
   ```

---

## Usage Examples

### Example 1: Natural Introduction

**User:**
```
سلام! من محمد هستم، ۲۵ سالمه و از تهران هستم.
```

**Behind the scenes (LLM calls):**
```python
save_user_info(field_name='name', field_value='محمد')
save_user_info(field_name='age', field_value='25')
save_user_info(field_name='location', field_value='تهران')
```

**Agent Response:**
```
سلام محمد! خوشحالم که آشنا شدیم. چطور می‌تونم کمکت کنم؟
```

**Stored Context:**
```json
{
  "user_name": {"value": "محمد"},
  "user_age": {"value": 25},
  "user_location": {"value": "تهران"}
}
```

### Example 2: Information in Questions

**User:**
```
من برنامه‌نویسم. می‌تونی کمکم کنی یه الگوریتم بنویسم؟
```

**Behind the scenes:**
```python
save_user_info(field_name='occupation', field_value='برنامه‌نویس')
```

**Agent Response:**
```
البته! چه الگوریتمی می‌خوای بنویسی؟
```

### Example 3: Accumulating Interests

**User 1:**
```
I like playing football
```

**Behind the scenes:**
```python
save_user_info(field_name='interest', field_value='football')
```

**User 2 (later):**
```
I also enjoy reading books
```

**Behind the scenes:**
```python
save_user_info(field_name='interest', field_value='reading')
```

**Final Context:**
```json
{
  "user_interests": {"value": ["football", "reading"]}
}
```

---

## Testing

### Run the test suite:

```bash
cd ai_platform
python test_tool_based_memory.py
```

### What it tests:

1. ✅ Multiple pieces of info extracted from single message
2. ✅ Agent doesn't mention saving data (silent operation)
3. ✅ Context persists across messages
4. ✅ Previous data preserved when adding new info
5. ✅ Agent can recall saved information
6. ✅ Last 2 user messages available for context

### Expected Output:

```
================================================================================
Testing Tool-Based User Information Extraction
================================================================================

Test 1: Natural introduction with name, age, and location...
  User: سلام! من محمد هستم، ۲۵ سالمه و از تهران هستم.
  Assistant: سلام محمد! خوشحالم که آشنا شدیم. چطور می‌تونم کمکت کنم؟
  ✅ Agent responded naturally without mentioning data saving
  ✅ All information extracted correctly

Test 2: Sharing occupation naturally...
  ✅ Occupation saved: برنامه‌نویس
  ✅ Previous data preserved

Test 3: Sharing interests naturally...
  ✅ Interests saved: ['football', 'reading']

Test 4: Agent recalls information using context...
  ✅ Agent successfully recalled user information

Test 5: Last 2 messages context...
  ✅ Agent has access to recent message context

================================================================================
✅ ALL TOOL-BASED EXTRACTION TESTS COMPLETED!
================================================================================
```

---

## Advantages Over Regex-Based Extraction

| Feature | Regex-Based (Old) | Tool-Based (New) |
|---------|-------------------|------------------|
| **Flexibility** | Fixed patterns only | Handles variations naturally |
| **Accuracy** | Miss typos/variations | LLM understands context |
| **Extensibility** | Edit regex for new fields | Just add to field_map |
| **Language Support** | Separate patterns per language | LLM handles multilingual |
| **Complex Sentences** | Fails on complex grammar | Understands naturally |
| **Silent Operation** | Not possible | ✅ Built-in |
| **Last Messages Context** | Manual implementation | ✅ Integrated |

### Example Comparisons

**Input:** "My name is Mohammad and I'm 25"

| Method | Result |
|--------|--------|
| Regex | May only catch "Mohammad" if "25" pattern doesn't match |
| Tool | ✅ Extracts both name=Mohammad, age=25 |

**Input:** "I'm Mohammad, btw I'm turning 26 next month but right now I'm 25"

| Method | Result |
|--------|--------|
| Regex | Might extract wrong age (26) |
| Tool | ✅ LLM understands "right now I'm 25" is current age |

---

## Configuration

### Environment Variables

```bash
# Model for LLM (should support function calling)
LITELLM_MODEL=gemini-2.5-flash-lite-preview-09-2025

# Context TTL (how long to keep user info)
SESSION_TTL_SECONDS=14400  # 4 hours

# Max conversation history
MAX_SESSION_MESSAGES=30
```

### System Prompt Customization

Edit `main.py:83-110` to customize instructions for the agent.

---

## Data Storage

### Database Schema

```sql
-- agent_context table
CREATE TABLE agent_context (
    session_id UUID NOT NULL,
    context_key VARCHAR NOT NULL,
    context_value JSONB NOT NULL,
    agent_type VARCHAR,
    expires_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (session_id, context_key)
);
```

### Example Stored Data

```json
{
  "user_name": {"value": "محمد"},
  "user_age": {"value": 25},
  "user_location": {"value": "تهران"},
  "user_occupation": {"value": "برنامه‌نویس"},
  "user_interests": {"value": ["فوتبال", "کتاب خواندن"]},
  "preferred_language": {"value": "fa"}
}
```

---

## Troubleshooting

### Agent mentions saving data

**Problem:** Agent says "I saved your information"

**Solution:** Strengthen the system prompt emphasis:
```python
"⚠️⚠️⚠️ CRITICAL: NEVER mention saving data to the user!"
```

### Information not extracted

**Problem:** User info not being saved

**Possible causes:**
1. Model doesn't support function calling
2. System prompt not clear enough
3. User message too ambiguous

**Debug:**
```python
# Check result.all_messages() to see tool calls
result = await self.agent.run(...)
print(result.all_messages())  # Should show tool_call messages
```

### Interests not accumulating

**Problem:** Only latest interest saved

**Check:** The tool handler correctly merges with existing interests:
```python
existing = ctx.deps.user_info.get("user_interests", {"value": []})
interests_list = existing.get("value", [])
```

---

## Future Enhancements

1. **More Field Types:**
   - Email addresses
   - Phone numbers
   - Preferences (theme, notifications)
   - Relationships (family members, friends)

2. **Advanced Features:**
   - Sentiment analysis (user mood)
   - Topic tracking (what they talk about most)
   - Temporal context (remembering when things were mentioned)
   - Cross-session patterns

3. **Privacy Controls:**
   - User-requested data deletion
   - Selective information sharing
   - Consent management

4. **Multi-Agent Sharing:**
   - Share context across different agent types
   - Privacy boundaries between agents

---

## Migration from Old System

The old regex-based system is completely replaced. No migration needed for new sessions. Existing sessions will work fine and gradually adopt the new system.

### Old vs New Code

**Old (regex-based):**
```python
def _extract_user_signals(self, message: str):
    if "من " in text and "هستم" in text:
        # Complex regex pattern...
        after_man = text.split("من", 1)[1].strip()
        # ... more processing ...
```

**New (tool-based):**
```python
@self.agent.tool
async def save_user_info(ctx, field_name, field_value):
    # LLM handles extraction, we just save it
    ctx.deps.pending_updates[field_name] = {"value": field_value}
```

---

## Summary

The tool-based memory system provides:

- ✅ **AI-powered extraction:** More accurate than regex
- ✅ **Silent operation:** No disruption to conversation flow
- ✅ **Last 2 messages context:** Better understanding
- ✅ **Natural conversations:** Extraction during normal dialog
- ✅ **Extensible:** Easy to add new field types
- ✅ **Multilingual:** Works across languages naturally

This approach creates a more intelligent, natural, and powerful conversational AI experience.

---

*Implemented: 2025-12-18*
*Author: Claude (AI Assistant)*
