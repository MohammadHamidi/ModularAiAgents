---
name: LightRAG Integration and Product-Specific Prompts
overview: Integrate LightRAG Server API into the knowledge base tool and reframe all agent system prompts to be product-specific for "زندگی با آیه‌ها" (Life with Verses), with shared add-on blocks and LightRAG query policies.
todos:
  - id: env-config
    content: Add LightRAG environment variables to .env file (LIGHTRAG_BASE_URL and optional auth)
    status: completed
  - id: update-kb-tool
    content: Replace knowledge_base.py mock implementation with LightRAG API client, rename to knowledge_base_query, update parameters to match LightRAG contract
    status: completed
    dependencies:
      - env-config
  - id: update-tool-references
    content: Update tool name references from knowledge_base_search to knowledge_base_query in main.py, registry.py, and chat_agent.py
    status: completed
    dependencies:
      - update-kb-tool
  - id: update-default-prompt
    content: Replace default agent system_prompt in agent_config.yaml with product-specific prompt for زندگی با آیه‌ها, including LightRAG policy and shared add-on
    status: completed
  - id: update-tutor-prompt
    content: Update friendly_tutor.yaml system_prompt to be product-specific (verse understanding + action practice) with LightRAG policy
    status: completed
  - id: update-professional-prompt
    content: Update professional_assistant.yaml system_prompt for internal team operations with LightRAG policy
    status: completed
  - id: update-minimal-prompt
    content: Update minimal_assistant.yaml system_prompt to maintain privacy-first but add action-driving and LightRAG policy
    status: completed
  - id: update-translator-prompt
    content: Update translator agent prompt in main.py to add internal_context rule without suggestions requirement
    status: completed
  - id: test-integration
    content: Test LightRAG integration and all prompt behaviors with sample queries (guest mode, verse queries, action flows, etc.)
    status: completed
    dependencies:
      - update-kb-tool
      - update-tool-references
      - update-default-prompt
      - update-tutor-prompt
      - update-professional-prompt
      - update-minimal-prompt
      - update-translator-prompt
---

# LightRAG Integration and Product-Specific Prompt Updates

## Overview

This plan integrates LightRAG Server API into the existing knowledge base tool and reframes all agent prompts to be product-specific for "زندگی با آیه‌ها" (Life with Verses) campaign, replacing generic assistant behavior with content-grounded, action-driving responses.

## Changes Required

### 1. Environment Configuration

**File:** `.env` (root directory)

Add LightRAG configuration:

- `LIGHTRAG_BASE_URL` (required) - Base URL for LightRAG server
- Optional auth: `LIGHTRAG_USERNAME`, `LIGHTRAG_PASSWORD`, `LIGHTRAG_API_KEY_HEADER_VALUE`, or `LIGHTRAG_BEARER_TOKEN`

### 2. Update Knowledge Base Tool

**File:** `services/chat-service/tools/knowledge_base.py`

**Changes:**

- Rename tool from `knowledge_base_search` to `knowledge_base_query`
- Replace mock implementation with LightRAG API client
- Update parameters to match LightRAG contract:
                                - `query` (string, required, min 3 chars)
                                - `mode` (enum: "mix"|"hybrid"|"local"|"global"|"naive"|"bypass", default: "mix")
                                - `include_references` (boolean, default: true)
                                - `include_chunk_content` (boolean, default: false)
                                - `response_type` (enum: "Bullet Points"|"Single Paragraph"|"Multiple Paragraphs", default: "Multiple Paragraphs")
                                - `top_k` (integer, default: 10)
                                - `chunk_top_k` (integer, default: 8)
                                - `max_total_tokens` (integer, default: 6000)
                                - `conversation_history` (array, optional)
- Implement LightRAG API client with auth handling (OAuth2 password flow, api_key_header_value, or bearer token)
- Call `POST /query` endpoint
- Format response with citations (Sources: [ref_id] file_path)

### 3. Update Tool Registry References

**Files:**

- `services/chat-service/main.py` - Update tool name in persona_tool_assignments
- `services/chat-service/tools/registry.py` - Update DEFAULT_PERSONA_TOOLS
- `services/chat-service/agents/chat_agent.py` - Update tool name check

**Change:** `knowledge_base_search` → `knowledge_base_query`

### 4. Create Shared Add-On Block

**New section to add to all agent prompts:**

```
SHARED ADD-ON (paste into all prompts)

هر پیام کاربر ممکن است با <internal_context>...</internal_context> شروع شود؛ از آن استفاده کن ولی هرگز در خروجی تکرار نکن.

اگر مطمئن نیستی یا داده کافی نیست، حدس نزن. بگو «اطلاعات کافی ندارم» و گزینه‌های بعدی پیشنهاد بده.

بعد از هر پاسخ، حتماً بخش «پیشنهادهای بعدی» را با 2 تا 4 گزینه کوتاه بده.

خروجی را کوتاه، عملیاتی، و مناسب موبایل بنویس.

هیچ‌وقت نگوی «اطلاعاتت را ذخیره کردم» یا به ابزارها اشاره نکن.
```

### 5. Update Default Agent Prompt

**File:** `services/chat-service/config/agent_config.yaml`

**Replace system_prompt with:**

- Product-specific prompt for "زندگی با آیه‌ها"
- Guest vs Logged-in mode detection
- Content-grounded responses (only from KB)
- Action-driving behavior (کنش → گزارش)
- LightRAG knowledge base policy
- Shared add-on block

