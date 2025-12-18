# Memory Issue Fix Documentation

## Problem Summary

The ModularAiAgents chatbot had two critical memory bugs that caused user context to be lost across conversations:

1. **Context Data Loss via `user_prefs` Overwriting**
2. **Interests Not Accumulating Across Sessions**

---

## Bug #1: Context Data Loss via `user_prefs` Overwriting

### Root Cause

In `chat_agent.py`, the `_extract_user_signals()` method created a nested structure under a `user_prefs` key that was overwritten on each request:

```python
# OLD CODE (lines 293-295)
if context_updates:
    prefs_updates["user_prefs"] = context_updates

# Later (lines 455-461)
context_updates_combined.update(context_updates)   # Flat: {user_name: {...}}
context_updates_combined.update(prefs_updates)     # Nested: {user_prefs: {user_name: {...}}}
```

### The Problem Flow

**Request 1:** User says "من محمد هستم" (I am Mohammad)
```python
# Saved to database:
{
    "user_name": {"value": "محمد"},
    "user_prefs": {"user_name": {"value": "محمد"}}
}
```

**Request 2:** User says "من ۲۵ سالمه" (I am 25 years old)
```python
# Loaded from database:
shared_context = {
    "user_name": {"value": "محمد"},
    "user_prefs": {"user_name": {"value": "محمد"}}
}

# Extracted from current message:
context_updates = {"user_age": {"value": 25}}
prefs_updates = {"user_prefs": {"user_age": {"value": 25}}}  # ONLY age!

# Merged:
context_updates_combined = {
    "user_name": {"value": "محمد"},       # From shared_context
    "user_prefs": {...},                  # From shared_context (will be overwritten!)
    "user_age": {"value": 25},            # From context_updates
    "user_prefs": {"user_age": {"value": 25}}  # OVERWRITES previous user_prefs!
}

# Final saved state:
{
    "user_name": {"value": "محمد"},        # ✓ Still there (flat key)
    "user_age": {"value": 25},             # ✓ New data
    "user_prefs": {"user_age": {"value": 25}}  # ✗ Lost user_name!
}
```

### The Fix

**Removed the problematic `user_prefs` nesting entirely:**

```python
# NEW CODE (line 293)
return context_updates, {}  # No longer creates user_prefs nesting
```

Now only flat keys are stored and retrieved:
```python
{
    "user_name": {"value": "محمد"},
    "user_age": {"value": 25},
    "user_location": {"value": "تهران"}
    # No user_prefs key!
}
```

---

## Bug #2: Interests Not Accumulating Across Sessions

### Root Cause

When extracting interests, the code read from `context_updates` (current request only) instead of `merged_context` (which includes previous sessions):

```python
# OLD CODE (line 244)
existing = context_updates.get("user_interests", {"value": []})
```

### The Problem Flow

**Session 1:** User says "I like football"
```python
# Saved:
{"user_interests": {"value": ["football"]}}
```

**Session 2:** User says "I like reading"
```python
# context_updates is empty at extraction time (only has current message)
existing = context_updates.get("user_interests", {"value": []})  # Returns []!

# Saved:
{"user_interests": {"value": ["reading"]}}  # Lost "football"!
```

### The Fix

**Two-phase approach:**

1. **During extraction:** Store new interests as `_new_interests` (temporary key)
2. **In process():** Merge `_new_interests` with existing interests from `shared_context`

```python
# NEW CODE - Phase 1: Extraction (lines 237-273)
extracted_interests = []

# Persian extraction
if "علاقه دارم" in text or "دوست دارم" in text:
    # ... extract interest ...
    extracted_interests.append(interest)

# English extraction
if "i like" in lowered or "i love" in lowered or "i enjoy" in lowered:
    # ... extract interest ...
    extracted_interests.append(interest)

# Store as temporary key
if extracted_interests:
    context_updates["_new_interests"] = {"value": extracted_interests}

# NEW CODE - Phase 2: Merging (lines 307-323)
if "_new_interests" in context_updates:
    new_interests = context_updates["_new_interests"].get("value", [])

    # Get existing interests from shared_context (previous sessions)
    existing_interests_data = (shared_context or {}).get("user_interests", {"value": []})
    existing_interests = existing_interests_data.get("value", [])

    # Merge without duplicates
    all_interests = list(existing_interests)
    for interest in new_interests:
        if interest not in all_interests:
            all_interests.append(interest)

    # Replace _new_interests with complete user_interests
    del context_updates["_new_interests"]
    if all_interests:
        context_updates["user_interests"] = {"value": all_interests}
```

Now interests accumulate correctly:
```python
# Session 1: "I like football"
{"user_interests": {"value": ["football"]}}

# Session 2: "I like reading"
{"user_interests": {"value": ["football", "reading"]}}  # ✓ Both present!
```

---

## Files Modified

- `ai_platform/services/chat-service/agents/chat_agent.py`
  - Lines 233-273: Refactored interests extraction
  - Line 293: Removed `user_prefs` nesting
  - Lines 307-323: Added interests merging logic
  - Lines 469-474: Simplified context_updates_combined building

---

## Testing

A comprehensive test suite has been added in `test_memory_fix.py` that verifies:

1. ✓ Name persists after adding age
2. ✓ Name and age persist after adding location
3. ✓ All fields persist after adding interests
4. ✓ Multiple interests accumulate correctly
5. ✓ No `user_prefs` key exists in final context
6. ✓ Bot can recall all stored information

### Run the test:

```bash
cd ai_platform
python test_memory_fix.py
```

Expected output:
```
=================================================================================
Testing Memory Accumulation Fix
=================================================================================

Step 1: User provides name...
  ✓ Name stored correctly

Step 2: User provides age...
  ✓ Both name and age stored correctly

Step 3: User provides location...
  ✓ All three fields (name, age, location) stored correctly

Step 4: User provides first interest...
  ✓ First interest stored: ['football']

Step 5: User provides second interest...
  ✓ Both interests accumulated: ['football', 'reading']

Step 6: Ask bot to recall all information...
  ✓ Bot recalls stored information

=================================================================================
✅ ALL MEMORY TESTS PASSED!
=================================================================================
```

---

## Impact

### Before Fix
- User context would be partially lost after each message
- Interests would reset on each session
- `user_prefs` key contained incomplete data

### After Fix
- All user context persists across messages and sessions
- Interests accumulate properly
- Cleaner data structure without redundant nesting
- More reliable memory-aware conversations

---

## Future Improvements

Consider these enhancements:

1. **Context Merging Helper:** Create a dedicated function for deep-merging nested dictionaries
2. **Context Versioning:** Add version field to handle schema migrations
3. **Context Validation:** Add Pydantic models to validate context structure
4. **Cleanup Script:** Remove old `user_prefs` keys from existing sessions in database
5. **More Tests:** Add tests for edge cases (empty values, special characters, etc.)

---

## Deployment Notes

This fix is **backward compatible** - existing sessions will continue to work. The old `user_prefs` keys will simply be ignored, and new data will be stored in the flat structure.

To clean up old data (optional):

```sql
-- Remove user_prefs keys from existing contexts
DELETE FROM agent_context WHERE context_key = 'user_prefs';
```

---

*Fixed on: 2025-12-18*
*Author: Claude (AI Assistant)*
