# Guardrails Implementation - Relevance Check

## Overview

Guardrails have been added to all AI agents to prevent them from answering irrelevant or off-topic questions. This ensures agents stay focused on their core mission.

## What Was Added

### Guardrail Section in All Personality Configs

Each agent now has a `⚠️⚠️⚠️ GUARDRAILS - RELEVANCE CHECK ⚠️⚠️⚠️` section that defines:

1. **✅ Relevant Topics** - What the agent should answer
2. **❌ Irrelevant Topics** - What the agent should NOT answer
3. **📋 How to Decline** - Template for politely declining irrelevant questions

## Agent-Specific Guardrails

### 1. Default Agent (`agent_config.yaml`)
**Relevant:**
- Quranic verses and interpretation
- Quranic actions (کنش)
- Content related to سفیران آیه‌ها
- Platform usage questions
- Educational questions about Quranic concepts

**Irrelevant:**
- General knowledge (history, geography, science, math - unless Quran-related)
- Technical computer questions
- Medical questions (unless medical agent)
- Legal questions (unless Quran-related)
- Political news
- Entertainment (unless Quran-related)

### 2. Friendly Tutor (`friendly_tutor.yaml`)
**Relevant:**
- Teaching and explaining Quranic verses to students
- How to teach Quranic concepts
- Designing educational content for classes
- School and educational actions
- Student questions about verses

**Irrelevant:**
- Non-Quranic academic subjects (math, physics, chemistry, non-Quranic history, geography)
- Technical computer questions
- Medical questions
- Legal questions (unless Quran-related)

### 3. Konesh Expert (`konesh_expert.yaml`)
**Relevant:**
- Selecting appropriate actions (home, school, mosque, virtual)
- How to execute actions
- Designing new actions
- Explaining existing actions
- Guidance for action execution

**Irrelevant:**
- Questions about verses (unless related to actions)
- Non-related educational questions
- Technical, medical, legal questions
- General questions unrelated to actions

### 4. Minimal Assistant (`minimal_assistant.yaml`)
**Relevant:**
- Quranic verses and interpretation
- Quranic actions
- Content related to سفیران آیه‌ها
- Platform questions (with privacy protection)

**Irrelevant:**
- General unrelated questions
- Technical, medical, legal questions
- Unnecessary personal questions

### 5. Professional Assistant (`professional_assistant.yaml`)
**Relevant:**
- Quranic verses and related content
- Quranic actions
- Content related to سفیران آیه‌ها
- Professional questions about the platform

**Irrelevant:**
- General unrelated questions
- Unrelated technical questions
- Unrelated medical, legal questions

### 6. Orchestrator (`orchestrator.yaml`)
**Special Behavior:**
- Checks relevance BEFORE routing
- If question is irrelevant, politely declines instead of routing
- Only routes relevant questions to appropriate agents

## Decline Template

All agents use a similar template to decline irrelevant questions:

```
"سلام! من [نوع دستیار] هستم و فقط می‌تونم در مورد [موضوعات مرتبط] کمکت کنم.

سوال تو در مورد [موضوع سوال] هست که خارج از حیطه کاری من هست.

اگه سوالی درباره [موضوعات مرتبط] داری، خوشحال می‌شم کمکت کنم! 😊"
```

Then suggests relevant topics:
- "درباره کنش‌های قرآنی بیشتر بدانم"
- "آیه‌های مرتبط"
- "نحوه استفاده از پلتفرم"

## Files Updated

1. ✅ `services/chat-service/config/agent_config.yaml`
2. ✅ `services/chat-service/config/personalities/friendly_tutor.yaml`
3. ✅ `services/chat-service/config/personalities/konesh_expert.yaml`
4. ✅ `services/chat-service/config/personalities/minimal_assistant.yaml`
5. ✅ `services/chat-service/config/personalities/professional_assistant.yaml`
6. ✅ `services/chat-service/config/personalities/orchestrator.yaml`

## Testing

To test guardrails:

```bash
# Test with irrelevant question
curl -X POST http://localhost:8001/chat/default \
  -H "Content-Type: application/json" \
  -d '{"message": "چطور یک وب‌سایت بسازم؟", "session_id": null}'

# Should get polite decline, not an answer
```

## To Apply Changes

```bash
docker-compose restart chat-service
```

After restart, all agents will check relevance before answering and politely decline irrelevant questions.