**Key behaviors:**

- Mode detection based on user_data presence
- Context-aware (current_page, current_verse_id, current_action_id if provided)
- Content-grounded (only answer from KB, no hallucination)
- Action-driving (always suggest next steps)
- Graceful fallback (if content missing, say so)

### 6. Update Tutor Agent Prompt

**File:** `services/chat-service/config/personalities/friendly_tutor.yaml`

**Update system_prompt to:**

- Focus on "آموزگار فهم آیه + تمرین کنش" (verse understanding + action practice)
- Keep educational tone but product-specific
- LightRAG knowledge base policy
- Shared add-on block

### 7. Update Professional Agent Prompt

**File:** `services/chat-service/config/personalities/professional_assistant.yaml`

**Update system_prompt to:**

- Focus on internal team operations (content delivery, tagging, requirements)
- Structured outputs (checklists, schemas, acceptance criteria)
- LightRAG knowledge base policy
- Shared add-on block

### 8. Update Minimal Agent Prompt

**File:** `services/chat-service/config/personalities/minimal_assistant.yaml`

**Update system_prompt to:**

- Keep privacy-first approach
- Still action-driving (2-4 suggestions)
- Explain login requirement for personalized features
- LightRAG knowledge base policy
- Shared add-on block

### 9. Update Translator Agent Prompt

**File:** `services/chat-service/main.py` (translator registration)

**Update system_prompt to:**

- Keep translation-only focus
- Add only internal_context rule + no hallucination
- Omit "suggestions" requirement (translator shouldn't push actions)

### 10. Add LightRAG Knowledge Base Policy

**Add to all agent prompts (except translator):**

```
KNOWLEDGE BASE POLICY (LightRAG)

You have access to an external Knowledge Base via LightRAG. When you need factual, product-specific, internal, or document-grounded information, you MUST use the tool: knowledge_base_query.

When to use knowledge_base_query (mandatory):
- The user asks about anything that could exist in our documents, SOPs, specs, meeting notes, configs, features, pricing, roadmap, policies, or domain text.
- The user requests sources, references, "where is this written?", or asks for confirmation/verification.
- You are not fully certain and answering from memory would risk hallucination.
- The question depends on exact wording, steps, parameters, or system behavior.

When NOT to use it:
- Purely conversational requests that don't depend on our stored knowledge (e.g., brainstorming names).
- General world knowledge questions unrelated to our documents (unless user explicitly wants "what does our KB say?").

How to query (required behavior):
1) Convert the user request into a search query. If the user message is short/ambiguous, expand it using context.
2) Call knowledge_base_query with:
   - mode = "mix" by default
   - include_references = true
   - include_chunk_content = false (set true only for evaluation/debug)
   - response_type chosen to match user needs
3) Use the returned information to answer.
4) If references are returned, cite them in a simple way at the end:
   - Example: Sources: [1] /path/fileA , [2] /path/fileB
5) If the KB returns insufficient/empty results, say so clearly:
   - "I couldn't find this in the Knowledge Base." Then ask for the missing identifier (doc name, feature name, version) OR provide a best-effort answer clearly labeled as uncertain.

Strict rules:
- Do NOT invent undocumented details.
- If KB is unavailable (timeout/error), explicitly state you could not access it and proceed cautiously.
- Use "bypass" mode ONLY when the user explicitly wants a direct LLM answer without KB retrieval.
- Always keep the final answer aligned with KB results; do not contradict them.
```

### 11. Update Tool Description

**File:** `services/chat-service/tools/knowledge_base.py`

Update tool description to match LightRAG contract and policy requirements.

## Implementation Order

1. Add environment variables to `.env`
2. Update knowledge_base.py tool implementation
3. Update tool name references across codebase
4. Update all agent YAML configs with new prompts
5. Update translator prompt in main.py
6. Test with sample queries

## Testing Checklist

- [ ] Guest mode: Ask personalized question → should suggest login
- [ ] Verse explanation without KB → should say "not in content" + suggest verse page
- [ ] Action flow → should propose actions + ask scenario
- [ ] Cancel flow → should ask reason + offer alternative
- [ ] Pending report → should appear in suggestions
- [ ] LightRAG query → should call API and format with citations
- [ ] KB unavailable → should state clearly and proceed cautiously
- [ ] No hallucination → should not invent verse content

## Files to Modify

1. `.env` - Add LightRAG config
2. `services/chat-service/tools/knowledge_base.py` - Replace with LightRAG client
3. `services/chat-service/main.py` - Update tool name references
4. `services/chat-service/tools/registry.py` - Update tool name
5. `services/chat-service/agents/chat_agent.py` - Update tool name check
6. `services/chat-service/config/agent_config.yaml` - New product-specific prompt
7. `services/chat-service/config/personalities/friendly_tutor.yaml` - Updated prompt
8. `services/chat-service/config/personalities/professional_assistant.yaml` - Updated prompt
9. `services/chat-service/config/personalities/minimal_assistant.yaml` - Updated prompt
10. `services/chat-service/main.py` (translator) - Updated prompt

## Notes

- All prompts maintain existing silent operation rules for save_user_info
- All prompts respect <internal_context> format
- Product context: "زندگی با آیه‌ها" campaign with 30 core verses
- User data can include: current_page, current_verse_id, current_action_id
- Tool name change requires updates in 3-4 files
- LightRAG auth supports multiple methods (OAuth2, api_key, bearer token)