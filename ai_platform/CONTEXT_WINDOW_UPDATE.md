# Context Window Update - Increased to 4 Messages

## Summary

The context window for all AI agents has been increased from 2 to 4 recent messages.

## What Changed

The `recent_messages_context.count` field in all personality configuration files has been updated from `2` to `4`.

## Files Updated

1. ✅ `services/chat-service/config/agent_config.yaml`
   - `count: 2` → `count: 4`

2. ✅ `services/chat-service/config/personalities/friendly_tutor.yaml`
   - `count: 2` → `count: 4`

3. ✅ `services/chat-service/config/personalities/konesh_expert.yaml`
   - `count: 2` → `count: 4`

4. ✅ `services/chat-service/config/personalities/minimal_assistant.yaml`
   - `count: 2` → `count: 4`

5. ✅ `services/chat-service/config/personalities/professional_assistant.yaml`
   - `count: 2` → `count: 4`

6. ✅ `services/chat-service/config/personalities/orchestrator.yaml`
   - `count: 2` → `count: 4`

## Impact

- **Before**: Agents had access to the last 2 user messages
- **After**: Agents now have access to the last 4 user messages

This means:
- Better conversation continuity
- Agents can remember more context from the conversation
- More accurate responses based on recent conversation history
- Better understanding of multi-turn conversations

## How It Works

The `recent_messages_context` configuration controls how many recent user messages are included in the system prompt context. The agent code in `chat_agent.py` uses this value:

```python
count = recent_config.get('count', 2)
last_user_messages = [
    msg for msg in (history or [])[-count*3:] if msg.get("role") == "user"
][-count:]
```

With `count: 4`, the agent will now include the last 4 user messages in the context.

## To Apply Changes

```bash
docker-compose restart chat-service
```

After restart, all agents will use the new context window of 4 messages.

