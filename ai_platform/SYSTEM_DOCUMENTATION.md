# AI Platform System Documentation

Complete documentation of all AI agents, features, system messages, and architecture.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [AI Agents](#ai-agents)
3. [Tools & Capabilities](#tools--capabilities)
4. [User Data Management](#user-data-management)
5. [System Messages & Prompts](#system-messages--prompts)
6. [API Endpoints](#api-endpoints)
7. [Configuration](#configuration)

---

## System Architecture

### Overview

The AI Platform is a modular, multi-agent system built with:
- **FastAPI** for REST APIs
- **Pydantic-AI** for agent orchestration
- **PostgreSQL** for persistent storage
- **Docker** for containerization

### Architecture Diagram

```
┌─────────────┐
│   Gateway   │  Port 8000 (Public API)
│   Service   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Chat Service│  Port 8001 (Internal)
│             │
│ ┌─────────┐ │
│ │ Agents │ │  default, tutor, professional, minimal, translator
│ └────┬────┘ │
│      │      │
│ ┌────▼────┐ │
│ │ Tools   │ │  calculator, weather, knowledge_base, web_search, etc.
│ └─────────┘ │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ PostgreSQL │  Port 5432
│  Database  │
└────────────┘
```

### Components

1. **Gateway Service** (`services/gateway/`)
   - Public-facing API endpoint
   - CORS enabled
   - Forwards requests to chat service

2. **Chat Service** (`services/chat-service/`)
   - Core AI agent orchestration
   - Session management
   - Context management
   - Tool registry

3. **Shared Modules** (`shared/`)
   - Database models
   - Context manager
   - Base agent interface

---

## AI Agents

The system supports **5 AI agents**, each with distinct personalities and capabilities.

### 1. Default Chat Agent (`default`)

**Key:** `default`  
**Config File:** `config/agent_config.yaml`  
**Version:** 2.0

#### Personality
- Friendly and helpful
- Conversational and natural
- Persian/English bilingual
- Silent memory operations

#### System Prompt
```
تو یک چت‌بات مفید با حافظه هوشمند هستی.

🧠 استفاده از حافظه:
پیام کاربر ممکن است با تگ <internal_context>...</internal_context> شروع شود.
این اطلاعات قبلی کاربر است. از آن استفاده کن اما هرگز این تگ را در پاسخت تکرار نکن!

🔴 ذخیره اطلاعات جدید (حتماً انجام بده):
هر وقت کاربر اطلاعاتی درباره خودش گفت، فوراً از ابزار save_user_info استفاده کن:
- اسم گفت → save_user_info(field_name="name", field_value="...")
- سن گفت (مثل "۲۵ سالمه" یا "25 ساله هستم") → save_user_info(field_name="age", field_value="25")
- شهر گفت → save_user_info(field_name="location", field_value="...")
- شغل گفت → save_user_info(field_name="occupation", field_value="...")
- علاقه گفت → save_user_info(field_name="interest", field_value="...")

⚠️ مهم: هرگز نگو "ذخیره کردم" - فقط طبیعی جواب بده.
⚠️ هرگز تگ internal_context را در پاسخ نشان نده!

🎭 شخصیت: دوستانه، کوتاه و مفید
🌐 زبان: با همان زبان کاربر پاسخ بده
```

#### Available Tools
- `knowledge_base_search` - Search knowledge base
- `calculator` - Mathematical calculations
- `get_weather` - Weather information

#### Model Configuration
- **Model:** `gemini-2.5-flash-lite-preview-09-2025`
- **Temperature:** 0.7
- **Max Turns:** 12

#### User Data Fields (17 enabled)
- Personal: `name`, `full_name`, `age`, `gender`, `birth_month`, `birth_year`, `phone_number`
- Residence: `province`, `city`, `location`
- Activity: `registered_actions`, `score`, `pending_reports`, `level`, `my_actions`, `saved_actions`, `saved_content`, `achievements`
- Additional: `occupation`, `interests`, `language`

---

### 2. Friendly Tutor (`tutor`)

**Key:** `tutor`  
**Config File:** `config/personalities/friendly_tutor.yaml`  
**Version:** 2.0

#### Personality
- Warm, patient, and encouraging
- Educational focus
- Uses emojis to make learning fun
- Celebrates progress and achievements

#### System Prompt
```
You are a friendly, encouraging tutor who loves helping students learn! 📚

🎭 Personality:
- Warm, patient, and encouraging
- Use emojis to make learning fun ✨
- Celebrate small victories and progress 🎉
- Break down complex topics into simple explanations
- Ask follow-up questions to check understanding

🧠 Smart Memory:
- You have access to the save_user_info tool
- When students share information (name, grade, subjects, interests), save it silently
- ⚠️ IMPORTANT: Don't interrupt the learning flow by mentioning data saving
- Focus on teaching, not on technical details

📋 Context Usage:
- Student information is shown at the top of each message
- Use their name, grade level, and interests to personalize lessons
- Remember their learning style and pace
- Last 2 messages help you track the conversation

🌐 Language:
- Use the student's preferred language
- Match their language automatically
- Adjust complexity based on their age/grade
```

#### Available Tools
- `knowledge_base_search` - Educational content search
- `calculator` - Math calculations
- `get_learning_resource` - Learning materials and resources

#### Model Configuration
- **Temperature:** 0.8 (higher for creative responses)
- **Max Turns:** 20

#### User Data Fields (8 enabled)
- `name`, `age`, `grade`, `subject`, `interest`, `learning_style`, `language`, `location`

---

### 3. Professional Assistant (`professional`)

**Key:** `professional`  
**Config File:** `config/personalities/professional_assistant.yaml`  
**Version:** 2.0

#### Personality
- Formal and business-focused
- Concise and efficient
- Task-oriented
- No emojis or casual language

#### System Prompt
```
You are a professional business assistant. Your communication style is formal,
concise, and highly efficient.

🎭 Personality:
- Professional and respectful
- Focused and task-oriented
- Clear and structured communication
- No emojis or casual language

🧠 Smart Memory:
- You have access to the save_user_info tool
- When users share information, save it immediately using the tool
- ⚠️ CRITICAL: Never mention to users that you're saving their information
- This happens silently in the background

📋 Context Usage:
- User information is provided at the top of each message
- Always use this information for personalized responses
- Last 2 user messages are available for context

🌐 Language:
- Use the user's preferred language if set
- Otherwise, match the user's language
- Maintain professional tone in all languages
```

#### Available Tools
- `knowledge_base_search` - Business information
- `web_search` - Current web information
- `get_company_info` - Company details
- `calculator` - Business calculations

#### Model Configuration
- **Temperature:** 0.5 (lower for consistency)
- **Max Turns:** 15

#### User Data Fields (8 enabled)
- `name`, `occupation`, `company`, `location`, `email`, `phone`, `language`, `timezone`

---

### 4. Minimal Assistant (`minimal`)

**Key:** `minimal`  
**Config File:** `config/personalities/minimal_assistant.yaml`  
**Version:** 2.0

#### Personality
- Privacy-focused
- Minimal data collection
- Concise and to-the-point
- Transparent about limitations

#### System Prompt
```
You are a helpful assistant focused on privacy and minimal data collection.

🎭 Personality:
- Helpful but respect privacy
- Only collect essential information
- Concise and to-the-point
- Transparent about limitations

🧠 Minimal Memory:
- You have access to save_user_info tool
- Only save information when absolutely necessary for the task
- Never save sensitive personal details
- Silent operation - never mention data saving

📋 Context Usage:
- Limited user information available
- Focus on current conversation
- Last 2 messages for context only

🌐 Language:
- Match user's language
- Simple, clear communication
```

#### Available Tools
- None (privacy-focused, no external tools)

#### Model Configuration
- **Temperature:** 0.7
- **Max Turns:** 10

#### User Data Fields (2 enabled)
- `language` - Essential for communication
- `name` - Optional, for personalization only

**Privacy Settings:**
- Data TTL: 1 hour (shortest)
- Auto-delete sensitive fields: Enabled

---

### 5. Translator Agent (`translator`)

**Key:** `translator`  
**Type:** Special purpose agent (not a persona)  
**Version:** 2.0

#### Purpose
- Professional translation service
- Accurate and natural translations
- Multi-language support

#### System Prompt
```
You are a professional translator. Translate accurately and naturally.
```

#### Available Tools
- None (pure translation)

#### Model Configuration
- **Temperature:** 0.3 (low for accuracy)
- **Max Turns:** 8

#### Capabilities
- Translation between languages
- Language detection
- Natural phrasing

---

## Tools & Capabilities

### Tool Registry System

Tools are registered globally and assigned to specific personas. Each persona can have different tool sets.

### Available Tools

#### 1. Calculator Tool (`calculator`)

**Purpose:** Mathematical calculations

**Parameters:**
- `expression` (string, required) - Mathematical expression

**Supported Operations:**
- Basic: `+`, `-`, `*`, `/`
- Advanced: `^` (power), `sqrt()`, `sin()`, `cos()`, `tan()`, `log()`, `ln()`
- Constants: `pi`, `e`
- Persian/Arabic digit conversion

**Example:**
```
User: "۱۰۰ ضربدر ۵ چقدر میشه؟"
Tool: calculator(expression="100 * 5")
Result: "[Calculator] 100 * 5 = 500"
```

**Assigned To:** `default`, `tutor`, `professional`

---

#### 2. Knowledge Base Search (`knowledge_base_search`)

**Purpose:** Search internal knowledge base

**Parameters:**
- `query` (string, required) - Search query
- `category` (string, optional) - Filter by category: `technical`, `general`, `faq`, `tutorial`
- `limit` (integer, optional) - Max results (default: 3)

**Status:** Mock implementation - ready for real vector DB integration

**Example:**
```
User: "Tell me about Python"
Tool: knowledge_base_search(query="Python", category="tutorial")
Result: Returns relevant articles/documents
```

**Assigned To:** `default`, `tutor`, `professional`

---

#### 3. Weather Tool (`get_weather`)

**Purpose:** Get weather information for cities

**Parameters:**
- `city` (string, required) - City name
- `unit` (string, optional) - `celsius` or `fahrenheit` (default: celsius)

**Status:** Mock implementation - ready for real weather API integration

**Supported Cities (Mock):**
- Persian: تهران, اصفهان, شیراز, مشهد
- English: New York, London, Paris, Tokyo

**Example:**
```
User: "هوای تهران چطوره؟"
Tool: get_weather(city="تهران")
Result: Temperature, condition, humidity
```

**Assigned To:** `default`

---

#### 4. Web Search Tool (`web_search`)

**Purpose:** Search the web for current information

**Parameters:**
- `query` (string, required) - Search query
- `num_results` (integer, optional) - Number of results (default: 3)

**Status:** Mock implementation - ready for real search API integration

**Example:**
```
User: "Search for Python programming trends"
Tool: web_search(query="Python programming trends", num_results=3)
Result: Returns web search results with titles, snippets, URLs
```

**Assigned To:** `professional`

---

#### 5. Company Info Tool (`get_company_info`)

**Purpose:** Get company information

**Parameters:**
- `company_name` (string, required) - Company name
- `info_type` (string, optional) - `overview`, `contact`, `products`, `financials`

**Status:** Mock implementation - ready for real company API integration

**Supported Companies (Mock):**
- Google, Microsoft

**Example:**
```
User: "Tell me about Google company"
Tool: get_company_info(company_name="Google", info_type="overview")
Result: Company overview, contact, products, financials
```

**Assigned To:** `professional`

---

#### 6. Learning Resource Tool (`get_learning_resource`)

**Purpose:** Get educational resources and learning materials

**Parameters:**
- `subject` (string, required) - Subject name
- `level` (string, optional) - `beginner`, `intermediate`, `advanced`
- `resource_type` (string, optional) - `book`, `video`, `course`, `article`

**Status:** Mock implementation - ready for real learning platform integration

**Example:**
```
User: "منابع یادگیری ریاضی برای سطح intermediate"
Tool: get_learning_resource(subject="ریاضی", level="intermediate")
Result: List of learning resources
```

**Assigned To:** `tutor`

---

### Tool Assignment Matrix

| Tool | Default | Tutor | Professional | Minimal |
|------|---------|-------|--------------|---------|
| `calculator` | ✅ | ✅ | ✅ | ❌ |
| `knowledge_base_search` | ✅ | ✅ | ✅ | ❌ |
| `get_weather` | ✅ | ❌ | ❌ | ❌ |
| `web_search` | ❌ | ❌ | ✅ | ❌ |
| `get_company_info` | ❌ | ❌ | ✅ | ❌ |
| `get_learning_resource` | ❌ | ✅ | ❌ | ❌ |

---

## User Data Management

### User Data Fields

The system supports **17+ user data fields** organized into categories:

#### Personal Information (اطلاعات فردی)
- `phone_number` (string) - شماره همراه
- `full_name` (string) - نام و نام خانوادگی
- `gender` (string) - جنسیت (مرد/زن/male/female)
- `birth_month` (integer) - ماه تولد (1-12)
- `birth_year` (integer) - سال تولد (1900-2025)

#### Residence Information (اطلاعات محل سکونت)
- `province` (string) - استان
- `city` (string) - شهر
- `location` (string) - موقعیت (city/country)

#### Activity Information (اطلاعات Activities)
- `registered_actions` (integer) - کنش ثبت شده
- `score` (integer) - امتیاز
- `pending_reports` (integer) - در انتظار ثبت گزارش
- `level` (string) - سطح من (beginner/intermediate/advanced)
- `my_actions` (array) - کنش های من
- `saved_actions` (array) - کنش های ذخیره شده
- `saved_content` (array) - محتوای ذخیره شده
- `achievements` (array) - دستاوردها

#### Additional Fields
- `name` (string) - نام
- `age` (integer) - سن (1-120)
- `occupation` (string) - شغل
- `interests` (array) - علایق
- `language` (string) - زبان ترجیحی (fa/en/ar/es/fr/de/zh/ja/ru)

### Data Storage

- **Database:** PostgreSQL
- **Table:** `agent_context`
- **Format:** JSONB with `{"value": ...}` structure
- **TTL:** Configurable per persona (default: 4 hours)

### Data Flow

```
User Message
    ↓
Agent Processes
    ↓
save_user_info Tool Called
    ↓
Context Manager
    ↓
PostgreSQL Database
    ↓
Available for All Agents in Session
```

### Silent Operation

**Critical Rule:** Agents NEVER mention data saving to users.

**Wrong:**
- ❌ "I've saved your information"
- ❌ "Let me remember that"
- ❌ "I'll store that"

**Correct:**
- ✅ Natural conversation flow
- ✅ "Hi Mohammad! How can I help?"
- ✅ "Great! Let's continue..."

---

## System Messages & Prompts

### Context Format

User information is provided to agents in `<internal_context>` tags:

```
<internal_context>
📋 اطلاعات کاربر (User Information):
• نام (Name): علی
• سن (Age): 28
• شهر (City): تهران
• امتیاز (Score): 2500
• سطح (Level): advanced

💬 آخرین پیام‌های کاربر (Last User Messages):
• "سلام! من علی هستم"
• "چند امتیاز دارم؟"
</internal_context>

[User's current message]
```

**Important:** Agents must NEVER repeat these tags in responses.

### System Prompt Components

Each agent's system prompt consists of:

1. **Main System Prompt** - Core personality and instructions
2. **Silent Operation Instructions** - How to save data without mentioning it
3. **Tool Usage Instructions** - How to use `save_user_info`
4. **Context Display Configuration** - How to format user info

### Dynamic Tool Description

The `save_user_info` tool description is **dynamically generated** based on enabled fields:

```
MANDATORY: Extract and save user information from messages.

YOU MUST call this tool whenever the user mentions ANY of these:
- User's name (first name, full name, or nickname) → field_name="name", field_value="..."
- User's age in years → field_name="age", field_value="25"
- User's location (city, country, or region) → field_name="location", field_value="..."
...

Examples:
- User says "من علی هستم" → call save_user_info(field_name="name", field_value="علی")
- User says "از شیراز هستم" → call save_user_info(field_name="location", field_value="شیراز")
- User says "25 سالمه" → call save_user_info(field_name="age", field_value="25")

IMPORTANT: Call this tool SILENTLY - never tell the user you're saving info.
```

---

## API Endpoints

### Gateway Service (Port 8000)

#### Health Check
```
GET /health
```

#### List Agents
```
GET /agents
```

#### Send Chat Message
```
POST /chat/{agent_key}
```

**Request Body:**
```json
{
  "message": "User message",
  "session_id": "uuid-or-null",
  "use_shared_context": true,
  "user_data": {
    "full_name": "علی رضایی",
    "phone_number": "09123456789",
    "score": 2500,
    "level": "advanced",
    "city": "تهران"
  }
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "output": "AI response",
  "metadata": {
    "model": "gemini-2.5-flash-lite-preview-09-2025",
    "history": [...]
  },
  "context_updates": {...}
}
```

#### Get User Data
```
GET /session/{session_id}/user-data
```

**Response:**
```json
{
  "session_id": "uuid",
  "personal_info": {
    "full_name": "علی رضایی",
    "phone_number": "09123456789",
    "gender": "مرد",
    "birth_month": 8,
    "birth_year": 1995
  },
  "residence_info": {
    "province": "تهران",
    "city": "تهران"
  },
  "activity_info": {
    "score": 3000,
    "level": "advanced",
    "registered_actions": 25
  },
  "all_data": {...}
}
```

#### Get Context
```
GET /session/{session_id}/context
```

#### Delete Session
```
DELETE /session/{session_id}
```

### Chat Service (Port 8001 - Internal)

Additional endpoints for configuration management:

#### List Tools
```
GET /tools
GET /tools/{tool_name}
```

#### Dynamic Field Management
```
GET /config/fields
POST /config/fields
DELETE /config/fields/{field_name}
POST /config/fields/{field_name}/enable
GET /config/export
POST /config/reload
```

---

## Configuration

### Environment Variables

#### Chat Service
- `DATABASE_URL` - PostgreSQL connection string
- `LITELLM_API_KEY` - API key for LLM provider
- `LITELLM_BASE_URL` - Base URL for LLM API (default: https://api.avalai.ir/v1)
- `LITELLM_MODEL` - Model name (default: gemini-2.5-flash-lite-preview-09-2025)
- `MAX_SESSION_MESSAGES` - Max messages per session (default: 30)
- `SESSION_TTL_SECONDS` - Session TTL (default: 14400 = 4 hours)

#### Gateway Service
- `CHAT_SERVICE_URL` - Internal chat service URL (default: http://chat-service:8001)

### Model Configuration

Each persona can have different model settings:

```yaml
model_config:
  default_model: "gemini-2.5-flash-lite-preview-09-2025"
  temperature: 0.7  # 0.0-1.0, higher = more creative
  max_turns: 12     # Max conversation turns
  max_tokens: null  # null = no limit
```

### Privacy Configuration

```yaml
privacy:
  data_ttl: 14400  # Seconds (4 hours)
  auto_delete_sensitive_fields: false
  sensitive_fields:
    - user_email
    - user_phone
  require_consent_for:
    - user_email
    - user_phone
```

---

## Features Summary

### Core Features

✅ **Multi-Agent System** - 5 distinct AI agents  
✅ **Shared Context** - All agents access same user data in session  
✅ **Dynamic User Data** - 17+ configurable fields  
✅ **Tool System** - Modular tools assigned per persona  
✅ **Silent Memory** - Data saved without interrupting conversation  
✅ **Persian/English** - Full bilingual support  
✅ **Session Management** - Persistent conversations  
✅ **API Integration** - RESTful API with Gateway  
✅ **Privacy Controls** - Configurable data retention  

### Advanced Features

✅ **Dynamic Field Management** - Add/remove fields at runtime  
✅ **Persona Switching** - Switch agents mid-conversation  
✅ **Partial Updates** - Update specific user data fields  
✅ **Context Persistence** - Data survives across messages  
✅ **Tool Registry** - Centralized tool management  
✅ **Mock Tools** - Ready for real API integration  

---

## File Structure

```
ai_platform/
├── services/
│   ├── gateway/          # Public API gateway
│   │   └── main.py
│   └── chat-service/     # Core AI service
│       ├── main.py       # API endpoints, agent registration
│       ├── agents/
│       │   ├── chat_agent.py      # Main chat agent
│       │   ├── translator_agent.py
│       │   ├── config_loader.py   # YAML config loader
│       │   └── litellm_compat.py  # LLM compatibility layer
│       ├── tools/        # Tool implementations
│       │   ├── registry.py
│       │   ├── calculator.py
│       │   ├── weather.py
│       │   ├── knowledge_base.py
│       │   └── web_search.py
│       └── config/
│           ├── agent_config.yaml          # Default agent
│           └── personalities/
│               ├── friendly_tutor.yaml
│               ├── professional_assistant.yaml
│               └── minimal_assistant.yaml
├── shared/               # Shared modules
│   ├── base_agent.py     # Base agent interface
│   ├── context_manager.py
│   ├── database.py
│   └── schemas.py
└── docker-compose.yml
```

---

## Development Notes

### Adding a New Agent

1. Create YAML config in `config/personalities/`
2. Add to `persona_configs` in `main.py`
3. Assign tools in `persona_tool_assignments`
4. Restart service

### Adding a New Tool

1. Create tool class in `tools/` directory
2. Inherit from `Tool` base class
3. Register in `main.py` startup
4. Assign to personas in `persona_tool_assignments`

### Modifying System Prompts

Edit YAML config files in `config/` directory. Changes take effect on service restart.

---

## Testing

Comprehensive test scripts available:
- `test_user_data_long_conversation.sh` - Full system test
- `test_user_data_api.sh` - API functionality test

---

**Last Updated:** 2025-12-19  
**Version:** 2.0

