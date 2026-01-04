# Knowledge Base Tool Issue - Fix Summary

## Problem

The agent was saying "با توجه به عدم وجود اطلاعات مشخص در پایگاه دانش" (Due to lack of specific information in the knowledge base) even though the knowledge base contains the information.

## Root Cause

The `journey_register` agent was missing the `knowledge_base_query` tool. It only had `query_konesh` tool assigned.

**Previous configuration:**
```python
"journey_register": ["query_konesh"],  # ❌ Missing knowledge_base_query!
```

When a user asked a question:
1. The system added KB instruction to the message: "حتماً ابتدا از knowledge_base_query استفاده کن"
2. But `journey_register` didn't have the `knowledge_base_query` tool available
3. So it used `query_konesh` instead (the only tool it had)
4. `query_konesh` queries the Safiranayeha API (not the local knowledge base)
5. The API doesn't have detailed content, so the agent said "no information in knowledge base"

## Fix Applied

Added `knowledge_base_query` tool to `journey_register`:

**File:** `ai_platform/services/chat-service/main.py` (line 287)

**New configuration:**
```python
persona_tool_assignments = {
    "orchestrator": ["route_to_agent"],
    "guest_faq": ["knowledge_base_query"],
    "action_expert": ["query_konesh", "knowledge_base_query"],
    "journey_register": ["query_konesh", "knowledge_base_query"],  # ✅ Added KB tool
    "rewards_invite": ["knowledge_base_query"],
}
```

## Verification

Service logs now show `journey_register` has 2 tools registered:
```
INFO:agents.chat_agent:_register_custom_tools for راهنمای ثبت کنش و مسیر سفیران: 2 tools to register
INFO:agents.chat_agent:  Registering tool: query_konesh, enabled=True
INFO:agents.chat_agent:  Successfully registered tool: knowledge_base_query, enabled=True
```

## Tool Assignment Summary

All agents now have appropriate tools:

| Agent | Tools | Purpose |
|-------|-------|---------|
| orchestrator | `route_to_agent` | Routes to specialist agents |
| guest_faq | `knowledge_base_query` | Queries KB for FAQ info |
| action_expert | `query_konesh`, `knowledge_base_query` | Queries both API and KB |
| journey_register | `query_konesh`, `knowledge_base_query` | ✅ Can now query KB |
| rewards_invite | `knowledge_base_query` | Queries KB for rewards info |

## Additional Consideration

There's still a question of **why** `journey_register` was selected for a question about "ایده‌های کنش خانگی" (home action ideas). That question would typically be better handled by:
- `action_expert` (for detailed action/konesh guidance)
- `guest_faq` (for general information)

This might be:
1. Due to user path (e.g., `/profile/*` → `journey_register`)
2. User explicitly requested `journey_register` agent
3. Session context suggested registration/journey flow

With the fix applied, `journey_register` can now properly query the knowledge base regardless of why it was selected.

## Status

✅ **Fixed and Deployed**
- Container rebuilt with updated tool assignments
- Service restarted successfully
- `journey_register` now has access to `knowledge_base_query` tool
- All agents can query the knowledge base when needed

## Date
January 4, 2026

